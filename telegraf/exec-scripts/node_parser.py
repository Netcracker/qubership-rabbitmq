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

import os

import prometheus_client
from prometheus_client import Gauge

_GRAPH = {}

_GRAPH['rabbitmq_cluster_state'] = Gauge(
    'rabbitmq_cluster_state',
    'RabbitMQ\'s cluster state',
    ['rabbitmq_cluster']
)

_GRAPH['rabbitmq_disk_space_available_bytes'] = Gauge(
    'rabbitmq_disk_space_available_bytes',
    'Disk space available before publishers blocked',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_process_max_fds'] = Gauge(
    'rabbitmq_process_max_fds',
    'File descriptors max available',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_process_open_fds'] = Gauge(
    'rabbitmq_process_open_fds',
    'File descriptors available',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_resident_memory_limit_bytes'] = Gauge(
    'rabbitmq_resident_memory_limit_bytes',
    'Memory limit',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_process_resident_memory_bytes'] = Gauge(
    'rabbitmq_process_resident_memory_bytes',
    'Memory usage',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_build_info'] = Gauge(
    'rabbitmq_build_info',
    'Nodes',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channels'] = Gauge(
    'rabbitmq_channels',
    'Channels',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channels_opened_total'] = Gauge(
    'rabbitmq_channels_opened_total',
    'Channels opened',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_channels_closed_total'] = Gauge(
    'rabbitmq_channels_closed_total',
    'Channels closed',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_queues_declared_total'] = Gauge(
    'rabbitmq_queues_declared_total',
    'Queues declared / s',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_queues_created_total'] = Gauge(
    'rabbitmq_queues_created_total',
    'Queues created',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_queues_deleted_total'] = Gauge(
    'rabbitmq_queues_deleted_total',
    'Queues deleted',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_connections_opened_total'] = Gauge(
    'rabbitmq_connections_opened_total',
    'Connections opened',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_connections_closed_total'] = Gauge(
    'rabbitmq_connections_closed_total',
    'Connections closed',
    ['rabbitmq_cluster', 'rabbitmq_node']
)

_GRAPH['rabbitmq_node_count'] = Gauge(
    'rabbitmq_node_count',
    'Node count',
    ['rabbitmq_cluster']
)


def parse_nodes(nodes, cluster_name):
    rabbitmq_channels_opened = {}
    rabbitmq_channels_closed = {}
    node_count = 0
    desired_node_count = int(os.getenv('DESIRED_NODE_COUNT', 0))

    for node in nodes:
        rabbitmq_channels_opened[node["name"]] += 1

    if node_count == desired_node_count:
        status = 0
    else:
        if node_count == 0:
            status = 2
        else:
            status = 1

    for node in nodes:
        node_name = node["name"]
        _GRAPH['rabbitmq_disk_space_available_bytes'].labels(cluster_name,
                                                             node_name).set(
            node['disk_free'])
        _GRAPH['rabbitmq_process_open_fds'].labels(cluster_name,
                                                   node_name).set(
            node['fd_used'])
        _GRAPH['rabbitmq_process_max_fds'].labels(cluster_name,
                                                  node_name).set(
            node['fd_total'])
        _GRAPH['rabbitmq_resident_memory_limit_bytes'].labels(cluster_name,
                                                              node_name).set(
            node['mem_limit'])
        _GRAPH['rabbitmq_process_resident_memory_bytes'].labels(cluster_name,
                                                                node_name).set(
            node['mem_used'])
        _GRAPH['rabbitmq_queues_declared_total'].labels(cluster_name,
                                                        node_name).set(
            node['queue_declared'])
        _GRAPH['rabbitmq_queues_created_total'].labels(cluster_name,
                                                       node_name).set(
            node['queue_created'])
        _GRAPH['rabbitmq_queues_deleted_total'].labels(cluster_name,
                                                       node_name).set(
            node['queue_deleted'])
        _GRAPH['rabbitmq_connections_opened_total'].labels(cluster_name,
                                                           node_name).set(
            node['connection_created'])
        _GRAPH['rabbitmq_connections_closed_total'].labels(cluster_name,
                                                           node_name).set(
            node['connection_closed'])
        rabbitmq_channels_opened[node_name] += int(node["channel_created"])
        rabbitmq_channels_closed[node_name] += int(node["channel_closed"])

    for node in rabbitmq_channels_opened:
        _GRAPH['rabbitmq_channels_opened_total'].labels(cluster_name, node). \
            set(rabbitmq_channels_opened[node])
        _GRAPH['rabbitmq_channels_closed_total'].labels(cluster_name, node). \
            set(rabbitmq_channels_closed[node])
        _GRAPH['rabbitmq_channels'].labels(cluster_name, node). \
            set(
            rabbitmq_channels_opened[node] - rabbitmq_channels_closed[node]
        )

    _GRAPH['rabbitmq_cluster_state'].labels(cluster_name). \
        set(status)

    _GRAPH['rabbitmq_node_count'].labels(cluster_name). \
        set(node_count)

    res = []

    for key in _GRAPH:
        res.append(prometheus_client.generate_latest(_GRAPH[key]))

    return res
