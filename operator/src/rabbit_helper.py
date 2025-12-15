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

from email.utils import quote
from email.utils import quote
import requests
import logging
from dataclasses import dataclass
import json
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class ShovelInfo:
    node: str
    timestamp: str
    name: str
    vhost: str
    type: str
    state: str
    src_uri: str
    src_protocol: str
    dest_protocol: str
    dest_uri: str
    src_queue: str
    dest_queue: str
    blocked_status: str

@dataclass
class ShovelInfo:
    node: str
    timestamp: str
    name: str
    vhost: str
    type: str
    state: str
    src_uri: str
    src_protocol: str
    dest_protocol: str
    dest_uri: str
    src_queue: str
    dest_queue: str
    blocked_status: str

class RabbitHelper:
    def __init__(self, user, password, rabbitmq_url, ssl=False):
        self._user = user
        self._password = password
        self._rabbitmq_url = rabbitmq_url
        self._ssl = ssl

    def is_cluster_alive(self, replicas):
        try:
            r = requests.get(url=f'{self._rabbitmq_url}/api/nodes', auth=(self._user, self._password), verify=self._ssl)
            nodes = list(map(lambda x: x['running'], r.json()))
            node_count = nodes.count(True)
            if node_count == int(replicas):
                return True
            logger.warning("rabbit is not ready yet, node_count = :" + str(node_count))
            return False
        except Exception as e:
            logger.warning("rabbit is not ready yet:" + str(e))
            return False
    
    def shovel_list(self) -> list[ShovelInfo]:
        try:
            r = requests.get(url=f'{self._rabbitmq_url}/api/shovels', auth=(self._user, self._password), verify=self._ssl)
            if r.status_code == 200:
                shovels = []
                for shovel_data in r.json():
                    shovel_info = ShovelInfo(**shovel_data)
                    shovels.append(shovel_info)
                return shovels
            logger.warning("rabbit shovel list is not ready yet, status code = :" + str(r.status_code))
            return []
        except Exception as e:
            logger.warning("rabbit shovel list is not ready yet:" + str(e))
            return []
        
    def validate_shovel(self, shovel: ShovelInfo):
        encoded_vhost = quote(shovel.vhost, safe='')
        encoded_name = quote(shovel.name, safe='')
        try:
            r = requests.get(url=f'{self._rabbitmq_url}/api/shovels/{encoded_vhost}/{encoded_name}', auth=(self._user, self._password), verify=self._ssl)
            if r.status_code == 200:
                return True
            logger.warning("rabbit shovel info is not ready yet, status code = :" + str(r.status_code))
            return False
        except Exception as e:
            logger.warning("rabbit shovel info is not ready yet:" + str(e))
            return False
    
    def is_shovel_alive(self, alive_percentage):
        try:
            shovels = self.shovel_list()
            total_shovels = len(shovels)
            # todo: handle zero shovels case probably no shovel created yet
            if total_shovels == 0:
                logger.info("No shovels found. Skipping shovel health check.")
                return True
            
            running_shovels = 0
            for shovel in shovels:
                valid = self.validate_shovel(shovel)
                if shovel.state == "running" and valid:
                    running_shovels += 1
                
                if not valid:
                    logger.warning(f"Shovel {shovel.name} in vhost {shovel.vhost} is not running or not valid.")
                    return False
                
            alive_ratio = running_shovels / total_shovels
            if alive_ratio >= alive_percentage:
                return True
            return False
        except Exception as e:
            logger.warning("rabbit shovel is not ready yet:" + str(e))
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
