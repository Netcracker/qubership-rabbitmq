#!/usr/bin/env python

# Copyright 2024-2025 NetCracker Technology Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import sys
import re

import yaml


def inject_volume_claim_template(statefulset):
    env_storage_class = os.environ.get("STORAGE_CLASS")
    env_storage_class_name = os.environ.get("STORAGE_CLASS_NAME")
    vct_name = os.getenv("VCT_NAME")
    pvc_capacity = os.getenv("PVC_CAPACITY")

    volume_claim_template = {
        "metadata": {
            "name": vct_name
        },
        "spec": {
            "accessModes": [
                "ReadWriteOnce"
            ],
            "resources": {
                "requests": {
                    "storage": pvc_capacity
                }
            }
        }
    }

    if env_storage_class:
        volume_claim_template["metadata"]["annotations"] = {
            "volume.beta.kubernetes.io/storage-class": env_storage_class
        }
    if env_storage_class_name:
        volume_claim_template["spec"]["storageClassName"] = env_storage_class_name
    statefulset["spec"]["volumeClaimTemplates"].append(volume_claim_template)
    statefulset["spec"]["template"]["spec"]["containers"][0]["volumeMounts"].append(
        {"mountPath": "/var/lib/rabbitmq", "name": vct_name}
    )


def upgrade_to_parallel(statefulset):
    statefulset["apiVersion"] = "apps/v1"

    if os.environ.get("PARALLEL_START"):
        statefulset["spec"]["podManagementPolicy"] = "Parallel"

    statefulset['spec']['updateStrategy'] = {'type': 'OnDelete'}

    statefulset["spec"]["template"]["spec"]["serviceAccountName"] = "rabbitmq"

    if os.getenv("POD_AFFINITY_TERM") == "required":
        statefulset["spec"]["template"]["spec"]["affinity"]["podAntiAffinity"].pop(
            "preferredDuringSchedulingIgnoredDuringExecution")
        statefulset["spec"]["template"]["spec"]["affinity"]["podAntiAffinity"].update(
            {
                "requiredDuringSchedulingIgnoredDuringExecution": [
                    {
                        "labelSelector": {
                            "matchExpressions": [
                                {
                                    "key": "app",
                                    "operator": "In",
                                    "values": [
                                        "${APPLICATION}"
                                    ]
                                }
                            ]
                        },
                        "topologyKey": "kubernetes.io/hostname"
                    }
                ]
            })


def inject_non_persistent_probes_15(statefulset):
    statefulset["spec"]["template"]["spec"]["containers"][0]["livenessProbe"] = {
        "exec": {
            "command": [
                "bash",
                "-c",
                """
                if [ -f /tmp/BACKUP_FLAG_FILE ]; then
                         echo "executing rabbitmq-diagnostics ping -q"
                        rabbitmq-diagnostics ping -q;
                else
                    rabbitmq-diagnostics -q check_running && rabbitmq-diagnostics -q check_local_alarms
                fi
                """
            ]
        },
        "initialDelaySeconds": 10,
        "timeoutSeconds": 5,
        "periodSeconds": 30,
        "successThreshold": 1,
        "failureThreshold": 30
    }

    statefulset["spec"]["template"]["spec"]["containers"][0]["readinessProbe"] = {
        "exec": {
            "command": [
                "bash",
                "-c",
                """
                if [ -f /tmp/BACKUP_FLAG_FILE ]; then
                         echo "executing rabbitmq-diagnostics ping -q"
                        rabbitmq-diagnostics ping -q;
                else
                    rabbitmq-diagnostics -q check_running && rabbitmq-diagnostics -q check_local_alarms
                fi
                """
            ]
        },
        "initialDelaySeconds": 20,
        "timeoutSeconds": 5,
        "periodSeconds": 30,
        "successThreshold": 1,
        "failureThreshold": 30
    }


