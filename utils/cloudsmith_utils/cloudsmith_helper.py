#!/usr/bin/python3

# File name: cloudsmith_helper.py
# Author: Nicu Siderias <nicu.siderias@analog.com>
# Description: Helper script for interacting with the Cloudsmith package repository API.
#              Provides functions to upload, download, copy, delete, and query packages
#              using Cloudsmith's version field as a virtual folder structure.
#              Requires CLOUDSMITH_API_KEY environment variable.

import argparse
import functools
import inspect
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import PurePosixPath

import requests

########################### Global Vars Instantiation ####################
API_URL = "https://api.cloudsmith.io/v1"

if "CLOUDSMITH_API_KEY" not in os.environ:
    raise RuntimeError("Cloudsmith_helper: CLOUDSMITH_API_KEY variable is not exported.")

session = requests.Session()
session.headers.update({"X-Api-Key": os.environ["CLOUDSMITH_API_KEY"]})

LOCAL_THREAD_STORAGE = threading.local()


def _get_session():
    """
    Returns a thread-local `requests.Session`, creating it on first use.

    `requests.Session` is not thread-safe, so each worker thread (e.g. those
    spawned by the ThreadPoolExecutor) gets its own session rather than sharing
    the module-level `session`. The session is pre-authenticated with the
    Cloudsmith API key and reused for the lifetime of the thread to benefit from
    connection pooling.

    :return: `requests.Session` the session bound to the current thread
    """
    if not hasattr(LOCAL_THREAD_STORAGE, "session"):
        LOCAL_THREAD_STORAGE.session = requests.Session()
        LOCAL_THREAD_STORAGE.session.headers.update({"X-Api-Key": os.environ["CLOUDSMITH_API_KEY"]})
    return LOCAL_THREAD_STORAGE.session


def _configure_logger(enable_logging=False, debug=False):
    logger.setLevel(logging.INFO)

    if logger.handlers:
        logger.handlers.clear()

    if __name__ == "__main__" or enable_logging or debug:
        handler = logging.StreamHandler(sys.stdout)
        if debug:
            logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
        else:
            logger.setLevel(logging.INFO)
            formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
    else:
        handler = logging.FileHandler(os.devnull)

    logger.addHandler(handler)


def _format_repo(repo):
    """
    Helper function that formats the repository name to include the 'adi/' prefix if missing.

    :param repo: `String` repository name
    :return: `String` formatted repository name
    """
    if not repo.startswith("adi/"):
        return "adi/" + repo
    return repo


def _log_on_exit(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"{func.__name__}: ENTERING")
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.debug(f"{func.__name__}: DONE ({elapsed:.2f}s)")
        return result

    return wrapper


logger = logging.getLogger(__name__)
_configure_logger()

# Global args variable, will be set when running from command line
args = None


def _resolve_param(value, attr_name, default=None, context=None):
    """
    Resolve a parameter from the function argument or the global CLI `args`.

    Falls back to `args.<attr_name>` when `value` is false. If still unresolved,
    returns `default` (when provided) or raises `RuntimeError` (when `context`
    is provided, indicating the parameter is required).

    :param value: `Any` the value passed by the caller.
    :param attr_name: `String` attribute name to look up on the global `args` namespace.
    :param default: `Any` fallback value if unresolved. `None` means no default.
    :param context: `String` if provided, the parameter is treated as required and this
                    string completes the error message (e.g., `"to deploy a package."`).
    :return: `Any` the resolved value.
    :raises RuntimeError: when the parameter is unresolved and `context` is provided.
    """
    if not value and args:
        value = getattr(args, attr_name, None)
    if not value:
        if default is not None:
            return default
        elif context:
            raise RuntimeError(f"Cloudsmith_helper: {attr_name} is required {context}")
    return value


def _get_public_methods(module=None):
    """
    Return the public function objects defined in a module, intended to be
    exposed as CLI-invokable methods via `--method`.

    :param module: `module` the module to introspect. Defaults to this module.
    :return: `List` of function objects defined in the given module.
    """
    module = module or sys.modules[__name__]
    own = [
        obj
        for name, obj in vars(module).items()
        if inspect.isfunction(obj) and obj.__module__ == module.__name__ and not name.startswith("_")
    ]
    return own


