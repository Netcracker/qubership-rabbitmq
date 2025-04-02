#!/bin/bash
set -x
set -e

if  [[ -n "${RABBITMQ_HIPE_COMPILE}" ]]; then
    echo "RABBITMQ_HIPE_COMPILE parameter is deprecated, HiPE compilation is no longer supported."
fi

# shellcheck disable=SC2153
if [[ -z "${PV_NAME}" ]] && [[ -z "$STORAGE_CLASS_NAME" ]] && \
  [[ -z "$STORAGE_CLASS" ]] && [[ $VCT_NAME == "default-vct-name" ]];
then
    # shellcheck disable=SC2016
    echo 'Trying to find the persistence volumes by template  "pv-rabbitmq-{{ oc_project }}-node$order_number" because the PV_NAME parameter is empty. Starting the search with 0.'
    PROJECT_NAME="$(oc project -q)"
    PV_0_NAME="pv-rabbitmq-${PROJECT_NAME}-node0"
    # TODO: the command can be failed because of a network problem. Autodiscovery of PVs will be failed.
    # shellcheck disable=SC2086
    PV_0="$(oc get pv ${PV_0_NAME} || true)"

    if [[ -z "${PV_0}" ]];
    then
        echo "Can't detect the ${PV_0_NAME} persistence volume. Autodiscovery of PVs failed."
    else
        echo "Detected the ${PV_0_NAME} persistence volume. Autodiscovery of PVs finishes successfully"

        export PV_NAME="${PV_0_NAME}"
        for (( i=1; i < REPLICAS; i++ ))
        do
            PV_NAME="${PV_NAME} pv-rabbitmq-${PROJECT_NAME}-node${i}"
        done

        echo "The final result of PV_NAME is \"${PV_NAME}\""
    fi
fi

bash scripts/put_parameters_to_map.sh

KUBE_VERSION=$(oc version | tail -n1)
export KUBE_VERSION
echo "${KUBE_VERSION}"

if [[ $KUBE_VERSION = *" v1.9."* ]] || [[ $KUBE_VERSION = *" v1.11."* ]]; then
    env OPENSHIFT_WORKSPACE="${OPENSHIFT_WORKSPACE}" envsubst < kubeaccess.yaml \
        | oc apply -f -
else
    # currently requires admin/anyuid privileges
    oc adm policy add-role-to-user admin -z default || true
    oc adm policy add-scc-to-user anyuid -z default || true
fi

if  [[ -n "$NODESELECTOR_REGION" ]]; then
    echo "patching project to add nodeselector region.."
    oc patch namespace "${OPENSHIFT_WORKSPACE}" --patch '{ "metadata":{"annotations": {"openshift.io/node-selector": "region='"${NODESELECTOR_REGION}"'" }}}'
fi

function deploy_rabbitmq() {
    BROKER_NAME="$1"

    echo "Final RabbitMQ template:"
    cat resources/rabbitmq.yaml
    oc delete statefulset --cascade=false "${BROKER_NAME}" --ignore-not-found=true
    # When PV_NODE_NAMES variable is set, we are ignoring all commands that require cluster admin privileges
    if  [[ -n "${PV_NAME}" ]] && [[ -n "${PV}" ]] && [[ -z "${PV_NODE_NAMES}" ]]; then
        PV_CALIMED=$(oc get pv "$PV" -o jsonpath="{.status.phase}")
        if [[ "$PV_CALIMED" != 'Released' ]] && [[ "$PV_CALIMED" != 'Available' ]]; then
            echo 'Warning. PV='"$PV"' have status:'"$PV_CALIMED"
        elif [[ "$PV_CALIMED" == 'Released' ]]; then
            echo "PV is released, patching..."
            oc patch pv "${PV}" --type json -p $'- op: remove\n  path: /spec/claimRef' || true
        fi
    fi

    oc process \
        -f resources/rabbitmq.yaml -p \
        DOCKER_TAG="${DOCKER_TAG}" \
        REPLICAS="${REPLICAS}" \
        BROKER_NAME_INTERNAL="${BROKER_NAME}" \
        RMQ_RES_REQUESTS_CPU="${RMQ_RES_REQUESTS_CPU}" \
        RMQ_RES_REQUEST_MEMORY="${RMQ_RES_REQUEST_MEMORY}" \
        RMQ_RES_LIMITS_CPU="${RMQ_RES_LIMITS_CPU}" \
        RMQ_RES_LIMITS_MEMORY="${RMQ_RES_LIMITS_MEMORY}" \
        RMQ_TIMEOUT_SECONDS="${RMQ_TIMEOUT_SECONDS}" \
        RABBITMQ_VM_MEMORY_HIGH_WATERMARK="${RABBITMQ_VM_MEMORY_HIGH_WATERMARK}" \
        PVC_CAPACITY="${PVC_CAPACITY}" \
        AUTOCLUSTER_CLEANUP="${AUTOCLUSTER_CLEANUP}" \
        CLEANUP_WARN_ONLY="${CLEANUP_WARN_ONLY}" \
        RABBITMQ_USE_LONGNAME="${RABBITMQ_USE_LONGNAME}" \
        PV="${PV}" \
        PVC_NAME="${PVC_NAME}" \
        PV_NODE="${PV_NODE}" \
        PV_STORAGE_CLASS="${PV_STORAGE_CLASS}" \
        IMAGE_PULL_POLICY="${IMAGE_PULL_POLICY}" \
        LABEL_VALUE="${LABEL_VALUE}" \
        LABEL_KEY="${LABEL_KEY}" \
        RABBITMQ_NODENAME="${RABBITMQ_NODENAME}" | oc apply -f -
}

