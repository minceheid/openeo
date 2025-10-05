#!/usr/bin/bash

date
echo "Updating OpenEO"
curl -sSL https://github.com/minceheid/openeo/raw/refs/heads/main/openeo_download.py | python3 -