########################### Define Arguments #############################
def _set_arguments():
    parent_args_parser = argparse.ArgumentParser(add_help=False)
    parent_args_parser.add_argument("--method", help="Method to invoke from this script.")
    parent_args_parser.add_argument(
        "--package_version",
        help="The version of the package, it is the location where you expect to find the package in a folder structure.",
    )
    parent_args_parser.add_argument("--package_name", help="The name of the package.")
    parent_args_parser.add_argument("--package_tags", help="List of tags for a package separated by a `,`.")
    parent_args_parser.add_argument("--local_path", help="Local path of a package to be uploaded to Cloudsmith.")
    parent_args_parser.add_argument(
        "--new_package_version", help="New package version used to copy to another location."
    )
    parent_args_parser.add_argument("--new_package_name", help="New package name used to copy to another location.")
    parent_args_parser.add_argument("--new_repo", help="Name of a new repository to copy a package to.")
    parent_args_parser.add_argument("--repo", help="Name of the Cloudsmith repositories to perform the actions.")
    parent_args_parser.add_argument(
        "--keep_folder_structure", action="store_true", help="Recreate folder structure based on package version."
    )
    parent_args_parser.add_argument(
        "--no_rel_path",
        action="store_true",
        help="Do not append relative path of local file to the package version.",
    )
    parent_args_parser.add_argument("--debug", action="store_true", help="Enable debug logging.")

    parser = argparse.ArgumentParser(
        prog="Cloudsmith Helper Script",
        description="This is a helper script for interacting with the Cloudsmith server. "
        "Required environmental variables: CLOUDSMITH_API_KEY. Requires the python package: cloudsmith-cli",
        epilog="Common error codes: 400: Bad Request, 401: Unauthorized, 403: Forbidden, 404: Not Found, 422: Unprocessable Entity. "
        "https://docs.cloudsmith.com/api/error-handling",
        parents=[parent_args_parser],
    )

    return parser.parse_args()


########################### Define Helper Methods ########################
PACKAGE_CACHE = {}


@_log_on_exit
def _get_all_packages(query, repo):
    """
    Function which fetches all packages matching a query from a Cloudsmith
    repository. Results are cached per version query and pages are fetched in
    parallel. If the query contains a '+name:' filter, it is applied locally
    against the cached version results.

    :param query: `String` Cloudsmith search query, optionally with a '+name:' filter.
    :param repo: `String` Cloudsmith repository name.
    :return: `List` of package dictionaries matching the query.
    """
    # Cache: strip +name: from query, fetch all packages for that version,
    # then filter locally by name if needed.
    name_filter = None
    version_query = query
    if "+name:" in query:
        version_query, name_filter = query.split("+name:", 1)

    cache_key = (version_query, repo)
    if cache_key in PACKAGE_CACHE:
        logger.debug(f"Cache hit for {version_query} in {repo}")
        if name_filter:
            return [p for p in PACKAGE_CACHE[cache_key] if re.search(name_filter, p["name"])]
        return PACKAGE_CACHE[cache_key]

    page_size = 500
    cloudsmith_repo = _format_repo(repo)
    base_url = f"{API_URL}/packages/{cloudsmith_repo}?query={version_query}&page_size={page_size}"

    # First request to get total count
    r = None
    for attempt in range(3):
        r = session.get(f"{base_url}&page=1")
        if r.ok:
            break
        if r.status_code == 404 and json.loads(r.text).get("detail") == "Invalid page.":
            return []
        if attempt < 2:
            time.sleep(2)
            logger.warning(f"Attempt {attempt + 1} failed with status {r.status_code}, retrying...")
        else:
            raise RuntimeError(
                f"Request to the Cloudsmith API failed - {base_url}. Status code: {r.status_code}. Status message: {r.text}"
            )

    packages = json.loads(r.text)

    # Get number of pages from response headers
    total_pages = int(r.headers.get("x-pagination-pagetotal", 1))

    if total_pages <= 1:
        PACKAGE_CACHE[cache_key] = packages
        if name_filter:
            return [p for p in packages if re.search(name_filter, p["name"])]
        return packages

    def fetch_page(page):
        """
        Function which fetches packages from one page.
        """
        url = f"{base_url}&page={page}"
        resp = None
        for attempt in range(3):
            resp = _get_session().get(url)
            if resp.ok:
                break
            if resp.status_code == 404 and json.loads(resp.text).get("detail") == "Invalid page.":
                return []
            if attempt < 2:
                time.sleep(2)
                logger.warning(f"Attempt {attempt + 1} failed with status {resp.status_code}, retrying...")
            else:
                raise RuntimeError(
                    f"Request failed - {url}. Status code: {resp.status_code}. Status message: {resp.text}"
                )
        return json.loads(resp.text)

    # Fetch remaining pages in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_page, page): page for page in range(2, total_pages + 1)}
        for future in as_completed(futures):
            packages.extend(future.result())

    PACKAGE_CACHE[cache_key] = packages
    if name_filter:
        return [p for p in packages if re.search(name_filter, p["name"])]
    return packages