function scale_down_rabbitmq_replic() {
    replica_name="${1}"

    echo "Scale down the ${replica_name} statfulset"
    oc rsh "${replica_name}"-0 /bin/sh -c "rabbitmqctl stop_app && rabbitmqctl reset"

    oc delete all -l rabbitmq-app="${replica_name}"
    oc delete pvc -l rabbitmq-app="${replica_name}"
}

function process_statefulset() {
    command=$1

    python scripts/modify_statefulset.py --template-folder "resources/" "${command}"
}

if [[ $KUBE_VERSION = *" v1.9."* ]] || [[ $KUBE_VERSION = *" v1.11."* ]]; then
    echo "modifying template.json to make it work with kubernetes 1.9 or 1.11..."

    if [[ ! -z "${POD_AFFINITY_TERM}" ]] && [[ "${POD_AFFINITY_TERM}" = "required" ]]
    then
        export POD_AFFINITY_TERM="${POD_AFFINITY_TERM}"
    fi

    process_statefulset upgrade_to_parallel
fi

if [[ -z "$STORAGE_CLASS_NAME" ]] && [[ -z "$STORAGE_CLASS" ]] && [[ $VCT_NAME == "default-vct-name" ]]; then
    # shellcheck disable=SC2153
    if  [[ -n "${PV_LABELS}" ]]; then
        echo "using host bound pvs configuration with labels"
        export RABBITMQ_USE_LONGNAME="false"
        export REPLICAS="1"
        # shellcheck disable=SC2206
        EXPECTED_REPLICAS=($PV_LABELS)
        EXPECTED_NUMBER_OF_REPLICAS="${#EXPECTED_REPLICAS[@]}"
        CURRENT_REPLICAS="$(oc get statefulset -l app=rmqlocal --no-headers | wc -l)"
        echo "Current number of statefulsets is ${CURRENT_REPLICAS}. But expected number is ${EXPECTED_NUMBER_OF_REPLICAS}"

        if ((EXPECTED_NUMBER_OF_REPLICAS < CURRENT_REPLICAS)); then
            i="0"
            for (( i=EXPECTED_NUMBER_OF_REPLICAS; i < CURRENT_REPLICAS; i++ ))
            do
                scale_down_rabbitmq_replic "rmqlocal-${i}"
            done
        fi

        process_statefulset inject_pvc_by_labels

        i="0"
        for PV_LABEL in ${PV_LABELS}
        do
            # shellcheck disable=SC2206
            NODES_ARR=($PV_NODE_NAMES)
            PV_NODE=${NODES_ARR[i]}
            if  [[ -n "${PV_LABELS_STORAGE_CLASSES}" ]]; then
                # shellcheck disable=SC2206
                STORAGE_CLASSES_ARR=($PV_LABELS_STORAGE_CLASSES)
                PV_STORAGE_CLASS=${STORAGE_CLASSES_ARR[i]}
            elif [[ -n "${PV_LABELS_STORAGE_CLASS}" ]]; then
                if [[ "${PV_LABELS_STORAGE_CLASS}" == '""' ]] || [[ "${PV_LABELS_STORAGE_CLASS}" == "''" ]]; then
                    PV_STORAGE_CLASS=""
                else
                    PV_STORAGE_CLASS="${PV_LABELS_STORAGE_CLASS}"
                fi
            fi
            LABEL_KEY=$(echo "${PV_LABEL}"|cut -d: -f1)
            LABEL_VALUE=$(echo "${PV_LABEL}"|cut -d: -f2)
            export PV_STORAGE_CLASS

            export LABEL_KEY
            export LABEL_VALUE
            export PV_NODE
            # TODO better name?
            PVC_NAME="${LABEL_VALUE}-rmq-pvc"
            export PVC_NAME

            deploy_rabbitmq "rmqlocal-${i}"

            i=$((i + 1))
        done
    elif  [[ -n "${PV_NAME}" ]]; then
        echo "using host bound pvs configuration"

        export RABBITMQ_USE_LONGNAME="false"
        export REPLICAS="1"
        if  [[ -z "${PV_NODE_NAMES}" ]]; then
            for PV in ${PV_NAME}
            do
                echo "Check that ${PV} PV exists and contains the node label"
                oc get pv "${PV}" -o=jsonpath='{.metadata.labels.node}'
            done
        fi
        # shellcheck disable=SC2206
        EXPECTED_REPLICAS=($PV_NAME)
        EXPECTED_NUMBER_OF_REPLICAS="${#EXPECTED_REPLICAS[@]}"
        CURRENT_REPLICAS="$(oc get statefulset -l app=rmqlocal --no-headers | wc -l)"
        echo "Current number of statefulsets is ${CURRENT_REPLICAS}. But expected number is ${EXPECTED_NUMBER_OF_REPLICAS}"

        if ((EXPECTED_NUMBER_OF_REPLICAS < CURRENT_REPLICAS)); then
            i="0"
            for (( i=EXPECTED_NUMBER_OF_REPLICAS; i < CURRENT_REPLICAS; i++ ))
            do
                scale_down_rabbitmq_replic "rmqlocal-${i}"
            done
        fi

        process_statefulset inject_pvc

        i="0"
        for PV in ${PV_NAME}
        do
            if  [[ -n "${PV_NODE_NAMES}" ]]; then
                # shellcheck disable=SC2206
                NODES_ARR=($PV_NODE_NAMES)
                PV_NODE=${NODES_ARR[i]}
                #ToDo: maybe we should ask for storage class in installation parameters
                PV_STORAGE_CLASS=""
            else
                # shellcheck disable=SC2086
                PV_NODE="$(oc get pv ${PV} -o=jsonpath='{.metadata.labels.node}')"
                # shellcheck disable=SC2086
                PV_STORAGE_CLASS="$(oc get pv ${PV} -o=jsonpath='{.spec.storageClassName}')"
                if [[ -z "$PV_STORAGE_CLASS" ]]; then
                    # shellcheck disable=SC2086
                    PV_STORAGE_CLASS="$(oc get pv ${PV} -o=jsonpath='{.metadata.annotations.volume\.beta\.kubernetes\.io/storage-class}')"
                fi
            fi

            export PV_NODE
            export PV_STORAGE_CLASS

            export PV

            PVC_NAME="${PV}-rmq-pvc"
            export PVC_NAME

            deploy_rabbitmq "rmqlocal-${i}"

            i=$((i + 1))
        done
    else
        if [[ $KUBE_VERSION = *" v1.9."* ]] || [[ $KUBE_VERSION = *" v1.11."* ]]; then
        # We are using different probes for 3.9/3.11 because in the situation
        # when pods are killed one right after another in reverse order 
        # both pods will be going up at the same time. In 1.5 however 
        # openshift will wait till one of the pods is Ready
            echo "using non-persistence configuration for V1.9 or V1.11"
            process_statefulset inject_non_persistent_probes_311
        else
            echo "using non-persistence configuration for V1.5"
            process_statefulset inject_non_persistent_probes_15
        fi
        deploy_rabbitmq "rmqlocal"
    fi
else
    echo "using volume claim template configuration"

    process_statefulset inject_volume_claim_template
    deploy_rabbitmq "rmqlocal"
fi

cat template.json