#!/bin/bash
set -euo pipefail

apt-get update
apt-get install -y --no-install-recommends graphviz

pip install -r requirements.txt
chmod +x terravision
