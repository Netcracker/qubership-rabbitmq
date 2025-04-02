#!/bin/bash
set -x
set -e

INITIAL_CLUSTER_FORMATION_ATTEMPTS="180"
CLUSTER_REFORMATION_ATTEMPTS="30"

if [[ -z "$STORAGE_CLASS_NAME" ]] && [[ -z "$STORAGE_CLASS" ]] && \
  [[ $VCT_NAME == "default-vct-name" ]] && [[ -n "${PV_NAME}" ]] || [[ -n "${PV_LABELS}" ]]; then
    echo "Rebooting pods for Multi-StatefulSet Deployment (see architecture.md for more information)"
    i="0"
    ITER_ARR="${PV_NAME}"
    if [[ -n "${PV_LABELS}" ]]; then
      ITER_ARR="${PV_LABELS}"
    fi
    # shellcheck disable=SC2034
    for PV in ${ITER_ARR}
    do
        j="0"
        while ! oc rsh "rmqlocal-${i}-0" /bin/sh -c "rabbitmq-diagnostics -q check_running && rabbitmq-diagnostics -q check_local_alarms" | grep 'reported no local alarms' &> /dev/null; do
            echo "waiting for pod rmqlocal-${i}-0 to get up, ${j} time"
            sleep 5
            j=$((j + 1))
            if [ "${j}" -eq "${INITIAL_CLUSTER_FORMATION_ATTEMPTS}" ]; then
		        echo "Time is over"
		        exit 1
            fi
        done
        i=$((i + 1))
    done
    i="0"
    # shellcheck disable=SC2034
    for PV in ${ITER_ARR}
    do
        oc delete pod "rmqlocal-${i}-0"
        sleep 30
        j="0"
        while ! oc rsh "rmqlocal-${i}-0" /bin/sh -c "rabbitmq-diagnostics -q check_running && rabbitmq-diagnostics -q check_local_alarms" | grep 'reported no local alarms' &> /dev/null; do
            echo "waiting for pod rmqlocal-${i}-0 to get back up, ${j} time"
            sleep 30
            j=$((j + 1))
            if [ "${j}" -eq "${CLUSTER_REFORMATION_ATTEMPTS}" ]; then
		        echo "Time is over"
		        exit 1
            fi
        done
        if ! oc rsh "rmqlocal-${i}-0" /bin/sh -c "rabbitmqctl cluster_status" | grep 'rabbit@rmqlocal-0-0' &> /dev/null; then
            echo "ERROR: Cluster wasn't formed, fix cluster formation and restart the job"
            exit 1
        fi
        i=$((i + 1))
    done
else
    echo "Rebooting pods for Single-StatefulSet Deployment (see architecture.md for more information), REPLICAS = ${REPLICAS}"
    # shellcheck disable=SC2034
    for (( i=0; i < REPLICAS; i++ ))
    do
        j="0"
        while ! oc rsh "rmqlocal-${i}" /bin/sh -c "rabbitmq-diagnostics -q check_running && rabbitmq-diagnostics -q check_local_alarms" | grep 'reported no local alarms' &> /dev/null; do
            echo "waiting for pod rmqlocal-${i} to get up, ${j} time"
            sleep 5
            j=$((j + 1))
            if [ "${j}" -eq "${INITIAL_CLUSTER_FORMATION_ATTEMPTS}" ]; then
		        echo "Time is over"
		        exit 1
            fi
        done
    done
    # shellcheck disable=SC2034
    for (( i=0; i < REPLICAS; i++ ))
    do
        oc delete pod "rmqlocal-${i}"
        sleep 30
        j="0"
        while ! oc rsh "rmqlocal-${i}" /bin/sh -c "rabbitmq-diagnostics -q check_running && rabbitmq-diagnostics -q check_local_alarms" | grep 'reported no local alarms' &> /dev/null; do
            echo "waiting for pod rmqlocal-${i} to get back up, ${j} time"
            sleep 30
            j=$((j + 1))
            if [ "${j}" -eq "${CLUSTER_REFORMATION_ATTEMPTS}" ]; then
		        echo "Time is over"
		        exit 1
            fi
        done
        if ! oc rsh "rmqlocal-${i}" /bin/sh -c "rabbitmqctl cluster_status" | grep 'rabbit@rmqlocal-0' &> /dev/null; then
            echo "ERROR: Cluster wasn't formed, fix cluster formation and restart the job"
            exit 1
        fi
    done
fi