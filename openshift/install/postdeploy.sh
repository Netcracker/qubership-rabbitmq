#!/bin/bash
set -x
set -e

if  [[ -n "${CLEAN_RABBITMQ_PVS}" ]] && [[ "${CLEAN_RABBITMQ_PVS}" == "true" ]]; then
    bash scripts/clean_rabbitmq_pvs.sh
fi

bash scripts/common_postdeploy.sh


