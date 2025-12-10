#!/usr/bin/python3
import argparse
import json
import logging
import os
import subprocess
import sys

import requests

########################### Global Vars Instantiation ####################
API_URL = "https://api.cloudsmith.io/v1"
CLOUDSMITH_REPO = None

if "CLOUDSMITH_API_KEY" not in os.environ:
    raise SystemError("CLOUDSMITH_API_KEY variable is not exported.")

logger = logging.getLogger(__name__)

########################### Define Arguments #############################
def set_arguments():
    parser = argparse.ArgumentParser(
        prog="Cloudsmith Helper Script",
        description="This is a helper script for interacting with the Cloudsmith server. " +\
                    "Required environmental variables: CLOUDSMITH_REPO, CLOUDSMITH_API_KEY.",
        epilog="Common error codes: 400: Bad Request, 401: Unauthorized, 403: Forbidden, 404: Not Found, 422: Unprocess Entity" +\
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

def get_all_packages(query):
    """
    Function that uses the `query` parameter to get a list of packages
    from Cloudsmith

    :param query: `String` Cloudsmith api query parameter
    :return: `List` of packages
    """
    page = 1
    page_size = 50
    data_count = 50
    packages = []

    while data_count == page_size:
        url = f"{API_URL}/packages/{CLOUDSMITH_REPO}?query={query}&page={page}&page_size={page_size}"
        r = requests.get(url, headers={"X-Api-Key": os.environ["CLOUDSMITH_API_KEY"]})
        if not r.ok:
            raise SystemError(f"Request to the Cloudsmith API failed - {url}.")

        p = json.loads(r.text)
        data_count = len(p)
        packages.extend(p)
        page += 1

    return packages

def set_cloudsmith_repo(repo):
    global CLOUDSMITH_REPO
    CLOUDSMITH_REPO = repo
    if not CLOUDSMITH_REPO.startswith("adi/"):
        CLOUDSMITH_REPO = "adi/" + CLOUDSMITH_REPO

def configure_logger():
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return

    if __name__ == "__main__":
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.FileHandler(os.devnull)

    logger.addHandler(handler)

configure_logger()

########################### Define Helper Methods ########################
def check_path(package_version=None):
    """
    Function which checks if a path exists in Cloudsmith. This is checked using
    the version which specifies where you would expect to find a package if there
    was a folder structure. The version should have a '/' at the end to specify
    a subpath, otherwise the checking is done considering the regex '^version$'

    :param package_version: `String` location to check. Relative URL after REPO.
    :return: `Boolean` True if the path exists, False otherwise.
    """
    if not package_version and not args.package_version:
        raise SystemError("--package_version is required to check if a path exists")

    if not package_version:
        package_version = args.package_version
    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("/"):
        package_version += "$"

    packages = get_all_packages(f"version:{package_version}")

    if not packages:
        logger.info("Path does not exist")
        return False

    logger.info("Path exists")
    return True

def get_subfolders(package_version=None):
    """
    Function which gets the list of subfolders from Cloudsmith, using `package_version`
    as a theoretical path.

    :param package_version: `String` version representing the theoretical path of files.
    :return: `List` full list of subfolders from the given location.
    """

    if not package_version and not args.package_version:
        raise SystemError("--package_version is required to check if a path exists")

    if not package_version:
        package_version = args.package_version
    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("/"):
        package_version += "/"

    packages = get_all_packages(f"version:{package_version}")

    folders = list(set(package["version"][len(package_version)-1:].split("/")[0] for package in packages))
    logger.info(folders)

    return folders

def get_files(package_version=None):
    """
    Function which gets the list of files from Cloudsmith, with the version
    `package_version` representing the theoretical path of the files.

    :param package_version: `String` theoretical location of the files.
    :return: `List` full list of files from the specified location.
    """

    if not package_version and not args.package_version:
        raise SystemError("--package_version is required to check if a path exists")

    if not package_version:
        package_version = args.package_version
    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("$"):
        package_version += "$"

    packages = get_all_packages(f"version:{package_version}")
    files = list(package["filename"] for package in packages)
    logger.info(files)

    return files

def get_folder_structure(package_version=None):
    """
    Function which returns the folder structure present in Cloudsmith, based
    on `package_version`

    :param package_version: `String` location to get folder structure for
    :return: `List` list of files at the given location (with relative paths)
    """

    if not package_version and not args.package_version:
        raise SystemError("--package_version is required to check if a path exists")

    if not package_version:
        package_version = args.package_version
    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_version.endswith("/"):
        package_version += "/"

    packages = get_all_packages(f"version:{package_version}")

    folders = list(set(package["version"][len(package_version)-1:] for package in packages))
    logger.info(folders)

    return folders

def copy_to_location(package_version=None, package_name=None, new_package_version=None, new_repo=None, package_tags=None):
    """
    Function which copies all packages from Cloudsmith, with a specific `package_version`
    to another location with a different `new_package_version`. The copying is done
    by downloading the packages locally first, then uploading with the `new_package_version`
    to a `new_repo` or the same repository.

    :param package_version: `String` version representing theoretical path of the packages.
    :param package_name: `String` name of the package to downoad. Copy all files if this is missing.
    :param new_package_version: `String` new version representing the new theoretical path to upload
                          the packages to. If missing, keep the same version.
    :param new_repo: `String` new repository where to upload to. If missing, use the same repo.
    :param package_tags: `String` tags for the package(s) split by ','. If missing, inherit the
                   tags from the original package.
    """
    if not package_version and not args.package_version:
        raise SystemError("--package_version is required to copy a package.")
    if not new_package_version and not args.new_package_version:
        raise SystemError("--new_package_version is required to copy a package.")

    if not package_version:
        package_version = args.package_version
    if not package_version.startswith("^"):
        package_version = f"^{package_version}"
    if not package_name:
        package_name = args.package_name
    if not new_package_version:
        new_package_version = args.new_package_version
    if not new_package_version:
        new_package_version = package_version
    if not package_tags:
        package_tags = args.package_tags

    # Download packages
    packages = get_artifacts_from_location(package_version, package_name)

    # Upload packages
    if new_repo:
        set_cloudsmith_repo(new_repo)

    for package in packages:
        if not package_tags:
            package_tags = ','.join(package['tags']['info'])
        deploy_to_location(package['name'], new_package_version, package_tags)
        # delete local files
        command = ["rm", package['name']]
        subprocess.run(command, check=True)

def create_item_to_location(package_version=None, package_name="dummy.txt"):
    """
    Functions which creates a `package_name` dummy file containing the string "Hello", which
    gets uploaded to Cloudsmith with the specified `package_version` representing a theoretical
    path.

    :param package_version: `String` theoretical path where to create the file.
    :param package_name: `String` name of the dummy file. Defaults to "dummy.txt".
    """
    if not package_version:
        package_version = args.package_version
    if args.package_name:
        package_name = args.package_name

    if package_version.endswith("/"):
        package_version = package_version[:-1]
    else:
        v = package_version.split("/")
        package_name = v[-1]
        v = v[:-1]
        package_version = "/".join(v)

    # create dummy file
    command = ["touch", package_name]
    subprocess.run(command, check=True)
    with open(package_name, "w") as file:
        file.write("Hello")
    deploy_to_location(package_name, package_version)
    # remove dummy file
    command = ["rm", package_name]
    subprocess.run(command, check=True)

def remove_item_from_location(package_version=None, package_name=None):
    """
    Function which removes a package from Cloudsmith, with the specified version
    and/or `package_name`. Can be either a file or a directory.

    :param package_version: `String` version(location) of the package to be removed, if missing, delete from root directory.
    :param package_name: `String` name of the package to be removed, if missing, all found with the version will be deleted.
    """

    query = ""
    if not package_version:
        package_version = args.package_version
    if not package_name:
        package_name = args.package_name

    if not package_name or not package_version:
        raise SystemError("Both `package_name` and `package_version` need to be specified, use `*` to delete all.")

    query += f"version:{package_version}+name:{package_name}"

    packages = get_all_packages(query)

    for package in packages:
        url = f"{API_URL}/packages/{CLOUDSMITH_REPO}/{package['identifier_perm']}"
        r = requests.delete(url, headers={"X-Api-Key": os.environ["CLOUDSMITH_API_KEY"]})
        if not r.ok:
            raise SystemError("Request to the Cloudsmith API failed")
        logger.info(f"Package {package['name']} with identifier {package['identifier_perm']} was deleted")

def get_artifacts_from_location(package_version=None, package_name=None, folder_structure=False):
    """
    Function which downloads artifacts from Cloudsmith, that match the `package_version`.
    The `folder_structure` can be recreated based on the `package_version`.

    :param package_version: `String` version(location) of the package(s) to be downloaded.
    :param folder_structure: `Bool` specify if the folder structure should be recreated.
    :return: `List` of the packages that were downloaded.
    """
    if not package_version and not args.package_version:
        raise SystemError("--package_version is required to check if a path exists")

    if not package_version:
        package_version = args.package_version
    if not package_version.startswith("^"):
        package_version = f"^{package_version}"

    if not package_name:
        package_name = args.package_name

    query = f"version:{package_version}"
    if package_name:
        query += f"+name:{package_name}"

    packages = get_all_packages(query)

    for package in packages:
        arguments = ["curl", "-H", f"X-Api-Key: {os.environ['CLOUDSMITH_API_KEY']}", "-1LfO", package['cdn_url']] 
        subprocess.run(arguments, check=True)
        if folder_structure:
            arguments = ["mkdir", "-p", package['version']]
            subprocess.run(arguments, check=True)
            arguments = ["mv", package['name'], package['version']]
            subprocess.run(arguments, check=True)
    logger.info(f"{len(packages)} packages with version {package_version} have been downloaded")
    return packages

def deploy_to_location(local_path=None, package_version=None, package_tags=None):
    """
    Function which uploads a package to Cloudsmith, from the given `local_path` to the given `CLOUDSMITH_REPO` with 
    a corresponding `package_version`. It requires the `cloudsmith-cli` tool to be installed. This can be done
    via `pip` - `python -m pip install cloudsmith-cli`

    :param local_path: `String` relative (or absolute) path to the package to be uploaded to Cloudsmith.
    :param package_version: `String` package version representing the path where you would like to find the package
                            if there would've been a folder structure. It defaults to `local_path` without the name itself.
    :param package_tags: `String` tags to be assigned to the package, separated by a `,`.
    """

    if not local_path and not args.local_path:
        raise SystemError("--local_path is required to copy a package.")

    if not local_path:
        local_path = args.local_path
    if not package_version:
        package_version = args.package_version
    if not package_tags:
        package_tags = args.package_tags

    if not package_version:
        package_version = '/'.join(local_path.split("/")[:-1])

    cmd = ["cloudsmith", "push", "raw", "--republish", CLOUDSMITH_REPO, local_path, "-k", os.environ["CLOUDSMITH_API_KEY"]]

    if package_version:
        cmd.extend(["--version", package_version])
    if package_tags:
        cmd.extend(["--tags", package_tags])

    output = subprocess.run(cmd, capture_output=True)
    if output.returncode == 0:
        logger.info(f"Package successfully uploaded package:{local_path} version:{package_version} package_tags:{package_tags}")
    else:
        raise SystemError(f"cmd: {cmd} failed with exit code {output.returncode}!")

def get_item_properties(package_version=None, package_name=None):
    """
    Function which gets the tags of a Cloudsmith package.

    :param package_version: `String` version of the package representing the theoretical location.
    :param package_name: `String` the name of the Cloudsmith package to retrieve tags from. Properties for folders do not exist.
    :return: `List` the tags for the given file
    """
    if not package_version:
        package_version = args.package_version
    if not package_name:
        package_name = args.package_name

    if not package_name:
        raise SystemError("Missing argument: package_name!")

    query = ""
    if package_version:
        query += f"version:{package_version}+"
    query += f"name:{package_name}"

    packages = get_all_packages(query)
    if not len(packages):
        raise SystemError(f"No package was found with the given parameters version:{package_version} name:{package_name}!")
    if len(packages) > 1:
        raise SystemError(f"Multiple packages found with the given parameters version:{package_version} name:{package_name}!")

    return packages[0].tags

if __name__ ==  "__main__":
    global args
    args = set_arguments()

    if not args:
        raise SystemError("Arguments failed to parse or are missing, try using `-h`")

    set_cloudsmith_repo(args.repo)

    if args.method is None:
        # Set pager to cat so that scrolling is not enabled
        os.environ['PAGER'] = 'cat'
        logger.info("\nWARNING: Method argument is missing!")
        help(check_path)
        help(get_subfolders)
        help(get_files)
        help(get_folder_structure)
        help(copy_to_location)
        help(create_item_to_location)
        help(remove_item_from_location)
        help(get_artifacts_from_location)
        help(deploy_to_location)
        help(get_item_properties)
    else:
        try:
            logger.info(args.method)
            method = globals()[args.method]
        except Exception:
            raise SystemError("Method not found: " + args.method) from None
        method()

############################ End of File ###############################
