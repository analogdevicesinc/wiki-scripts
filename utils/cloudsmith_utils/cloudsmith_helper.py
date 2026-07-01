#!/usr/bin/python3

# File name: cloudsmith_helper.py
# Author: Nicu Siderias <nicu.siderias@analog.com>
# Description: Helper script for interacting with the Cloudsmith package repository API.
#              Provides functions to upload, download, copy, delete, and query packages
#              using Cloudsmith's version field as a virtual folder structure.
#              Requires CLOUDSMITH_API_KEY environment variable.

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import PurePosixPath

import requests

########################### Global Vars Instantiation ####################
API_URL = "https://api.cloudsmith.io/v1"

if "CLOUDSMITH_API_KEY" not in os.environ:
    raise SystemError("Cloudsmith_helper: CLOUDSMITH_API_KEY variable is not exported.")

session = requests.Session()
session.headers.update({"X-Api-Key": os.environ["CLOUDSMITH_API_KEY"]})


def configure_logger(enable_logging=False, debug=False):
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


def format_repo(repo):
    """
    Helper function that formats the repository name to include the 'adi/' prefix if missing.

    :param repo: `String` repository name
    :return: `String` formatted repository name
    """
    if not repo.startswith("adi/"):
        return "adi/" + repo
    return repo


def log_on_exit(func):
    def wrapper(*args, **kwargs):
        logger.debug(f"{func.__name__}: ENTERING")
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.debug(f"{func.__name__}: DONE ({elapsed:.2f}s)")
        return result

    return wrapper


logger = logging.getLogger(__name__)
configure_logger()

# Global args variable, will be set when running from command line
args = None


########################### Define Arguments #############################
def set_arguments():
    parser = argparse.ArgumentParser(
        prog="Cloudsmith Helper Script",
        description="This is a helper script for interacting with the Cloudsmith server. "
        "Required environmental variables: CLOUDSMITH_API_KEY.",
        epilog="Common error codes: 400: Bad Request, 401: Unauthorized, 403: Forbidden, 404: Not Found, 422: Unprocess Entity"
        "https://docs.cloudsmith.com/api/error-handling",
    )
    parser.add_argument("--method", help="Method to invoke from this script.")
    parser.add_argument(
        "--package_version",
        help="The version of the package, it is the location where you expect to find the package in a folder structure.",
    )
    parser.add_argument("--package_name", help="The name of the package.")
    parser.add_argument("--package_tags", help="List of tags for a package separated by a `,`.")
    parser.add_argument("--local_path", help="Local path of a package to be uploaded to Cloudsmith.")
    parser.add_argument("--new_package_version", help="New package version used to copy to another location.")
    parser.add_argument("--new_package_name", help="New package name used to copy to another location.")
    parser.add_argument("--new_repo", help="Name of a new repository to copy a package to.")
    parser.add_argument("--repo", help="Name of the Cloudsmith repositories to perform the actions.", required=True)
    parser.add_argument(
        "--keep_folder_structure", action="store_true", help="Recreate folder structure based on package version."
    )
    return parser.parse_args()


########################### Define Helper Methods ########################
_packages_cache = {}


@log_on_exit
def _get_all_packages(query, repo):
    # Cache: strip +name: from query, fetch all packages for that version,
    # then filter locally by name if needed.
    name_filter = None
    version_query = query
    if "+name:" in query:
        version_query, name_filter = query.split("+name:", 1)

    cache_key = (version_query, repo)
    if cache_key in _packages_cache:
        logger.debug(f"Cache hit for {version_query} in {repo}")
        if name_filter:
            return [p for p in _packages_cache[cache_key] if re.search(name_filter, p["name"])]
        return _packages_cache[cache_key]

    page_size = 500
    cloudsmith_repo = format_repo(repo)
    base_url = f"{API_URL}/packages/{cloudsmith_repo}?query={version_query}&page_size={page_size}"

    # First request to get total count
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
            raise SystemError(
                f"Request to the Cloudsmith API failed - {base_url}. Status code: {r.status_code}. Status message: {r.text}"
            )

    packages = json.loads(r.text)

    # Get number of pages from response headers
    total_pages = int(r.headers.get("x-pagination-pagetotal"))

    if total_pages <= 1:
        _packages_cache[cache_key] = packages
        if name_filter:
            return [p for p in packages if re.search(name_filter, p["name"])]
        return packages

    def fetch_page(page):
        """
        Function which fetches packages from one page.
        """
        url = f"{base_url}&page={page}"
        for attempt in range(3):
            resp = session.get(url)
            if resp.ok:
                break
            if resp.status_code == 404 and json.loads(resp.text).get("detail") == "Invalid page.":
                return []
            if attempt < 2:
                time.sleep(2)
                logger.warning(f"Attempt {attempt + 1} failed with status {resp.status_code}, retrying...")
            else:
                raise SystemError(
                    f"Request failed - {url}. Status code: {resp.status_code}. Status message: {resp.text}"
                )
        return json.loads(resp.text)

    # Fetch remaining pages in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_page, page): page for page in range(2, total_pages + 1)}
        for future in as_completed(futures):
            packages.extend(future.result())

    _packages_cache[cache_key] = packages
    if name_filter:
        return [p for p in packages if re.search(name_filter, p["name"])]
    return packages