@_log_on_exit
def check_path(package_version=None, package_name=None, repo=None):
    """
    Check if a package exists at a given version path.

    This is checked using the version which specifies where you would expect
    to find a package if there was a folder structure. The version should have
    a '/' at the end to specify a subpath, otherwise the checking is done considering the regex '^version$'

    :param package_version: `String` location to check. Relative URL after REPO.
    :param package_name: `String` Name of the package to check.
    :param repo: `String` Cloudsmith repository name.
    :return: `Boolean` True if the path exists, False otherwise.
    """
    package_version = _resolve_param(package_version, "package_version", context="to check if a path exists.")
    repo = _resolve_param(repo, "repo", context="to check if a path exists.")
    package_name = _resolve_param(package_name, "package_name", context="to check if a path exists.")

    package_version = package_version.replace("/", "-")
    url = f"https://dl.cloudsmith.io/basic/adi/{repo}/raw/versions/{package_version}/{package_name}"

    logger.info(f"Checking path existence for version: '{package_version}' and file'{package_name}' in repo: '{repo}'")

    response = session.head(url)
    if response.status_code == 200:
        return True
    logger.info(f"Response status code: {response.status_code} for URL: {url}.")
    return False


@_log_on_exit
def get_subfolders(package_version=None, repo=None):
    """
    List first-level subfolders at a given version path.

    :param package_version: `String` version representing the theoretical path of files.
    :param repo: `String` Cloudsmith repository name.
    :return: `List` full list of subfolders from the given location.
    """
    package_version = _resolve_param(package_version, "package_version", context="to get subfolders.")
    repo = _resolve_param(repo, "repo", context="to get subfolders.")

    logger.info(f"Getting subfolders for version: '{package_version}' in repo: '{repo}'")

    enhance_package_version = package_version
    if not package_version.startswith("^"):
        enhance_package_version = f"^{package_version}"
    if not package_version.endswith("/"):
        enhance_package_version += "/"

    packages = _get_all_packages(f"version:{enhance_package_version}", repo)

    # Extract unique first-level subfolder names from each package's version path.
    # For each package, compute the relative path from base package_version, then take the
    # first component as the subfolder name. Packages at the root level (no parts) are filtered out.
    # Example: package_version="hdl/main", package["version"]="hdl/main/boot_files" -> subfolder="boot_files"
    folders = sorted(
        list(
            set(
                p.parts[0]
                for package in packages
                if (p := PurePosixPath(package["version"]).relative_to(package_version)).parts
            )
        )
    )
    logger.info("Subfolders: " + str(folders))

    return folders