def inject_non_persistent_probes_311(statefulset):
    statefulset["spec"]["template"]["spec"]["containers"][0]["readinessProbe"] = {
        "exec": {
            "command": [
                "/bin/bash",
                "-c",
                """
                if [ -f /tmp/BACKUP_FLAG_FILE ]; then
                         echo "executing rabbitmq-diagnostics ping -q"
                        rabbitmq-diagnostics ping -q;
                elif [ -f /var/lib/rabbitmq/started_at_least_once ]; then
                    echo "executing rabbitmq-diagnostics ping -q"
                    rabbitmq-diagnostics ping -q;
                elif rabbitmqctl await_online_nodes $(( ( $(echo -n ${MY_POD_NAME##*-}) + 1 ) / 2 + 1 )) -t 1 ; then
                    echo "awaiting nodes succeeded"
                    touch /var/lib/rabbitmq/started_at_least_once
                elif rabbitmq-diagnostics -q check_running && rabbitmq-diagnostics -q check_local_alarms ; then
                    echo "manually resetting rabbit"
                    rabbitmqctl stop_app
                    rabbitmqctl reset
                    rabbitmqctl start_app
                    exit 1
                else    echo "probe failed"
                    exit 1
                fi
                """
            ]
        },
        "initialDelaySeconds": 10,
        "timeoutSeconds": 15,
        "periodSeconds": 30,
        "successThreshold": 1,
        "failureThreshold": 30
    }


def inject_openshift_1_5_fix(statefulset):
    statefulset["spec"]["template"]["spec"]["containers"][0]["livenessProbe"]["initialDelaySeconds"] = 180


def inject_pvc(template, statefulset, is_pv_by_labels=False):
    statefulset["spec"]["template"]["spec"]["volumes"].append(
        {
            "name": "rmqvolumedatamount",
            "persistentVolumeClaim": {"claimName": "${PVC_NAME}"}
        }
    )
    statefulset["spec"]["template"]["spec"]["containers"][0]["volumeMounts"].append(
        {"mountPath": "/var/lib/rabbitmq", "name": "rmqvolumedatamount"}
    )

    statefulset["spec"]["template"]["spec"]["nodeSelector"] = {"kubernetes.io/hostname": "${PV_NODE}"}

    del statefulset["spec"]["template"]["spec"]["containers"][0]["lifecycle"]["preStop"]
# start hostpath probes
    statefulset["spec"]["template"]["spec"]["containers"][0]["livenessProbe"] = {
        "exec": {
            "command": [
                "/bin/bash",
                "-c",
                """
if [ -f /tmp/BACKUP_FLAG_FILE ]; then
                         echo "executing rabbitmq-diagnostics ping -q"
                        rabbitmq-diagnostics ping -q;
                        exit 0
fi

rabbitmq-diagnostics -q check_running && rabbitmq-diagnostics -q check_local_alarms || exit 1

if [[ "$HOSTNAME" != "rmqlocal-0-0" ]] && [[ ! -f /var/lib/rabbitmq/started_at_least_once ]] ; then
    FD_OUTPUT="/proc/1/fd/1"
    # result is empty when current node didn't join with the zero node
    CLUSTER_STATE="$(rabbitmqctl cluster_status | grep -c rmqlocal-0-0)"
    echo "Cluster state: ${CLUSTER_STATE}" &> "${FD_OUTPUT}"

    if [[ "${CLUSTER_STATE}" -gt 0 ]];
    then
        echo "Current node ${HOSTNAME} joined with the zero node" &> "${FD_OUTPUT}"
        touch /var/lib/rabbitmq/started_at_least_once
        exit 0
    fi

    echo "Try to join with zero node" &> "${FD_OUTPUT}"

    rabbitmqctl stop_app &> "${FD_OUTPUT}"
    rabbitmqctl join_cluster rabbit@rmqlocal-0-0 &> "${FD_OUTPUT}"
    rabbitmqctl start_app &> "${FD_OUTPUT}"

    echo "Current node ${HOSTNAME} joined with the zero node" &> "${FD_OUTPUT}"
    exit 1
fi
                """
            ]
        },
        "initialDelaySeconds": 10,
        "timeoutSeconds": 15,
        "periodSeconds": 30,
        "successThreshold": 1,
        "failureThreshold": 30
    }

    statefulset["spec"]["template"]["spec"]["containers"][0]["readinessProbe"] = {
        "exec": {
            "command": [
                "rabbitmq-diagnostics",
                "ping",
                "-q"
            ]
        },
        "initialDelaySeconds": 10,
        "timeoutSeconds": 5,
        "periodSeconds": 10,
        "successThreshold": 1,
        "failureThreshold": 90
    }
