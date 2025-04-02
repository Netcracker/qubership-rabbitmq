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

_GRAPH['rabbitmq_connections'] = Gauge(
    'rabbitmq_connections',
    'Connections',
    ['rabbitmq_cluster', 'rabbitmq_node']
)


def parse_connections(connections, nodes, cluster_name):
    connections_count = {}

    for node in nodes:
        if not node["name"] in connections_count:
            connections_count[node["name"]] = 0

    for connection in connections:
        connections_count[connection["node"]] += 1

    for node in connections_count:
        _GRAPH['rabbitmq_connections'].labels(cluster_name, node).\
            set(connections_count[node])

    res = []

    for key in _GRAPH:
        res.append(prometheus_client.generate_latest(_GRAPH[key]))

    return res
