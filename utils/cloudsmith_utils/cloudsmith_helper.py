#!/usr/bin/python3
import argparse
import io
import json
import logging
import os
from pathlib import PurePosixPath
import requests
import subprocess
import sys
import tarfile
import zipfile

########################### Global Vars Instantiation ####################
API_URL = "https://api.cloudsmith.io/v1"

if "CLOUDSMITH_API_KEY" not in os.environ:
    raise SystemError("CLOUDSMITH_API_KEY variable is not exported.")


def configure_logger(enable_logging=False):
    logger.setLevel(logging.INFO)

    if logger.handlers:
        logger.handlers.clear()

    if __name__ == "__main__" or enable_logging:
        handler = logging.StreamHandler(sys.stdout)
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


logger = logging.getLogger(__name__)
configure_logger()

# Global args variable, will be set when running from command line
args = None


########################### Define Arguments #############################
def set_arguments():
    parser = argparse.ArgumentParser(
        prog="Cloudsmith Helper Script",
        description="This is a helper script for interacting with the Cloudsmith server. "
                    "Required environmental variables: CLOUDSMITH_REPO, CLOUDSMITH_API_KEY.",
        epilog="Common error codes: 400: Bad Request, 401: Unauthorized, 403: Forbidden, 404: Not Found, 422: Unprocess Entity"
               "https://docs.cloudsmith.com/api/error-handling")
    parser.add_argument('--method', help="Method to invoke from this script.")
    parser.add_argument('--package_version', help="The version of the package, it is the location where you expect to find the package in a folder structure.")
    parser.add_argument('--package_name', help="The name of the package.")
    parser.add_argument('--package_tags', help="List of tags for a package separated by a `,`.")
    parser.add_argument('--local_path', help="Local path of a package to be uploaded to Cloudsmith.")
    parser.add_argument('--new_package_version', help="New package version used to copy to another location.")
    parser.add_argument('--new_repo', help="Name of a new repository to copy a package to.")
    parser.add_argument('--repo', help="Name of the Cloudsmith repositories to perform the actions.", required=True)
    return parser.parse_args()


########################### Define Helper Methods ########################
def _get_all_packages(query, repo):
    """
    Function that uses the `query` parameter to get a list of packages
    from Cloudsmith

    :param query: `String` Cloudsmith api query parameter
    :param repo: `String` Cloudsmith repository name
    :return: `List` of packages
    """
    page = 1
    page_size = 50
    data_count = 50
    packages = []
    cloudsmith_repo = format_repo(repo)

    while data_count == page_size:
        url = f"{API_URL}/packages/{cloudsmith_repo}?query={query}&page={page}&page_size={page_size}"
        r = requests.get(url, headers={"X-Api-Key": os.environ["CLOUDSMITH_API_KEY"]})

        # Handle "Invalid page" error when there are no more pages (e.g., exactly 50 items)
        if r.status_code == 404:
            response_data = json.loads(r.text)
            if response_data.get("detail") == "Invalid page.":
                break
            raise SystemError(f"Request to the Cloudsmith API failed - {url}. Response: {r.text}")

        if not r.ok:
            raise SystemError(f"Request to the Cloudsmith API failed - {url}. Status code: {r.status_code}")

        p = json.loads(r.text)
        data_count = len(p)
        packages.extend(p)
        page += 1

    return packages


