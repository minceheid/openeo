#!/usr/bin/python3

from urllib.request import urlopen
from datetime import datetime,timezone
from argparse import ArgumentParser
import json,os


parser = ArgumentParser()
parser.add_argument("-r", "--release", dest="release",help="Release tag or branch name to install")
parser.add_argument("-l", "--list", action='store_true',help="List available releases or branches")

args=parser.parse_args()


if os.getlogin()!="pi":
	print("ERROR: this must be be run by the pi user")
	exit(10)

if os.system("sudo whoami>/dev/null")!=0:
	print("ERROR: the pi user does not appear to have full sudo rights. Please check configurations")
	exit(11)


releases=[]

# Get Releases
url="https://api.github.com/repos/minceheid/openeo/releases"
response = urlopen(url)
data_json = json.loads(response.read())

for release in data_json:
    release_date=datetime.fromisoformat(release["created_at"].replace('Z', '+00:00'))
    if (release_date>datetime(2025,7,31,tzinfo=timezone.utc)):
	# This is a viable release candidate
        releases.append(release["name"])

# Get Branches
response = urlopen("https://api.github.com/repos/minceheid/openeo/branches")
data_json = json.loads(response.read())

for branch in data_json:
	releases.append(branch["name"])

if (args.list):
	for name in releases:
		print(name)
	exit(0)

if (len(releases)==0):
	print("ERROR: No release candidates found. Something odd happening")
	exit(2)

selected_release=None
if (args.release):
	for name in releases:
		if (args.release==name):
			selected_release=name
			# break from loop
			continue
	if selected_release==None:
		print(f"ERROR: \"{args.release}\" not found")
		exit(1)
else:
	selected_release=releases[0]


response = urlopen(f"https://api.github.com/repos/minceheid/openeo/commits/{selected_release}")
data_json = json.loads(response.read())
sha=data_json["sha"]

selected_release_url=f"https://github.com/minceheid/openeo/archive/{sha}.tar.gz"
selected_release_destdir=f"openeo-{sha}"


print(f"Release \"{selected_release}\" selected for download from \"{selected_release_url}\" to \"{selected_release_destdir}\"")

RELEASEDIR="/home/pi/releases"
if ( not os.path.isdir(RELEASEDIR)):
	os.mkdir(RELEASEDIR)

os.chdir(RELEASEDIR)
if (os.getcwd()!=RELEASEDIR):
	print(f"ERROR: was not able to chdir to {RELEASEDIR} - please investigate")
	exit(4)

DEPLOY=f"{RELEASEDIR}/{selected_release_destdir}/openeo_deploy.bash"

if (os.path.exists(selected_release_destdir)):
	print(f"an installation already exists at {selected_release_destdir}. Deleting")
	retval=os.system(f"sudo rm -rf {selected_release_destdir}")
	if (retval!=0):
		print(f"ERROR: deletion of {selected_release_destdir} failed - please investigate")
		exit(3)

# Now we should be ready to download and extracto
retval=os.system(f"curl -sSL {selected_release_url} | tar xvzf -")
if (retval!=0 or not os.path.isfile(DEPLOY)):
	print(f"ERROR: extract of tarball failed - please investigate {retval}")
	exit(5)

print(f"Running Deploy Script: {DEPLOY}");
retval=0
#retval=os.system(DEPLOY)
if (retval!=0):
	print(f"ERROR: Deploy script may not have completed sucessfully - please investigate")
	exit(6)

print("Deployment complete. A reboot is recommended")
