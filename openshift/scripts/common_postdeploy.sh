#!/bin/bash
set -x
set -e

if [ "${MONITORING_ENABLED}" = "true" ];
then
    echo "Deploy the telegraf"

    bash scripts/deploy_monitoring.sh
else
    echo "Skip deploying the telegraf"
fi

if [ "${BACKUP_DAEMON_ENABLED}" = "true" ];
then
    echo "Deploy backup daemon for rabbitmq"

    bash scripts/deploy_backup_daemon.sh
else
    echo "Skip deploying backup daemon for rabbitmq"
fi

if [[ ! -z "${RUN_CLUSTER_TEST}" ]] && [[ "${RUN_CLUSTER_TEST}" == "true" ]];
then
    if [[ -z "${TEST_PATH}" ]];
    then
        echo "generating TEST_PATH param"
        if [[ -z "${REGISTRY}" ]];
        then
            export REGISTRY="artifactorycn.netcracker.com:17008"
            echo "Use default registry = ${REGISTRY}"
        else
            echo "Use custom registry = ${REGISTRY}"
        fi

        if [[ -z "${TEST_IMAGE}" ]];
        then
            export TEST_IMAGE="thirdparty/thirdparty.platform.services_rabbitmq:master_latest_robot-image"
            echo "Use default test_image = ${TEST_IMAGE}"
        else
            echo "Use custom test_image = ${TEST_IMAGE}"
        fi
        export TEST_PATH=${REGISTRY}/${TEST_IMAGE}
        echo "Run test for cluster"
        bash scripts/test_cluster.sh
    else
        echo "using predefined TEST_PATH from deploy param"
        echo "Run test for cluster"
        bash scripts/test_cluster.sh
    fi
fi