@_log_on_exit
def get_files(package_version=None, repo=None):
    """
    List the files stored at an exact version path.

    The `package_version` is anchored so it matches that version only,
    treating it as a virtual folder whose contents are the returned filenames.

    :param package_version: `String` theoretical location of the files.
    :param repo: `String` Cloudsmith repository name.
    :return: `List` full list of files from the specified location.
    """
    package_version = _resolve_param(package_version, "package_version", context="to get files.")
    repo = _resolve_param(repo, "repo", context="to get files.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("$"):
        package_version += "$"

    logger.info(f"Getting files for version: '{package_version}' in repo: '{repo}'")

    packages = _get_all_packages(f"version:{package_version}", repo)
    files = sorted(list(package["filename"] for package in packages))
    logger.info("Files: " + str(files))

    return files


@_log_on_exit
def get_folder_structure(package_version=None, repo=None):
    """
    List all relative paths recursively under a version path.

    :param package_version: `String` location to get folder structure for
    :param repo: `String` Cloudsmith repository name.
    :return: `List` list of files at the given location (with relative paths)
    """
    package_version = _resolve_param(package_version, "package_version", context="to get folder structure.")
    repo = _resolve_param(repo, "repo", context="to get folder structure.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("/"):
        package_version += "/"

    logger.info(f"Getting folder structure for version: '{package_version}' in repo: '{repo}'")

    packages = _get_all_packages(f"version:{package_version}", repo)

    folders = sorted(list(set(package["version"][len(package_version) - 1 :] for package in packages)))
    logger.info("Subfolders: " + str(folders))

    return folders


@_log_on_exit
def get_folder_and_files_structure(package_version=None, repo=None):
    """
    List folders and their files under a version path.

    :param package_version: `String` location to get folder structure for
    :param repo: `String` Cloudsmith repository name.
    :return: `Dict<String, List<String>>` dictionary with folder paths as keys and list of files as values
    """
    package_version = _resolve_param(package_version, "package_version", context="to get folder structure.")
    repo = _resolve_param(repo, "repo", context="to get folder structure.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("/"):
        package_version += "/"

    logger.info(f"Getting folder and files structure for version: '{package_version}' in repo: '{repo}'")

    packages = _get_all_packages(f"version:{package_version}", repo)

    folders_and_files = {}
    for package in packages:
        relative_path = package["version"][len(package_version) - 1 :]
        if relative_path not in folders_and_files:
            folders_and_files[relative_path] = []
        folders_and_files[relative_path].append(package["filename"])

    # Because we push artifacts wihtout waiting time (-W) there can be a time when
    # the packages are not sync. This can result in duplicated artifacts,
    # with the same name and version, until the system "republish it".
    # To void that, a set, on the files, is used
    folders_and_files = {k: sorted(set(v)) for k, v in sorted(folders_and_files.items())}
    logger.info("Subfolders and files: " + str(folders_and_files))

    return folders_and_files


@_log_on_exit
def copy_to_location(
    package_version=None,
    package_name=None,
    new_package_version=None,
    new_package_name=None,
    new_repo=None,
    package_tags=None,
    repo=None,
):
    """
    Copy packages from one version path to another.

    Downloads packages locally first, then re-uploads with the `new_package_version`
    to a `new_repo` or the same repository.

    :param package_version: `String` version representing theoretical path of the packages.
    :param package_name: `String` name of the package to download. Copy all files if this is missing.
    :param new_package_version: `String` new version representing the new theoretical path to upload
                          the packages to. If missing, keep the same version.
    :param new_package_name: `String` new name for the package at the destination. If missing, use the
                          original package name.
    :param new_repo: `String` new repository where to upload to. If missing, use the same repo.
    :param package_tags: `String` tags for the package(s) split by ','. If missing, inherit the
                   tags from the original package.
    :param repo: `String` Cloudsmith repository name.
    """
    package_version = _resolve_param(package_version, "package_version", context="to copy a package.")
    repo = _resolve_param(repo, "repo", context="to copy a package.")
    package_name = _resolve_param(package_name, "package_name")
    new_package_version = _resolve_param(new_package_version, "new_package_version", default=package_version)
    new_package_name = _resolve_param(new_package_name, "new_package_name")
    new_repo = _resolve_param(new_repo, "new_repo", default=repo)
    package_tags = _resolve_param(package_tags, "package_tags")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"

    if package_version.endswith("/") and not package_name and not new_package_version.endswith("/"):
        raise RuntimeError(
            "Cloudsmith_helper: If the source package_version is a folder (ends with '/'), the new_package_version must also be a folder (end with '/')."
        )

    logger.info(
        f"Copying packages from version: '{package_version}' in repo: '{repo}' to version: '{new_package_version}' in repo: '{new_repo}'"
    )

    # Download packages
    packages = get_artifacts_from_location(package_version, package_name, repo=repo)

    for package in packages:
        if not package_tags:
            package_tags = ",".join(package.get("tags", {}).get("info", []))

        # Use new_package_name if provided, otherwise keep the original package name
        upload_name = new_package_name if new_package_name else package["name"]
        if upload_name != package["name"]:
            os.rename(package["name"], upload_name)

        logger.info(
            f"Copy package: '{upload_name}({package['name']})' with version: '{new_package_version}' in repo: '{new_repo}' with tags: '{package_tags}'"
        )
        deploy_to_location(upload_name, new_package_version, package_tags, repo=new_repo)
        # delete local files
        os.remove(upload_name)


@_log_on_exit
def remove_item_from_location(package_version=None, package_name=None, repo=None):
    """
    Delete packages matching a version and name.

    Can be either a file or a directory.
    Use `"*"` for either parameter to match all versions or names respectively.

    :param package_version: `String` version(location) of the package to be removed. Use `"*"` to match all versions.
    :param package_name: `String` name of the package to be removed. Use `"*"` to match all names.
    :param repo: `String` Cloudsmith repository name.
    """
    repo = _resolve_param(repo, "repo", context="to remove an item.")
    package_version = _resolve_param(package_version, "package_version", context="to remove an item.")
    package_name = _resolve_param(package_name, "package_name", context="to remove an item.")

    # Build query based on provided parameters
    query = ""
    if package_version and package_version != "*":
        query += f"version:{package_version}"
    if package_name and package_name != "*":
        query += "+" if query else ""
        query += f"name:{package_name}"

    cloudsmith_repo = _format_repo(repo)
    logger.info(
        f"Package(s) {(f'with name {package_name}' if package_name else '')} {(f'with version {package_version}' if package_version else '')} from repo {cloudsmith_repo} will be deleted"
    )
    packages = _get_all_packages(query, repo)
    if not packages:
        logger.info("No packages found to delete.")
        return

    def delete_package(package):
        logger.info(f"Deleting package {package['name']} with identifier {package['identifier_perm']}")
        url = f"{API_URL}/packages/{cloudsmith_repo}/{package['identifier_perm']}"
        for attempt in range(3):
            r = _get_session().delete(url)
            if r.ok:
                break
            if attempt < 2:
                time.sleep(2)
                logger.warning(f"Attempt {attempt + 1} failed with status {r.status_code}, retrying...")
            else:
                raise RuntimeError(f"Request to the Cloudsmith API failed - DELETE {url} returned {r.status_code}")
        logger.info(f"Package {package['name']} with identifier {package['identifier_perm']} was deleted")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(delete_package, package): package for package in packages}
        for future in as_completed(futures):
            future.result()


@_log_on_exit
def get_artifacts_from_location(package_version=None, package_name=None, keep_folder_structure=False, repo=None):
    """
    Download packages matching a version path.
    The `keep_folder_structure` can be recreated based on the `package_version`.

    :param package_version: `String` version(location) of the package(s) to be downloaded.
    :param package_name: `String` name of the package to download. If missing, all packages matching the version will be downloaded.
    :param keep_folder_structure: `Bool` specify if the folder structure should be recreated. Defaults to False.
    :param repo: `String` Cloudsmith repository name.
    :return: `List` of the packages that were downloaded.
    """
    package_version = _resolve_param(package_version, "package_version", context="to get artifacts.")
    repo = _resolve_param(repo, "repo", context="to get artifacts.")
    package_name = _resolve_param(package_name, "package_name")
    keep_folder_structure = _resolve_param(keep_folder_structure, "keep_folder_structure")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"

    query = f"version:{package_version}"
    if package_name:
        query += f"+name:{package_name}"

    packages = _get_all_packages(query, repo)

    for package in packages:
        logger.info(f"Downloading package: {package['name']} from {package['cdn_url']}")
        response = session.get(package["cdn_url"])
        if response.status_code != 200:
            raise RuntimeError(
                f"Download failed for {package['name']} from {package['cdn_url']}. Status code: {response.status_code}"
            )
        with open(package["name"], "wb") as f:
            f.write(response.content)
        if keep_folder_structure:
            dir_to_create = (
                os.path.dirname(package["version"])
                if "." in os.path.basename(package["version"])
                else package["version"]
            )
            os.makedirs(dir_to_create, exist_ok=True)
            os.rename(package["name"], os.path.join(dir_to_create, package["name"]))
    logger.info(f"{len(packages)} packages with version {package_version} have been downloaded")
    return packages


@_log_on_exit
def deploy_to_location(local_path=None, package_version=None, package_tags=None, repo=None):
    """
    Upload a raw package to Cloudsmith.

    Requires the `cloudsmith-cli` tool to be installed.
    This can be done via `pip` - `python -m pip install cloudsmith-cli`

    :param local_path: `String` relative (or absolute) path to the package to be uploaded to Cloudsmith.
    :param package_version: `String` package version representing the path where you would like to find the package
                            if there would've been a folder structure. Required.
    :param package_tags: `String` tags to be assigned to the package, separated by a `,`.
    :param repo: `String` Cloudsmith repository name.
    """

    local_path = _resolve_param(local_path, "local_path", context="to deploy a package.")
    repo = _resolve_param(repo, "repo", context="to deploy a package.")
    package_version = _resolve_param(package_version, "package_version", context="to deploy a package.")
    package_tags = _resolve_param(package_tags, "package_tags")

    cloudsmith_repo = _format_repo(repo)
    cmd = ["cloudsmith", "push", "raw", "-SW", "--republish", cloudsmith_repo, local_path]

    cmd.extend(["--version", package_version])
    if package_tags:
        cmd.extend(["--tags", package_tags])

    output = subprocess.run(cmd, capture_output=True)
    if output.returncode == 0:
        logger.info(
            f"Package successfully uploaded package:{local_path} version:{package_version} package_tags:{package_tags}"
        )
    else:
        raise RuntimeError(
            f"cmd: {cmd} failed with exit code {output.returncode}! stderr: {output.stderr.decode('utf-8')} stdout: {output.stdout.decode('utf-8')}"
        )


@_log_on_exit
def upload_to_location(local_path=None, package_version=None, package_tags=None, no_rel_path=False, repo=None):
    """
    Upload files or directories to Cloudsmith.

    If `local_path` is a directory, all files within it are uploaded recursively.
    When `no_rel_path` is False, the file's directory path relative to `local_path`
    is appended to `package_version`.

    :param local_path: `String` path to a file or directory to upload.
    :param package_version: `String` version (virtual folder path) for the upload.
    :param package_tags: `String` tags for the package(s), separated by a `,`.
    :param no_rel_path: `Bool` if True, do not append relative path to version. Defaults to False.
    :param repo: `String` Cloudsmith repository name.
    """
    local_path = _resolve_param(local_path, "local_path", context="to upload.")
    repo = _resolve_param(repo, "repo", context="to upload.")
    package_version = _resolve_param(package_version, "package_version", default="")
    package_tags = _resolve_param(package_tags, "package_tags")
    no_rel_path = _resolve_param(no_rel_path, "no_rel_path")

    if package_version and not package_version.endswith("/"):
        package_version += "/"

    local_path = os.path.abspath(local_path) if "/" in local_path else local_path

    # Collect files to upload
    files_to_upload = []
    if os.path.isdir(local_path):
        for dirpath, _, filenames in os.walk(local_path):
            for fname in filenames:
                files_to_upload.append(os.path.join(dirpath, fname))
    elif os.path.isfile(local_path):
        files_to_upload.append(local_path)
    else:
        raise RuntimeError(f"Cloudsmith_helper: local_path does not exist: {local_path}")

    for file_path in files_to_upload:
        if no_rel_path:
            file_version = package_version
        else:
            file_version = package_version + os.path.dirname(file_path)

        logger.info(f"Uploading {file_path} to adi/{repo} with version '{file_version}'")
        deploy_to_location(file_path, file_version, package_tags, repo=repo)


@_log_on_exit
def get_item_properties(package_version=None, package_name=None, repo=None):
    """
    Get tags for a specific package.

    :param package_version: `String` version of the package representing the theoretical location. Optional.
    :param package_name: `String` the name of the Cloudsmith package to retrieve tags from. Properties for folders do not exist.
    :param repo: `String` Cloudsmith repository name.
    :return: `List` the tags for the given file
    """
    package_name = _resolve_param(package_name, "package_name", context="to get item properties.")
    repo = _resolve_param(repo, "repo", context="to get item properties.")
    package_version = _resolve_param(package_version, "package_version")

    query = ""
    if package_version:
        query += f"version:{package_version}+"
    query += f"name:{package_name}"

    packages = _get_all_packages(query, repo)
    if not len(packages):
        raise RuntimeError(
            f"No package was found with the given parameters: version:{package_version} name:{package_name}!"
        )
    if len(packages) > 1:
        raise RuntimeError(
            f"Multiple packages found with the given parameters: version:{package_version} name:{package_name}!"
        )

    logger.info(
        f"Tags for package with version: '{package_version}' and name: '{package_name}' in repo: '{repo}': {packages[0]['tags']['info']}"
    )

    return packages[0]["tags"]["info"]


@_log_on_exit
def get_item_properties_as_dict(package_version=None, package_name=None, repo=None):
    """
    Get tags for a package as a key-value dictionary.
    Tags name/value should be separated by '-' in Cloudsmith.

    E.g., a tag `commit_date=2024-08-21-08-44-50` in Cloudsmith should be represented as `commit_date-2024-08-21-08-44-50`

    :param package_version: `String` version of the package representing the theoretical location. Optional.
    :param package_name: `String` the name of the Cloudsmith package to retrieve tags from. Properties for folders do not exist.
    :param repo: `String` Cloudsmith repository name.
    :return: `Dict` the tags for the given file as a dictionary
    """
    tags = get_item_properties(package_version, package_name, repo)
    tags_dict = {}
    for tag in tags:
        if "-" in tag:
            key, value = tag.split("-", 1)
            if key in tags_dict:
                tags_dict[key].append(value)
            else:
                tags_dict[key] = [value]
        else:
            tags_dict[tag] = None

    logger.info(f"Tags as dict: {tags_dict}")

    return tags_dict


@_log_on_exit
def get_sha256_for_file(package_version=None, package_name=None, repo=None):
    """
    Get the SHA256 checksum of a package.

    :param package_version: `String` version of the package representing the theoretical location.
    :param package_name: `String` the name of the Cloudsmith package to retrieve tags from.
    :param repo: `String` Cloudsmith repository name.
    :return: `String` sha256 hash of the package
    """
    package_name = _resolve_param(package_name, "package_name", context="to get item sha.")
    repo = _resolve_param(repo, "repo", context="to get item sha.")
    package_version = _resolve_param(package_version, "package_version", context="to get item sha.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("$"):
        package_version += "$"

    query = f"version:{package_version}+name:{package_name}"

    packages = _get_all_packages(query, repo)
    if not len(packages):
        raise RuntimeError(
            f"Cloudsmith_helper: No package was found with the given parameters: version:{package_version} name:{package_name}!"
        )
    if len(packages) > 1:
        raise RuntimeError(
            f"Cloudsmith_helper: Multiple packages found with the given parameters: version:{package_version} name:{package_name}!"
        )

    return packages[0]["checksum_sha256"]


if __name__ == "__main__":
    args = _set_arguments()

    if not args:
        raise RuntimeError("Cloudsmith_helper: Arguments failed to parse or are missing, try using `-h`")

    available_methods = _get_public_methods()

    if args.method is None:
        logger.warning("Method argument is missing! Available methods:")
        for method in available_methods:
            # Get the documentation first line of each function
            first_line = (method.__doc__ or "").strip().split("\n")[0]
            # Get the function parameters
            params = ", ".join(inspect.signature(method).parameters)
            # Create the headers
            header = f"{method.__name__}({params})"
            if len(header) > 60:
                # For long headers, split the parameters and the description of different lines
                logger.info(f"  {method.__name__:60s} {first_line}\n\t({params})")
            else:
                logger.info(f"  {header:60s} {first_line}")
    else:
        if not args.repo:
            raise RuntimeError("Cloudsmith_helper: --repo is required.")
        method_map = {m.__name__: m for m in available_methods}
        if args.method not in method_map:
            raise RuntimeError(f"Cloudsmith_helper: Method not found: {args.method}")
        _configure_logger(True, args.debug)
        logger.info(args.method)
        method_map[args.method]()
