#!/bin/bash

CONFIG_NODES=""

if [[ ! -z "${RABBITMQ_PLUGINS}" ]];
then
    RABBITMQ_PLUGINS=",${RABBITMQ_PLUGINS}"
fi

if [[ -n "${PV_NAME}" ]] && [[ -z "$STORAGE_CLASS_NAME" ]] &&  \
  [[ -z "$STORAGE_CLASS" ]] && [[ $VCT_NAME == "default-vct-name" ]]; then
    CONFIG_NODES="cluster_formation.peer_discovery_backend = rabbit_peer_discovery_classic_config
"
    i="0"

    for PV_NAME in ${PV_NAME}
    do
        CONFIG_NODES="${CONFIG_NODES}cluster_formation.classic_config.nodes.${i} = rabbit@rmqlocal-${i}-0
"
        i=$((i + 1))
    done
    ENABLED_PLUGINS="[rabbitmq_management${RABBITMQ_PLUGINS}]."
elif [[ -n "${PV_LABELS}" ]] && [[ -z "$STORAGE_CLASS_NAME" ]] &&  \
  [[ -z "$STORAGE_CLASS" ]] && [[ $VCT_NAME == "default-vct-name" ]]; then
        CONFIG_NODES="cluster_formation.peer_discovery_backend = rabbit_peer_discovery_classic_config
"
    i="0"

    for PV_LABELS in ${PV_LABELS}
    do
        CONFIG_NODES="${CONFIG_NODES}cluster_formation.classic_config.nodes.${i} = rabbit@rmqlocal-${i}-0
"
        i=$((i + 1))
    done
    ENABLED_PLUGINS="[rabbitmq_management${RABBITMQ_PLUGINS}]."

else
    CONFIG_NODES="cluster_formation.peer_discovery_backend = rabbit_peer_discovery_k8s
cluster_formation.k8s.host = kubernetes.default.svc.cluster.local
cluster_formation.k8s.address_type = hostname"
    ENABLED_PLUGINS="[rabbitmq_management,rabbitmq_peer_discovery_k8s${RABBITMQ_PLUGINS}]."
fi

RABBITMQ_CONF=$(cat <<-END
## Clustering
$CONFIG_NODES
cluster_partition_handling = autoheal

## queue master locator 
queue_master_locator = min-masters

## enable guest user 
loopback_users.guest = false
## logging
log.console = false

log.upgrade.level = none

log.upgrade.file = false

log.file = false

END
)

ADVANCED_CONF='[{lager,
    [{handlers,
        [{lager_console_backend,
            [{formatter_config,["[",date," ",time,"]",color,"[",severity,"] ",
                  {pid,[]},
                  " ",message,"\n"]},
             {level,info}]}]}]
}, {rabbit,
    [{log,
        [{file, [{file, false}]}] %% Disable RabbitMQ file handler
    }]}].'

echo "RabbitMQ config: ${RABBITMQ_CONF}"
echo "RabbitMQ advanced config for lager: ${ADVANCED_CONF}"
echo "RabbitMQ plugins: ${ENABLED_PLUGINS}"

oc delete cm rabbitmq-config --ignore-not-found=true
oc create cm rabbitmq-config \
    --from-literal=enabled_plugins="${ENABLED_PLUGINS}" \
    --from-literal=rabbitmq.conf="${RABBITMQ_CONF}" \
    --from-literal=advanced.config="${ADVANCED_CONF}"


oc delete secrets rabbitmq-default-secret
oc create secret generic rabbitmq-default-secret \
    --from-literal=user="${RABBITMQ_USER}" \
    --from-literal=password="${RABBITMQ_PASSWORD}" \
    --from-literal=rmqcookie="${RABBITMQ_COOKIE}"