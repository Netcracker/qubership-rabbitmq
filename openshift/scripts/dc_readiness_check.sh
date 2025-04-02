#!/usr/bin/env bash

check_readiness() {
    attempts=40
    is_ready=false
    while [ $attempts -gt 0 ]
  	do
        local dc
        dc=$(oc get dc "$1" -o=json)
        set +e
        local EXIT_CODE
        python scripts/check.py "${dc}"
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 0 ]; then
            is_ready=true
            break
        elif [ $EXIT_CODE -eq 1 ]; then
            is_ready=false
        fi
        echo "waiting for $1 to become ready, attempts left: ${attempts}"
        sleep 5
        attempts="$((attempts - 1))"
    set -e
    done
    if [ $is_ready == false ]; then
        echo "Something went wrong! Pods of $1 is not ready"
        exit 1
    fi
}