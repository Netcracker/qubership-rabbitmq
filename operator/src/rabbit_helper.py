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

import requests
import logging

logger = logging.getLogger(__name__)


class RabbitHelper:
    def __init__(self, user, password, rabbitmq_url, ssl=False):
        self._user = user
        self._password = password
        self._rabbitmq_url = rabbitmq_url
        self._ssl = ssl

    def is_cluster_alive(self, replicas):
        try:
            r = requests.get(url=f'{self._rabbitmq_url}/api/nodes', auth=(self._user, self._password), verify=self._ssl, timeout=2)
            nodes = r.json()
            # node_count = nodes.count(True)
            if len(nodes) == int(replicas):
                return True
            logger.warning("rabbit is not ready yet, node_count = :" + str(node_count))
            return False
        except Exception as e:
            logger.warning("rabbit is not ready yet:" + str(e))
            return False


def join_maps(side: dict, main: dict) -> dict:
    res = {}
    if side is not None:
        for key in side.keys():
            res[key] = side[key]
    if main is not None:
        for key in main.keys():
            res[key] = main[key]
    return res
