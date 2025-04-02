#!/usr/bin/env bash

set -e
. scripts/dc_readiness_check.sh

if [[ -z "${INFLUXDB_URL// }" ]]
then
    echo "Not found INFLUXDB_URL parameter"
    exit 1
fi

if [[ -z "${INFLUXDB_DATABASE// }" ]]
then
    echo "Not found INFLUXDB_DATABASE parameter"
    exit 1
fi

if [[ -z "${INFLUXDB_USER// }" ]]
then
    echo "Not found INFLUXDB_USER parameter"
    exit 1
fi

if [[ -z "${INFLUXDB_PASSWORD// }" ]]
then
    echo "Not found INFLUXDB_PASSWORD parameter"
    exit 1
fi

if [[ -z "${TELEGRAF_IMAGE// }" ]]
then
    echo "Not found TELEGRAF_IMAGE parameter"
    exit 1
fi

oc delete secrets rabbitmq-monitoring --ignore-not-found
oc create secret generic rabbitmq-monitoring \
    --from-literal=influxdb-debug="${INFLUXDB_DEBUG:-false}" \
    --from-literal=metric-collection-interval="${METRIC_COLLECTION_INTERVAL:-30s}" \
    --from-literal=influxdb-url="${INFLUXDB_URL}" \
    --from-literal=influxdb-database="${INFLUXDB_DATABASE}" \
    --from-literal=influxdb-user="${INFLUXDB_USER}" \
    --from-literal=influxdb-password="${INFLUXDB_PASSWORD}"

oc create sa rabbitmq-monitoring || true
oc policy add-role-to-user view -z rabbitmq-monitoring


oc process -f template.telegraf.yaml -p TELEGRAF_IMAGE="${TELEGRAF_IMAGE}" \
   | oc apply -f -

oc delete pod -l name=telegraf --grace-period=0 --ignore-not-found

sleep 15  
  
check_readiness "telegraf"
