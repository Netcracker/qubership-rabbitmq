#!/bin/bash
set -x
set -e

REBOOT_SECONDS=240
POD_KILL_GRACE_PERIOD=30

function clean_reboot_pods() {
    pod_arr=$1
        echo "Rebooting pods for Single StatefulSet Deployment (see architecture.md for more information)"
    i="0"
    # shellcheck disable=SC2034
    for rmqpod in ${pod_arr}
    do
         j="0"
         until timeout 15s oc rsh "rmqlocal-${i}-0" /bin/sh -c "touch /var/lib/rabbitmq/delete_all"
         do
            echo "waiting for pod rmqlocal-${i}-0 to be able to execute command, ${j} time"
            sleep 1
            j=$((j + 1))
            if [ "${j}" -eq "${REBOOT_SECONDS}" ]; then
		        echo "Time is over"
		        exit 1
            fi
         done
         i=$((i + 1))
    done
    oc delete --force --grace-period="${POD_KILL_GRACE_PERIOD}" pod --all
    echo "sleeping for ${POD_KILL_GRACE_PERIOD} seconds after killing all pods"
    sleep "${POD_KILL_GRACE_PERIOD}"
}

if [[ -z "$STORAGE_CLASS_NAME" ]] && [[ -z "$STORAGE_CLASS" ]] && \
  [[ $VCT_NAME == "default-vct-name" ]] && [[ -n "${PV_NAME}" ]]
then
  clean_reboot_pods "${PV_NAME}"
elif [[ -z "$STORAGE_CLASS_NAME" ]] && [[ -z "$STORAGE_CLASS" ]] && \
  [[ $VCT_NAME == "default-vct-name" ]] && [[ -n "${PV_LABELS}" ]]
then
  clean_reboot_pods "${PV_LABELS}"
fi