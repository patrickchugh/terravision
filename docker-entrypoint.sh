#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${TFENV_TERRAFORM_VERSION:-}" ]]; then
    export PATH="/home/terravision/.tfenv/bin:${PATH}"
    /home/terravision/.tfenv/bin/tfenv install "${TFENV_TERRAFORM_VERSION}"
    /home/terravision/.tfenv/bin/tfenv use "${TFENV_TERRAFORM_VERSION}"
fi


exec terravision "$@"
