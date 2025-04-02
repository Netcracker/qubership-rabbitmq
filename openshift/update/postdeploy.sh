#!/bin/bash
set -x
set +e

POD_NAME=$(oc get pod --selector app="${BROKER_NAME_INTERNAL}" | grep "${BROKER_NAME_INTERNAL}" | grep -v -m1 'deploy'| cut -d " " -f1)

oc exec "${POD_NAME}" change_password "${RABBITMQ_USER}" "${RABBITMQ_PASSWORD}"
# todo refactor
# shellcheck disable=SC2181
while [[ $? -ne 0 ]]; do
    sleep 10
    if [[ -f /bin/change_password ]]; then
        oc exec "${POD_NAME}" change_password "${RABBITMQ_USER}" "${RABBITMQ_PASSWORD}"
    else 
        break
    fi
done
set -e

if  [[ -n "${CLEAN_RABBITMQ_PVS}" ]] && [[ "${CLEAN_RABBITMQ_PVS}" == "true" ]]; then
    bash scripts/clean_rabbitmq_pvs.sh
elif  [[ -n "${AUTO_REBOOT}" ]] && [[ "${AUTO_REBOOT}" == "true" ]]; then
    bash scripts/restart_nodes_with_validation.sh
fi

bash scripts/common_postdeploy.sh
