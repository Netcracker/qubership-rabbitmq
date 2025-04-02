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

_GRAPH['rabbitmq_channel_messages_published_total'] = Gauge(
    'rabbitmq_channel_messages_published_total',
    'Message publishing rate',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channel_messages_redelivered_total'] = Gauge(
    'rabbitmq_channel_messages_redelivered_total',
    'Outgoing messages / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channel_messages_delivered_total'] = Gauge(
    'rabbitmq_channel_messages_delivered_total',
    'Outgoing messages / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channel_messages_delivered_ack_total'] = Gauge(
    'rabbitmq_channel_messages_delivered_ack_total',
    'Outgoing messages / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channel_get_total'] = Gauge(
    'rabbitmq_channel_get_total',
    'Outgoing messages / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channel_get_ack_total'] = Gauge(
    'rabbitmq_channel_get_ack_total',
    'Outgoing messages / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channel_messages_confirmed_total'] = Gauge(
    'rabbitmq_channel_messages_confirmed_total',
    'Messages confirmed to publishers / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channel_messages_unroutable_dropped_total'] = Gauge(
    'rabbitmq_channel_messages_unroutable_dropped_total',
    'Unroutable messages dropped / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channel_messages_unroutable_returned_total'] = Gauge(
    'rabbitmq_channel_messages_unroutable_returned_total',
    'Unroutable messages returned to publishers / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channel_messages_unconfirmed'] = Gauge(
    'rabbitmq_channel_messages_unconfirmed',
    'Messages unconfirmed to publishers / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channel_messages_acked_total'] = Gauge(
    'rabbitmq_channel_messages_acked_total',
    'Messages acknowledged / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channel_get_empty_total'] = Gauge(
    'rabbitmq_channel_get_empty_total',
    'Polling operations that yield no result / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channel_consumers'] = Gauge(
    'rabbitmq_channel_consumers',
    'Publishers and Consumers',
    ['rabbitmq_cluster', 'rabbitmq_node']
)


def parse_channels(channels, nodes, cluster_name):
    published_total = {}
    redelivered_total = {}
    delivered_ack = {}
    delivered_no_ack = {}
    get_ack = {}
    get_no_ack = {}
    confirmed = {}
    ack = {}
    drop_unroutable = {}
    return_unroutable = {}
    unconfirmed = {}
    empty = {}
    consumers = {}
    connections = {}

    for node in nodes:
        if not node["name"] in published_total:
            published_total[node["name"]] = 0
            redelivered_total[node["name"]] = 0
            delivered_ack[node["name"]] = 0
            delivered_no_ack[node["name"]] = 0
            get_ack[node["name"]] = 0
            get_no_ack[node["name"]] = 0
            confirmed[node["name"]] = 0
            ack[node["name"]] = 0
            drop_unroutable[node["name"]] = 0
            return_unroutable[node["name"]] = 0
            unconfirmed[node["name"]] = 0
            empty[node["name"]] = 0
            consumers[node["name"]] = 0
            connections[node["name"]] = 0

    for channel in channels:
        unconfirmed[channel["node"]] += int(
            channel.get("messages_unconfirmed", 0))
        consumers[channel["node"]] += int(
            channel.get("consumer_count", 0))
        if channel.get("message_stats"):
            published_total[channel["node"]] += int(
                channel["message_stats"].get("publish", 0))
            redelivered_total[channel["node"]] += int(
                channel["message_stats"].get("redeliver", 0))
            delivered_ack[channel["node"]] += int(
                channel["message_stats"].get("deliver", 0))
            delivered_no_ack[channel["node"]] += int(
                channel["message_stats"].get("deliver_no_ack", 0))
            get_ack[channel["node"]] += int(
                channel["message_stats"].get("get", 0))
            get_no_ack[channel["node"]] += int(
                channel["message_stats"].get("get_no_ack", 0))
            confirmed[channel["node"]] += int(
                channel["message_stats"].get("confirm", 0))
            ack[channel["node"]] += int(
                channel["message_stats"].get("ack", 0))
            drop_unroutable[channel["node"]] += int(
                channel["message_stats"].get("drop_unroutable", 0))
            return_unroutable[channel["node"]] += int(
                channel["message_stats"].get("return_unroutable", 0))
            empty[channel["node"]] += int(
                channel["message_stats"].get("get_empty", 0))

    for node in published_total:
        _GRAPH['rabbitmq_channel_messages_published_total'].labels(
            cluster_name, node).set(published_total[node])
        _GRAPH['rabbitmq_channel_messages_redelivered_total'].labels(
            cluster_name, node).set(redelivered_total[node])
        _GRAPH['rabbitmq_channel_messages_delivered_ack_total'].labels(
            cluster_name, node).set(delivered_ack[node])
        _GRAPH['rabbitmq_channel_messages_delivered_total'].labels(
            cluster_name, node).set(delivered_no_ack[node])
        _GRAPH['rabbitmq_channel_get_ack_total'].labels(
            cluster_name, node).set(get_ack[node])
        _GRAPH['rabbitmq_channel_get_total'].labels(
            cluster_name, node).set(get_no_ack[node])
        _GRAPH['rabbitmq_channel_messages_confirmed_total'].labels(
            cluster_name, node).set(confirmed[node])
        _GRAPH['rabbitmq_channel_messages_acked_total'].labels(
            cluster_name, node).set(ack[node])
        _GRAPH['rabbitmq_channel_messages_unroutable_dropped_total'].labels(
            cluster_name, node).set(drop_unroutable[node])
        _GRAPH['rabbitmq_channel_messages_unroutable_returned_total'].labels(
            cluster_name, node).set(return_unroutable[node])
        _GRAPH['rabbitmq_channel_messages_unconfirmed'].labels(
            cluster_name, node).set(unconfirmed[node])
        _GRAPH['rabbitmq_channel_get_empty_total'].labels(
            cluster_name, node).set(empty[node])
        _GRAPH['rabbitmq_channel_consumers'].labels(
            cluster_name, node).set(consumers[node])

    res = []

    for key in _GRAPH:
        res.append(prometheus_client.generate_latest(_GRAPH[key]))
    return res
