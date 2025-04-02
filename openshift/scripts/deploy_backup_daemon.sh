#!/usr/bin/env bash

set -e

. scripts/dc_readiness_check.sh

if [[ -z "${BACKUP_DOCKER_TAG}" ]]
then
    echo "Not found BACKUP_DOCKER_TAG parameter"
    exit 1
fi

function process_backuper() {
    command=$1
    python scripts/modify_backup_dc.py --template-folder "backup_daemon_resources/" "${command}"
}

if  [[ -n "${BACKUP_STORAGE_NODE}" ]];
then
   process_backuper inject_nodeselector
fi

KUBE_VERSION=$(oc version | tail -n1)
export KUBE_VERSION
echo "${KUBE_VERSION}"
if [[ $KUBE_VERSION = *" v1.9."* ]] || [[ $KUBE_VERSION = *" v1.11."* ]]; then
    env OPENSHIFT_WORKSPACE="${OPENSHIFT_WORKSPACE}" envsubst < backup_daemon_resources/backuper_kubeaccess.yaml \
        | oc apply -f -
    process_backuper inject_rabbitmq_sa
fi


cat backup_daemon_resources/backup_template.yaml

if  [[ -n "${BACKUP_PV_LABEL}" ]];
then
    BACKUP_PV_LABEL_KEY=$(echo "${BACKUP_PV_LABEL}"|cut -d: -f1)
    BACKUP_PV_LABEL_VALUE=$(echo "${BACKUP_PV_LABEL}"|cut -d: -f2)
    if  [[ -n "${BACKUP_STORAGE_CLASS}" ]];
    then
    if [[ "${BACKUP_STORAGE_CLASS}" == '""' ]] || [[ "${BACKUP_STORAGE_CLASS}" == "''" ]]; then
        BACKUP_STORAGE_CLASS=""
    fi
      oc process \
      -f backup_daemon_resources/backuper_pvc_with_selector_and_storage_class.yaml -p \
      BACKUP_PV_LABEL_KEY="${BACKUP_PV_LABEL_KEY}" \
      BACKUP_STORAGE_CLASS="${BACKUP_STORAGE_CLASS}" \
      BACKUP_PV_LABEL_VALUE="${BACKUP_PV_LABEL_VALUE}" | oc apply -f - || true
    else
      oc process \
      -f backup_daemon_resources/backuper_pvc_with_selector.yaml -p \
      BACKUP_PV_LABEL_KEY="${BACKUP_PV_LABEL_KEY}" \
      BACKUP_STORAGE_CLASS="${BACKUP_STORAGE_CLASS}" \
      BACKUP_PV_LABEL_VALUE="${BACKUP_PV_LABEL_VALUE}" | oc apply -f - || true
    fi
else
oc process \
    -f backup_daemon_resources/backuper_pvc.yaml -p \
    BACKUP_STORAGE_SIZE="${BACKUP_STORAGE_SIZE}" \
    BACKUP_STORAGE_CLASS="${BACKUP_STORAGE_CLASS}" \
    BACKUP_STORAGE_PV="${BACKUP_STORAGE_PV}" | oc apply -f - || true
fi

oc process \
    -f backup_daemon_resources/backup_template.yaml -p \
    BACKUP_CPU_REQUEST="${BACKUP_CPU_REQUEST}" \
    BACKUP_CPU_LIMIT="${BACKUP_CPU_LIMIT}" \
    BACKUP_MEMORY_REQUEST="${BACKUP_MEMORY_REQUEST}" \
    BACKUP_MEMORY_LIMIT="${BACKUP_MEMORY_LIMIT}" \
    BACKUP_DOCKER_TAG="${BACKUP_DOCKER_TAG}" \
    BACKUP_LOG_LEVEL="${BACKUP_LOG_LEVEL}" \
    BACKUP_STORAGE_NODE="${BACKUP_STORAGE_NODE}" \
    BACKUP_SCHEDULE="${BACKUP_SCHEDULE}" | oc apply -f -

check_readiness "rabbitmq-backup-daemon"


