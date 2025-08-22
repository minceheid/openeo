#!/usr/bin/env python3
"""
GitHub Release/Branch Downloader for OpenEO

This script allows the `pi` user to:
  - List available releases and branches from the minceheid/openeo repo
  - Download and extract a selected release/branch
  - Write the release/branch name to release.txt in the extracted directory
  - Run the included deployment script (openeo_deploy.bash)

Author: Mike Scott
Date: 2025-08-20
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.error import URLError, HTTPError
from urllib.request import urlopen


GITHUB_REPO = "minceheid/openeo"
RELEASEDIR = "/home/pi/releases"
CUTOFF_DATE = datetime(2025, 7, 31, tzinfo=timezone.utc)


# ---------------------------
# Utility & Error Handling
# ---------------------------

class DeploymentError(Exception):
    """Custom exception for deployment-related errors."""
    pass


def run_command(cmd: list[str], check: bool = True) -> int:
    """Run a shell command and stream output directly to the terminal.

    Returns the process return code. Raises DeploymentError if check=True and command fails.
    """
    try:
        # Flush Python stdout so that subprocess output appears immediately
        sys.stdout.flush()
        result = subprocess.run(cmd, check=check)
        return result.returncode
    except subprocess.CalledProcessError as e:
        raise DeploymentError(f"Command failed: {' '.join(cmd)} (exit {e.returncode})")



def fetch_json(url: str) -> dict:
    """Fetch and parse JSON from a URL."""
    try:
        with urlopen(url) as response:
            return json.load(response)
    except HTTPError as e:
        raise DeploymentError(f"HTTP error fetching {url}: {e}")
    except URLError as e:
        raise DeploymentError(f"Network error fetching {url}: {e}")
    except json.JSONDecodeError as e:
        raise DeploymentError(f"Invalid JSON from {url}: {e}")


def fetch_url(url: str) -> bytes:
    """Fetch raw content from a URL."""
    try:
        with urlopen(url) as response:
            return response.read()
    except HTTPError as e:
        raise DeploymentError(f"HTTP error fetching {url}: {e}")
    except URLError as e:
        raise DeploymentError(f"Network error fetching {url}: {e}")


# ---------------------------
# GitHub Metadata Fetching
# ---------------------------

def get_releases_and_branches() -> list[str]:
    """Return a list of valid release tags and branch names."""
    releases = []

    # Fetch releases
    releases_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
    for release in fetch_json(releases_url):
        release_date = datetime.fromisoformat(release["created_at"].replace("Z", "+00:00"))
        if release_date > CUTOFF_DATE:
            releases.append(release["name"])

    # Fetch branches
    branches_url = f"https://api.github.com/repos/{GITHUB_REPO}/branches"
    for branch in fetch_json(branches_url):
        releases.append(branch["name"])

    return releases


def resolve_commit_sha(ref: str) -> str:
    """Resolve a release or branch name to a commit SHA."""
    commit_url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/{ref}"
    data = fetch_json(commit_url)
    return data["sha"]


def verify_required_file(sha: str, filename: str = "openeo_download.py"):
    """Check that a required file exists at the commit SHA on GitHub."""
    raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{sha}/{filename}"
    try:
        fetch_url(raw_url)  # will throw if 404 or network error
    except DeploymentError:
        raise DeploymentError(f"Incompatible release: missing required file '{filename}' at {sha}")


# ---------------------------
# Deployment Steps
# ---------------------------

def ensure_environment():
    """Verify script is running under correct conditions."""
    if os.getlogin() != "pi":
        raise DeploymentError("This script must be run as the 'pi' user.")

    # Run sudo check silently (no stdout/stderr leakage)
    try:
        subprocess.run(["sudo", "whoami"], check=True,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        raise DeploymentError("The 'pi' user does not appear to have full sudo rights.")



def prepare_release_dir():
    """Ensure release directory exists and is writable."""
    if not os.path.isdir(RELEASEDIR):
        os.mkdir(RELEASEDIR)
    os.chdir(RELEASEDIR)



def download_and_extract(url: str, destdir: str):
    """Download and extract a tarball from GitHub, retrying on 403 errors."""

    if os.path.exists(destdir):
        print(f"Removing existing installation at {destdir}")
        subprocess.run(["sudo", "rm", "-rf", destdir], check=True)

    retries = 3
    for attempt in range(1, retries + 1):
        print(f"Attempt {attempt} to download {url}...")

        # Run curl with -f (fail silently on HTTP errors) and pipe into tar
        try:
            curl_cmd = ["curl", "-sSL", "-f", url]
            tar_cmd = ["tar", "xvzf", "-"]

            curl_proc = subprocess.Popen(curl_cmd, stdout=subprocess.PIPE)
            tar_proc = subprocess.Popen(tar_cmd, stdin=curl_proc.stdout)
            curl_proc.stdout.close()  # allow curl_proc to receive SIGPIPE if tar_proc exits
            tar_proc.communicate()

            if curl_proc.wait() == 0 and tar_proc.returncode == 0:
                print("Download and extraction successful.")
                return
            else:
                # If curl fails, check if it was 403
                curl_returncode = curl_proc.returncode
                if curl_returncode == 22:  # curl exit code 22 = HTTP error
                    print("Received HTTP error (possibly 403). Waiting 60s before retry...")
                    if attempt < retries:
                        time.sleep(60)
                        continue
                    else:
                        raise DeploymentError(f"Failed to download {url} after {retries} attempts.")
                else:
                    raise DeploymentError(f"curl or tar failed (curl={curl_returncode}, tar={tar_proc.returncode})")

        except subprocess.CalledProcessError as e:
            raise DeploymentError(f"Command failed: {e}")

    raise DeploymentError(f"Failed to download and extract {url} after {retries} attempts.")

def write_release_file(destdir: str, release_name: str):
    """Write release/branch name into release.txt inside extracted dir."""
    release_file = os.path.join(RELEASEDIR, destdir, "release.txt")
    try:
        with open(release_file, "w") as f:
            f.write(release_name + "\n")
    except OSError as e:
        raise DeploymentError(f"Failed to write release.txt: {e}")


def run_deploy_script(destdir: str):
    """Run the deployment script if it exists."""
    deploy_script = os.path.join(RELEASEDIR, destdir, "openeo_deploy.bash")
    if not os.path.isfile(deploy_script):
        raise DeploymentError(f"Deploy script not found: {deploy_script}")

    print(f"Running Deploy Script: {deploy_script}")
    run_command(["bash", deploy_script])


# ---------------------------
# Main
# ---------------------------

def main():
    parser = argparse.ArgumentParser(description="Download and deploy GitHub release/branch for OpenEO.")
    parser.add_argument("-r", "--release", help="Release tag or branch name to install")
    parser.add_argument("-l", "--list", action="store_true", help="List available releases or branches")
    args = parser.parse_args()

    try:
        ensure_environment()

        releases = get_releases_and_branches()
        if not releases:
            raise DeploymentError("No release candidates found.")

        if args.list:
            print("\n".join(releases))
            return

        # Select release
        if args.release:
            if args.release not in releases:
                raise DeploymentError(f"Requested release '{args.release}' not found.")
            selected = args.release
        else:
            selected = releases[0]  # default to newest candidate

        sha = resolve_commit_sha(selected)

        # Verify required file exists in commit before download
        verify_required_file(sha, "openeo_download.py")

        url = f"https://github.com/{GITHUB_REPO}/archive/{sha}.tar.gz"
        destdir = f"openeo-{sha}"

        print(f"Selected '{selected}' → {url} → {destdir}")

        prepare_release_dir()
        download_and_extract(url, destdir)

        # Write release.txt with release or branch name
        write_release_file(destdir, selected)

        run_deploy_script(destdir)

        print("Deployment complete. A reboot is recommended.")

    except DeploymentError as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
