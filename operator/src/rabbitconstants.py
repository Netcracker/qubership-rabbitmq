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

from kubernetes.client import V1Probe, V1ExecAction

rabbitmq_hostpath_liveness_probe_command = ['bin/bash', '-c',
                                            # TODO $(get_user):$(get_password) was changed to guest:guest
                                            """

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

rabbitmq_hostpath_readiness_probe_command = ['rabbitmq-diagnostics', 'ping', '-q']

rabbitmq_storageclass_liveness_probe_command = ['bin/bash', '-c', """
if [ -f /var/lib/rabbitmq/started_at_least_once ]; then
    echo "executing complete version of rabbitmq status check"
    if rabbitmq-diagnostics -q check_running && rabbitmq-diagnostics -q check_local_alarms ; then
        :
    else
        echo "http-liveness probe failed"
        exit 1
    fi
elif rabbitmqctl await_online_nodes $(( ( $(echo -n ${MY_POD_NAME##*-}) + 1 ) / 2 + 1 )) -t 1 ; then
    echo "awaiting nodes succeeded"
else echo "awaiting nodes liveness probe failed"
    exit 1
fi
"""
                                                ]

rabbitmq_storageclass_readiness_probe_command = ['bin/bash', '-c', """
if [ -f /var/lib/rabbitmq/started_at_least_once ]; then
    echo "executing rabbitmq-diagnostics ping -q"
    rabbitmq-diagnostics ping -q;
elif rabbitmqctl await_online_nodes $(( ( $(echo -n ${MY_POD_NAME##*-}) + 1 ) / 2 + 1 )) -t 1 ; then
    echo "awaiting nodes succeeded"
    touch /var/lib/rabbitmq/started_at_least_once
else
    echo "probe failed"
    exit 1
fi
"""]

rabbitmq_storage_class_pre_stop_command = ['bin/bash', '-c', """
                    rabbitmqctl stop;
                     if [ ! -f /var/lib/rabbitmq/started_at_least_once ]; then
                        rm -r /var/lib/rabbitmq/*
                    fi
"""]

storageclass_readiness_probe = V1Probe(failure_threshold=90,
                                       initial_delay_seconds=10,
                                       period_seconds=10, success_threshold=1,
                                       timeout_seconds=5,
                                       _exec=V1ExecAction(
                                           command=rabbitmq_storageclass_readiness_probe_command))

storageclass_liveness_probe = V1Probe(failure_threshold=30,
                                      initial_delay_seconds=10,
                                      period_seconds=30, success_threshold=1,
                                      timeout_seconds=15,
                                      _exec=V1ExecAction(
                                          command=rabbitmq_storageclass_liveness_probe_command))

hostpath_readiness_probe = V1Probe(failure_threshold=90,
                                   initial_delay_seconds=10,
                                   period_seconds=10, success_threshold=1,
                                   timeout_seconds=5,
                                   _exec=V1ExecAction(
                                       command=rabbitmq_hostpath_readiness_probe_command))

hostpath_liveness_probe = V1Probe(failure_threshold=30,
                                  initial_delay_seconds=10,
                                  period_seconds=30, success_threshold=1,
                                  timeout_seconds=15,
                                  _exec=V1ExecAction(
                                      command=rabbitmq_hostpath_liveness_probe_command))
