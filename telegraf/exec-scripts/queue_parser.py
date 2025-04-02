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

import prometheus_client
from prometheus_client import Gauge

_GRAPH = {}

_GRAPH['rabbitmq_queue_messages_ready'] = Gauge(
    'rabbitmq_queue_messages_ready',
    'Ready messages',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_queue_messages_unacked'] = Gauge(
    'rabbitmq_queue_messages_unacked',
    'Unacknowledged messages',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_queue_messages_published_total'] = Gauge(
    'rabbitmq_queue_messages_published_total',
    'Messages routed to queues / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_queues'] = Gauge(
    'rabbitmq_queues',
    'Queues',
    ['rabbitmq_cluster', 'rabbitmq_node']
)


def parse_queues(queues, nodes, cluster_name):
    message_ready_total = {}
    message_unacked_total = {}
    publish = {}
    queue_count = {}

    for node in nodes:
        if not node["name"] in message_ready_total:
            message_ready_total[node["name"]] = 0
            message_unacked_total[node["name"]] = 0
            publish[node["name"]] = 0
            queue_count[node["name"]] = 0

    for queue in queues:
        queue_count[queue["node"]] += 1
        message_ready_total[queue["node"]] += int(
            queue.get("messages_ready", 0))
        message_unacked_total[queue["node"]] += int(
            queue.get("messages_unacknowledged", 0))
        if queue.get("message_stats"):
            publish[queue["node"]] += int(
                queue["message_stats"].get("publish", 0))

    for node in message_ready_total:
        _GRAPH['rabbitmq_queue_messages_unacked'].labels(cluster_name, node).\
            set(message_unacked_total[node])
        _GRAPH['rabbitmq_queue_messages_ready'].labels(cluster_name, node).\
            set(message_ready_total[node])
        _GRAPH['rabbitmq_queue_messages_published_total'].\
            labels(cluster_name, node).set(publish[node])
        _GRAPH['rabbitmq_queues'].\
            labels(cluster_name, node).set(queue_count[node])

    res = []

    for key in _GRAPH:
        res.append(prometheus_client.generate_latest(_GRAPH[key]))

    return res