# finish hostpath probes
    for env in statefulset["spec"]["template"]["spec"]["containers"][0]["env"]:
        if env['name'] == 'RABBITMQ_NODENAME':
            env['value'] = 'rabbit@$(BROKER_NAME_INTERNAL)-0'

    internal_service = template["objects"][1]

    del internal_service["spec"]["clusterIP"]
    internal_service["metadata"]["name"] = "${BROKER_NAME_INTERNAL}-0"

    if is_pv_by_labels:
        pv_conf = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": "${PVC_NAME}",
                "labels": {
                    "app": "${APPLICATION}",
                    "rabbitmq-app": "${BROKER_NAME_INTERNAL}"
                }
            },
            "spec": {
                "accessModes": [
                    "ReadWriteOnce"
                ],
                "storageClassName": "${PV_STORAGE_CLASS}",
                "selector": {
                    "matchLabels": {"${LABEL_KEY}": "${LABEL_VALUE}"}
                },
                "resources": {
                    "requests": {
                        "storage": "${PVC_CAPACITY}"
                    }
                }
            }
        }
        if "PV_LABELS_STORAGE_CLASSES" not in os.environ:
            if "PV_LABELS_STORAGE_CLASS" not in os.environ or os.environ.get("PV_LABELS_STORAGE_CLASS") == '':
                pv_conf['spec'].pop('storageClassName')
        template["objects"].append(pv_conf)
    else:
        template["objects"].append(
            {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {
                    "annotations": {
                        # TODO: this annotation will not be supported in a future Kubernetes release, storageClassName attribute should be used instead.
                        "volume.beta.kubernetes.io/storage-class": "${PV_STORAGE_CLASS}"
                    },
                    "name": "${PVC_NAME}",
                    "labels": {
                        "app": "${APPLICATION}",
                        "rabbitmq-app": "${BROKER_NAME_INTERNAL}"
                    }
                },
                "spec": {
                    "accessModes": [
                        "ReadWriteOnce"
                    ],
                    "resources": {
                        "requests": {
                            "storage": "${PVC_CAPACITY}"
                        }
                    },
                    "volumeName": "${PV}"
                }
            }
        )

    del statefulset["spec"]["template"]["spec"]["affinity"]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process the rabbitmq_template.yaml file to the rabbitmq.yaml')
    parser.add_argument('--template-folder', dest='path_to_template', help="Path to the rabbitmq.json")
    parser.add_argument('command', choices=['inject_volume_claim_template', 'inject_pvc', 'upgrade_to_parallel',
                                            'inject_non_persistent_probes_15', 'inject_non_persistent_probes_311',
                                            'inject_pvc_by_labels'])

    args = parser.parse_args()

    if not args.path_to_template:
        print('Specify path to RabbitMQ template')
        sys.exit(1)

    path_to_rabbitmq = args.path_to_template + 'rabbitmq.yaml'
    path_to_rabbitmq_template = args.path_to_template + 'rabbitmq_template.yaml'

    if os.path.exists(path_to_rabbitmq):
        print('Using the rabbimq.yaml file')
        template_path = path_to_rabbitmq
    else:
        print('Using the rabbimq_template.yaml file')
        template_path = path_to_rabbitmq_template

    with open(template_path, 'r') as f:
        template_yaml = yaml.load(f)

    template_statefulset = template_yaml["objects"][0]

    if args.command == 'inject_volume_claim_template':
        inject_volume_claim_template(template_statefulset)
    elif args.command == 'upgrade_to_parallel':
        upgrade_to_parallel(template_statefulset)
    elif args.command == 'inject_pvc':
        inject_pvc(template_yaml, template_statefulset)
    elif args.command == 'inject_pvc_by_labels':
        inject_pvc(template_yaml, template_statefulset, is_pv_by_labels=True)
    elif args.command == 'inject_non_persistent_probes_15':
        inject_non_persistent_probes_15(template_statefulset)
    elif args.command == 'inject_non_persistent_probes_311':
        inject_non_persistent_probes_311(template_statefulset)
    else:
        print('Unexpected command: {}'.format(args.command))
        sys.exit(1)

    kube_version = os.getenv("KUBE_VERSION")
    if (re.search(r"v1.5", kube_version)):
        inject_openshift_1_5_fix(template_statefulset)

    with open(path_to_rabbitmq, 'w') as f:
        yaml.dump(template_yaml, f)