def check_path(package_version=None, repo=None):
    """
    Function which checks if a path exists in Cloudsmith. This is checked using
    the version which specifies where you would expect to find a package if there
    was a folder structure. The version should have a '/' at the end to specify
    a subpath, otherwise the checking is done considering the regex '^version$'

    :param package_version: `String` location to check. Relative URL after REPO.
    :param repo: `String` Cloudsmith repository name.
    :return: `Boolean` True if the path exists, False otherwise.
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("package_version is required to check if a path exists.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("repo is required to check if a path exists.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("/"):
        package_version += "$"

    logger.info(f"Checking path existence for version: '{package_version}' in repo: '{repo}'")

    packages = _get_all_packages(f"version:{package_version}", repo)

    if not packages:
        logger.info("Path does not exist")
        return False

    logger.info("Path exists")
    return True


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
        raise SystemError("package_version is required to get subfolders.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("repo is required to get subfolders.")

    logger.info(f"Getting subfolders for version: '{package_version}' in repo: '{repo}'")

    enhance_package_version = package_version
    if not package_version.startswith("^"):
        enhance_package_version = f"^{package_version}"
    if not package_version.endswith("/"):
        enhance_package_version += "/"

    packages = _get_all_packages(f"version:{enhance_package_version}", repo)

    folders = list(set(p.parts[0] for package in packages if (p := PurePosixPath(package["version"]).relative_to(package_version)).parts))
    logger.info("Subfolders: " + str(folders))

    return folders


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
        raise SystemError("package_version is required to get files.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("repo is required to get files.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("$"):
        package_version += "$"

    logger.info(f"Getting files for version: '{package_version}' in repo: '{repo}'")

    packages = _get_all_packages(f"version:{package_version}", repo)
    files = list(package["filename"] for package in packages)
    logger.info("Files: " + str(files))

    return files


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
        raise SystemError("package_version is required to get folder structure.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("repo is required to get folder structure.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("/"):
        package_version += "/"

    logger.info(f"Getting folder structure for version: '{package_version}' in repo: '{repo}'")

    packages = _get_all_packages(f"version:{package_version}", repo)

    folders = list(set(package["version"][len(package_version) - 1:] for package in packages))
    logger.info("Subfolders: " + str(folders))

    return folders


def get_folder_and_files_structure(package_version=None, repo=None):
    """
    Function which returns the folder and files structure present in Cloudsmith, based
    on `package_version`

    :param package_version: `String` location to get folder structure for
    :param repo: `String` Cloudsmith repository name.
    :return: `List` list of files at the given location (with relative paths)
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("package_version is required to get folder structure.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("repo is required to get folder structure.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("/"):
        package_version += "/"

    logger.info(f"Getting folde and files structure for version: '{package_version}' in repo: '{repo}'")

    packages = _get_all_packages(f"version:{package_version}", repo)

    folders_and_files = {}
    for package in packages:
        relative_path = package["version"][len(package_version) - 1:]
        if relative_path not in folders_and_files:
            folders_and_files[relative_path] = []
        folders_and_files[relative_path].append(package["filename"])

    logger.info("Subfolders and files: " + str(folders_and_files))

    return folders_and_files


def copy_to_location(package_version=None, package_name=None, new_package_version=None, new_repo=None, package_tags=None, repo=None):
    """
    Function which copies all packages from Cloudsmith, with a specific `package_version`
    to another location with a different `new_package_version`. The copying is done
    by downloading the packages locally first, then uploading with the `new_package_version`
    to a `new_repo` or the same repository.

    :param package_version: `String` version representing theoretical path of the packages.
    :param package_name: `String` name of the package to download. Copy all files if this is missing.
    :param new_package_version: `String` new version representing the new theoretical path to upload
                          the packages to. If missing, keep the same version.
    :param new_repo: `String` new repository where to upload to. If missing, use the same repo.
    :param package_tags: `String` tags for the package(s) split by ','. If missing, inherit the
                   tags from the original package.
    :param repo: `String` Cloudsmith repository name.
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("package_version is required to copy a package.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("repo is required to copy a package.")

    if not new_package_version and args:
        new_package_version = args.new_package_version
    if not new_package_version:
        new_package_version = package_version

    # Optional parameters - use args as fallback if parameter not provided
    if not package_name and args:
        package_name = args.package_name
    if not new_repo and args:
        new_repo = args.new_repo
    if not new_repo:
        new_repo = repo
    if not package_tags and args:
        package_tags = args.package_tags

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"

    if package_version.endswith("/") and not package_name and not new_package_version.endswith("/"):
        raise SystemError("If the source package_version is a folder (ends with '/'), the new_package_version must also be a folder (end with '/').")

    logger.info(f"Copying packages from version: '{package_version}' in repo: '{repo}' to version: '{new_package_version}' in repo: '{new_repo}'")

    # Download packages
    packages = get_artifacts_from_location(package_version, package_name, repo=repo)

    for package in packages:
        if not package_tags:
            package_tags = ','.join(package['tags']['info'])

        package_name = package['name']
        if not new_package_version.endswith("/"):
            package_name = new_package_version.split("/")[-1]
            new_package_version = new_package_version.rsplit("/", 1)[0] + "/"
            os.rename(package['name'], package_name)

        logger.info(f"Copy package: '{package_name}({package['name']})' with version: '{new_package_version}' in repo: '{new_repo}' with tags: '{package_tags}'")
        deploy_to_location(package_name, new_package_version, package_tags, repo=new_repo)
        # delete local files
        command = ["rm", package_name]
        subprocess.run(command, check=True)


def remove_item_from_location(package_version=None, package_name=None, repo=None):
    """
    Function which removes a package from Cloudsmith, with the specified version
    and/or `package_name`. Can be either a file or a directory.

    :param package_version: `String` version(location) of the package to be removed. Optional.
    :param package_name: `String` name of the package to be removed. Optional.
    :param repo: `String` Cloudsmith repository name.
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("repo is required to remove an item.")

    # Optional parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_name and args:
        package_name = args.package_name

    # Build query based on provided parameters
    query = ""
    if package_version:
        query += f"version:{package_version}"
    if package_name:
        query += "+" if query else ""
        query += f"name:{package_name}"

    cloudsmith_repo = format_repo(repo)
    logger.info(f"Package(s) {(f'with name {package_name}' if package_name else '')} {(f'with version {package_version}' if package_version else '')} from repo {cloudsmith_repo} will be deleted")
    packages = _get_all_packages(query, repo)
    if not packages:
        logger.info("No packages found to delete.")
        return
    for package in packages:
        logger.info(f"Deleting package {package['name']} with identifier {package['identifier_perm']}")
        url = f"{API_URL}/packages/{cloudsmith_repo}/{package['identifier_perm']}"
        for attempt in range(3):
            r = requests.delete(url, headers={"X-Api-Key": os.environ["CLOUDSMITH_API_KEY"]})
            if r.ok:
                break
            if attempt < 2:
                logger.warning(f"Attempt {attempt + 1} failed with status {r.status_code}, retrying...")
            else:
                raise SystemError(f"Request to the Cloudsmith API failed - DELETE {url} returned {r.status_code}")
        logger.info(f"Package {package['name']} with identifier {package['identifier_perm']} was deleted")


def get_artifacts_from_location(package_version=None, package_name=None, folder_structure=False, repo=None):
    """
    Function which downloads artifacts from Cloudsmith, that match the `package_version`.
    The `folder_structure` can be recreated based on the `package_version`.

    :param package_version: `String` version(location) of the package(s) to be downloaded.
    :param package_name: `String` name of the package to download. If missing, all packages matching the version will be downloaded.
    :param folder_structure: `Bool` specify if the folder structure should be recreated. Defaults to False.
    :param repo: `String` Cloudsmith repository name.
    :return: `List` of the packages that were downloaded.
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("package_version is required to get artifacts.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("repo is required to get artifacts.")

    # Optional parameters - use args as fallback if parameter not provided
    if not package_name and args:
        package_name = args.package_name

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"

    query = f"version:{package_version}"
    if package_name:
        query += f"+name:{package_name}"

    packages = _get_all_packages(query, repo)

    for package in packages:
        arguments = ["curl", "-H", f"X-Api-Key: {os.environ['CLOUDSMITH_API_KEY']}", "-1LfO", package['cdn_url']]
        result = subprocess.run(arguments, capture_output=True)
        if result.returncode != 0:
            # Remove API key from arguments for safe logging
            args_safe = [arg for i, arg in enumerate(arguments) if i != 2]
            raise SystemError(f"curl command failed with exit code {result.returncode}: {args_safe}")
        if folder_structure:
            arguments = ["mkdir", "-p", package['version']]
            subprocess.run(arguments, check=True)
            arguments = ["mv", package['name'], package['version']]
            subprocess.run(arguments, check=True)
    logger.info(f"{len(packages)} packages with version {package_version} have been downloaded")
    return packages


def extract_file_from_archive(package_version=None, package_name=None, target_file=None, output_path=None, repo=None):
    """
    Extracts a specific file from a tar.gz or zip archive on Cloudsmith without
    downloading the entire archive to disk. The archive is streamed into memory
    and only the requested file is extracted.

    :param package_version: `String` version(location) of the archive package.
    :param package_name: `String` name of the archive (e.g., 'mypackage.tar.gz' or 'mypackage.zip').
    :param target_file: `String` path of the file inside the archive to extract.
    :param output_path: `String` optional path to save the extracted file. If a directory,
                        the filename from target_file will be used. If None, returns content as bytes.
    :param repo: `String` Cloudsmith repository name.
    :return: `bytes` content of the extracted file if output_path is None, otherwise None.
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("package_version is required to extract file from archive.")

    if not package_name and args:
        package_name = args.package_name
    if not package_name:
        raise SystemError("package_name is required to extract file from archive.")

    if not target_file:
        raise SystemError("target_file is required to extract file from archive.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("repo is required to extract file from archive.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("$"):
        package_version += "$"

    query = f"version:{package_version}+name:{package_name}"
    packages = _get_all_packages(query, repo)

    if not packages:
        raise SystemError(f"Package not found: {package_name} at version {package_version}")

    package = packages[0]
    logger.info(f"Streaming archive from: {package['cdn_url']}")

    response = requests.get(
        package['cdn_url'],
        headers={"X-Api-Key": os.environ["CLOUDSMITH_API_KEY"]},
        stream=True
    )
    response.raise_for_status()

    file_obj = io.BytesIO(response.content)

    # Extract based on archive type
    if package_name.endswith('.tar.gz') or package_name.endswith('.tgz'):
        with tarfile.open(fileobj=file_obj, mode='r:gz') as tf:
            try:
                member = tf.getmember(target_file)
                extracted = tf.extractfile(member)
                if extracted:
                    content = extracted.read()
                else:
                    raise SystemError(f"Could not extract file (may be a directory): {target_file}")
            except KeyError:
                raise SystemError(f"File not found in archive: {target_file}")
    elif package_name.endswith('.zip'):
        with zipfile.ZipFile(file_obj, 'r') as zf:
            try:
                content = zf.read(target_file)
            except KeyError:
                raise SystemError(f"File not found in archive: {target_file}")
    else:
        raise SystemError(f"Unsupported archive format: {package_name}. Supported: .tar.gz, .tgz, .zip")

    logger.info(f"Extracted '{target_file}' ({len(content)} bytes) from {package_name}")

    if output_path:
        if os.path.isdir(output_path):
            output_path = os.path.join(output_path, os.path.basename(target_file))
        with open(output_path, 'wb') as f:
            f.write(content)
        logger.info(f"Saved to: {output_path}")
        return None

    return content


def list_archive_contents(package_version=None, package_name=None, repo=None):
    """
    Lists the contents of a tar.gz or zip archive on Cloudsmith without
    downloading the entire archive to disk.

    :param package_version: `String` version(location) of the archive package.
    :param package_name: `String` name of the archive (e.g., 'mypackage.tar.gz' or 'mypackage.zip').
    :param repo: `String` Cloudsmith repository name.
    :return: `List` of tuples (filename, size) for each file in the archive.
    """
    # Mandatory parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version
    if not package_version:
        raise SystemError("package_version is required to list archive contents.")

    if not package_name and args:
        package_name = args.package_name
    if not package_name:
        raise SystemError("package_name is required to list archive contents.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("repo is required to list archive contents.")

    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("$"):
        package_version += "$"

    query = f"version:{package_version}+name:{package_name}"
    packages = _get_all_packages(query, repo)

    if not packages:
        raise SystemError(f"Package not found: {package_name} at version {package_version}")

    package = packages[0]
    logger.info(f"Streaming archive from: {package['cdn_url']}")

    response = requests.get(
        package['cdn_url'],
        headers={"X-Api-Key": os.environ["CLOUDSMITH_API_KEY"]},
        stream=True
    )
    response.raise_for_status()

    file_obj = io.BytesIO(response.content)
    contents = []

    if package_name.endswith('.tar.gz') or package_name.endswith('.tgz'):
        with tarfile.open(fileobj=file_obj, mode='r:gz') as tf:
            for member in tf.getmembers():
                if not member.isdir():
                    contents.append((member.name, member.size))
    elif package_name.endswith('.zip'):
        with zipfile.ZipFile(file_obj, 'r') as zf:
            for info in zf.infolist():
                if not info.is_dir():
                    contents.append((info.filename, info.file_size))
    else:
        raise SystemError(f"Unsupported archive format: {package_name}. Supported: .tar.gz, .tgz, .zip")

    logger.info(f"Found {len(contents)} files in {package_name}")
    return contents


def deploy_to_location(local_path=None, package_version=None, package_tags=None, repo=None):
    """
    Function which uploads a package to Cloudsmith, from the given `local_path` to the given repository with
    a corresponding `package_version`. It requires the `cloudsmith-cli` tool to be installed. This can be done
    via `pip` - `python -m pip install cloudsmith-cli`

    :param local_path: `String` relative (or absolute) path to the package to be uploaded to Cloudsmith.
    :param package_version: `String` package version representing the path where you would like to find the package
                            if there would've been a folder structure. It defaults to `local_path` without the name itself.
    :param package_tags: `String` tags to be assigned to the package, separated by a `,`.
    :param repo: `String` Cloudsmith repository name.
    """

    # Mandatory parameters - use args as fallback if parameter not provided
    if not local_path and args:
        local_path = args.local_path
    if not local_path:
        raise SystemError("local_path is required to deploy a package.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("repo is required to deploy a package.")

    if not package_version and args:
        package_version = args.package_version
    if not package_tags and args:
        package_tags = args.package_tags

    if not package_version:
        package_version = '/'.join(local_path.split("/")[:-1])

    cloudsmith_repo = format_repo(repo)
    cmd = ["cloudsmith", "push", "raw", "-SW", "--republish", cloudsmith_repo, local_path, "-k", os.environ["CLOUDSMITH_API_KEY"]]

    if package_version:
        cmd.extend(["--version", package_version])
    if package_tags:
        cmd.extend(["--tags", package_tags])

    output = subprocess.run(cmd, capture_output=True)
    if output.returncode == 0:
        logger.info(f"Package successfully uploaded package:{local_path} version:{package_version} package_tags:{package_tags}")
    else:
        # Remove -k and API key from command for safe logging
        cmd_safe = [arg for i, arg in enumerate(cmd) if arg != "-k" and (i == 0 or cmd[i - 1] != "-k")]
        raise SystemError(f"cmd: {cmd_safe} failed with exit code {output.returncode}!")


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
        raise SystemError("package_name is required to get item properties.")

    if not repo and args:
        repo = args.repo
    if not repo:
        raise SystemError("repo is required to get item properties.")

    # Optional parameters - use args as fallback if parameter not provided
    if not package_version and args:
        package_version = args.package_version

    query = ""
    if package_version:
        query += f"version:{package_version}+"
    query += f"name:{package_name}"

    packages = _get_all_packages(query, repo)
    if not len(packages):
        raise SystemError(f"No package was found with the given parameters: version:{package_version} name:{package_name}!")
    if len(packages) > 1:
        raise SystemError(f"Multiple packages found with the given parameters: version:{package_version} name:{package_name}!")

    return packages[0]['tags']['info']


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
        if '-' in tag:
            key, value = tag.split('-', 1)
            if key in tags_dict:
                tags_dict[key].append(value)
            else:
                tags_dict[key] = [value]
        else:
            tags_dict[tag] = None
    return tags_dict


if __name__ == "__main__":
    args = set_arguments()

    if not args:
        raise SystemError("Arguments failed to parse or are missing, try using `-h`")

    if args.method is None:
        # Set pager to cat so that scrolling is not enabled
        os.environ['PAGER'] = 'cat'
        logger.info("\nWARNING: Method argument is missing!")
        help(check_path)
        help(get_subfolders)
        help(get_files)
        help(get_folder_structure)
        help(get_folder_and_files_structure)
        help(copy_to_location)
        help(remove_item_from_location)
        help(get_artifacts_from_location)
        help(extract_file_from_archive)
        help(list_archive_contents)
        help(deploy_to_location)
        help(get_item_properties)
        help(get_item_properties_as_dict)
    else:
        try:
            logger.info(args.method)
            method = globals()[args.method]
        except Exception:
            raise SystemError("Method not found: " + args.method)
        method()