@log_on_exit
def check_path(package_version=None, package_name=None, repo=None):
    """
    Function which checks if a path exists in Cloudsmith. This is checked using
    the version which specifies where you would expect to find a package if there
    was a folder structure. The version should have a '/' at the end to specify
    a subpath, otherwise the checking is done considering the regex '^version$'

    :param package_version: `String` location to check. Relative URL after REPO.
    :param package_name: `String` Name of the package to check.
    :param repo: `String` Cloudsmith repository name.
    :return: `Boolean` True if the path exists, False otherwise.
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("Cloudsmith_helper: package_version is required to check if a path exists.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("Cloudsmith_helper: repo is required to check if a path exists.")

    if not package_name and args:
        package_name = args.package_name
    if not package_name:
        raise SystemError("Cloudsmith_helper: package_name is required to check if a path exists.")

    package_version = package_version.replace("/", "-")
    url = f"https://dl.cloudsmith.io/basic/adi/{repo}/raw/versions/{package_version}/{package_name}"

    logger.info(f"Checking path existence for version: '{package_version}' and file'{package_name}' in repo: '{repo}'")

    response = session.head(url)
    if response.status_code == 200:
        return True
    logger.info(f"Response status code: {response.status_code} for URL: {url}.")
    return False


@log_on_exit
def get_subfolders(package_version=None, repo=None):
    """
    Function which gets the list of subfolders from Cloudsmith, using `package_version`
    as a theoretical path.

    :param package_version: `String` version representing the theoretical path of files.
    :param repo: `String` Cloudsmith repository name.
    :return: `List` full list of subfolders from the given location.
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("Cloudsmith_helper: package_version is required to get subfolders.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("Cloudsmith_helper: repo is required to get subfolders.")

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


@log_on_exit
def get_files(package_version=None, repo=None):
    """
    Function which gets the list of files from Cloudsmith, with the version
    `package_version` representing the theoretical path of the files.

    :param package_version: `String` theoretical location of the files.
    :param repo: `String` Cloudsmith repository name.
    :return: `List` full list of files from the specified location.
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("Cloudsmith_helper: package_version is required to get files.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("Cloudsmith_helper: repo is required to get files.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("$"):
        package_version += "$"

    logger.info(f"Getting files for version: '{package_version}' in repo: '{repo}'")

    packages = _get_all_packages(f"version:{package_version}", repo)
    files = sorted(list(package["filename"] for package in packages))
    logger.info("Files: " + str(files))

    return files


@log_on_exit
def get_folder_structure(package_version=None, repo=None):
    """
    Function which returns the folder structure present in Cloudsmith, based
    on `package_version`

    :param package_version: `String` location to get folder structure for
    :param repo: `String` Cloudsmith repository name.
    :return: `List` list of files at the given location (with relative paths)
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("Cloudsmith_helper: package_version is required to get folder structure.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("Cloudsmith_helper: repo is required to get folder structure.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("/"):
        package_version += "/"

    logger.info(f"Getting folder structure for version: '{package_version}' in repo: '{repo}'")

    packages = _get_all_packages(f"version:{package_version}", repo)

    folders = sorted(list(set(package["version"][len(package_version) - 1 :] for package in packages)))
    logger.info("Subfolders: " + str(folders))

    return folders


@log_on_exit
def get_folder_and_files_structure(package_version=None, repo=None):
    """
    Function which returns the folder and files structure present in Cloudsmith, based
    on `package_version`

    :param package_version: `String` location to get folder structure for
    :param repo: `String` Cloudsmith repository name.
    :return: `Dict<String, List<String>>` dictionary with folder paths as keys and list of files as values
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("Cloudsmith_helper: package_version is required to get folder structure.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("Cloudsmith_helper: repo is required to get folder structure.")

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


@log_on_exit
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
    Function which copies all packages from Cloudsmith, with a specific `package_version`
    to another location with a different `new_package_version`. The copying is done
    by downloading the packages locally first, then uploading with the `new_package_version`
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
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("Cloudsmith_helper: package_version is required to copy a package.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("Cloudsmith_helper: repo is required to copy a package.")

    # Optional parameters - use args as fallback if parameter not provided
    if not package_name and args:
        package_name = args.package_name
    if not new_package_version and args:
        new_package_version = args.new_package_version
    if not new_package_version:
        new_package_version = package_version
    if not new_package_name and args:
        new_package_name = args.new_package_name
    if not new_repo and args:
        new_repo = args.new_repo
    if not new_repo:
        new_repo = repo
    if not package_tags and args:
        package_tags = args.package_tags

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"

    if package_version.endswith("/") and not package_name and not new_package_version.endswith("/"):
        raise SystemError(
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


@log_on_exit
def remove_item_from_location(package_version=None, package_name=None, repo=None):
    """
    Function which removes a package from Cloudsmith, with the specified version
    and/or `package_name`. Can be either a file or a directory.

    At least one of `package_version` or `package_name` must be provided.
    Use "*" for either parameter to match all versions or names respectively.

    :param package_version: `String` version(location) of the package to be removed. Use "*" to match all versions.
    :param package_name: `String` name of the package to be removed. Use "*" to match all names.
    :param repo: `String` Cloudsmith repository name.
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("Cloudsmith_helper: repo is required to remove an item.")

    # Optional parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_name and args:
        package_name = args.package_name

    # At least one of package_version or package_name must be provided to prevent accidental deletion of all packages
    if not package_version and not package_name:
        raise SystemError(
            "Cloudsmith_helper: At least one of package_version or package_name must be provided to remove items. "
            "Use '*' to explicitly match all."
        )

    # Build query based on provided parameters
    query = ""
    if package_version and package_version != "*":
        query += f"version:{package_version}"
    if package_name and package_name != "*":
        query += "+" if query else ""
        query += f"name:{package_name}"

    cloudsmith_repo = format_repo(repo)
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
            r = session.delete(url)
            if r.ok:
                break
            if attempt < 2:
                time.sleep(2)
                logger.warning(f"Attempt {attempt + 1} failed with status {r.status_code}, retrying...")
            else:
                raise SystemError(f"Request to the Cloudsmith API failed - DELETE {url} returned {r.status_code}")
        logger.info(f"Package {package['name']} with identifier {package['identifier_perm']} was deleted")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(delete_package, package): package for package in packages}
        for future in as_completed(futures):
            future.result()


@log_on_exit
def get_artifacts_from_location(package_version=None, package_name=None, keep_folder_structure=False, repo=None):
    """
    Function which downloads artifacts from Cloudsmith, that match the `package_version`.
    The `keep_folder_structure` can be recreated based on the `package_version`.

    :param package_version: `String` version(location) of the package(s) to be downloaded.
    :param package_name: `String` name of the package to download. If missing, all packages matching the version will be downloaded.
    :param keep_folder_structure: `Bool` specify if the folder structure should be recreated. Defaults to False.
    :param repo: `String` Cloudsmith repository name.
    :return: `List` of the packages that were downloaded.
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("Cloudsmith_helper: package_version is required to get artifacts.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("Cloudsmith_helper: repo is required to get artifacts.")

    # Optional parameters - use args as fallback if parameter not provided
    if not package_name and args:
        package_name = args.package_name

    if not keep_folder_structure and args:
        keep_folder_structure = args.keep_folder_structure

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"

    query = f"version:{package_version}"
    if package_name:
        query += f"+name:{package_name}"

    packages = _get_all_packages(query, repo)

    for package in packages:
        response = session.get(package["cdn_url"])
        if response.status_code != 200:
            raise SystemError(
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


@log_on_exit
def deploy_to_location(local_path=None, package_version=None, package_tags=None, repo=None):
    """
    Function which uploads a package to Cloudsmith, from the given `local_path` to the given repository with
    a corresponding `package_version`. It requires the `cloudsmith-cli` tool to be installed. This can be done
    via `pip` - `python -m pip install cloudsmith-cli`

    :param local_path: `String` relative (or absolute) path to the package to be uploaded to Cloudsmith.
    :param package_version: `String` package version representing the path where you would like to find the package
                            if there would've been a folder structure. Required.
    :param package_tags: `String` tags to be assigned to the package, separated by a `,`.
    :param repo: `String` Cloudsmith repository name.
    """

    # Mandatory parameters - use args as fallback if parameter not provided
    if not local_path and args:
        local_path = args.local_path
    if not local_path:
        raise SystemError("Cloudsmith_helper: local_path is required to deploy a package.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("Cloudsmith_helper: repo is required to deploy a package.")

    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("Cloudsmith_helper: package_version is required to deploy a package.")

    if not package_tags and args:
        package_tags = args.package_tags

    cloudsmith_repo = format_repo(repo)
    cmd = [
        "cloudsmith",
        "push",
        "raw",
        "-SW",
        "--republish",
        cloudsmith_repo,
        local_path,
        "-k",
        os.environ["CLOUDSMITH_API_KEY"],
    ]

    cmd.extend(["--version", package_version])
    if package_tags:
        cmd.extend(["--tags", package_tags])

    output = subprocess.run(cmd, capture_output=True)
    if output.returncode == 0:
        logger.info(
            f"Package successfully uploaded package:{local_path} version:{package_version} package_tags:{package_tags}"
        )
    else:
        # Remove -k and API key from command for safe logging
        cmd_safe = [arg for i, arg in enumerate(cmd) if arg != "-k" and (i == 0 or cmd[i - 1] != "-k")]
        raise SystemError(
            f"cmd: {cmd_safe} failed with exit code {output.returncode}! stderr: {output.stderr.decode('utf-8')} stdout: {output.stdout.decode('utf-8')}"
        )


@log_on_exit
def get_item_properties(package_version=None, package_name=None, repo=None):
    """
    Function which gets the tags of a Cloudsmith package.

    :param package_version: `String` version of the package representing the theoretical location. Optional.
    :param package_name: `String` the name of the Cloudsmith package to retrieve tags from. Properties for folders do not exist.
    :param repo: `String` Cloudsmith repository name.
    :return: `List` the tags for the given file
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_name and args:
        package_name = args.package_name
    if not package_name:
        raise SystemError("Cloudsmith_helper: package_name is required to get item properties.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("Cloudsmith_helper: repo is required to get item properties.")

    # Optional parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version

    query = ""
    if package_version:
        query += f"version:{package_version}+"
    query += f"name:{package_name}"

    packages = _get_all_packages(query, repo)
    if not len(packages):
        raise SystemError(
            f"No package was found with the given parameters: version:{package_version} name:{package_name}!"
        )
    if len(packages) > 1:
        raise SystemError(
            f"Multiple packages found with the given parameters: version:{package_version} name:{package_name}!"
        )

    logger.info(
        f"Tags for package with version: '{package_version}' and name: '{package_name}' in repo: '{repo}': {packages[0]['tags']['info']}"
    )

    return packages[0]["tags"]["info"]


@log_on_exit
def get_item_properties_as_dict(package_version=None, package_name=None, repo=None):
    """
    Function which gets the tags of a Cloudsmith package and return it as dictionary.
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


@log_on_exit
def get_sha256_for_file(package_version=None, package_name=None, repo=None):
    """
    Function which gets the sha256 of a Cloudsmith package.

    :param package_version: `String` version of the package representing the theoretical location.
    :param package_name: `String` the name of the Cloudsmith package to retrieve tags from.
    :param repo: `String` Cloudsmith repository name.
    :return: `String` sha256 hash of the package
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_name and args:
        package_name = args.package_name
    if not package_name:
        raise SystemError("Cloudsmith_helper: package_name is required to get item sha.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("Cloudsmith_helper: repo is required to get item sha.")

    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("Cloudsmith_helper: package_version is required to get item sha.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("$"):
        package_version += "$"

    query = f"version:{package_version}+name:{package_name}"

    packages = _get_all_packages(query, repo)
    if not len(packages):
        raise SystemError(
            f"Cloudsmith_helper: No package was found with the given parameters: version:{package_version} name:{package_name}!"
        )
    if len(packages) > 1:
        raise SystemError(
            f"Cloudsmith_helper: Multiple packages found with the given parameters: version:{package_version} name:{package_name}!"
        )

    return packages[0]["checksum_sha256"]


if __name__ == "__main__":
    args = set_arguments()

    if not args:
        raise SystemError("Cloudsmith_helper: Arguments failed to parse or are missing, try using `-h`")

    if args.method is None:
        # Set pager to cat so that scrolling is not enabled
        os.environ["PAGER"] = "cat"
        logger.warning("Method argument is missing!")
        help(check_path)
        help(get_subfolders)
        help(get_files)
        help(get_folder_structure)
        help(get_folder_and_files_structure)
        help(copy_to_location)
        help(remove_item_from_location)
        help(get_artifacts_from_location)
        help(deploy_to_location)
        help(get_item_properties)
        help(get_item_properties_as_dict)
        help(get_sha256_for_file)
    else:
        try:
            logger.info(args.method)
            method = globals()[args.method]
        except Exception:
            raise SystemError("Cloudsmith_helper: Method not found: " + args.method)
        method()
