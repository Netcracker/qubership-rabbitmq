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

import sys
import json


def is_available():
    json_resp = json.loads(sys.argv[1])
    spec_replicas = json_resp['spec']['replicas']
    current_replicas = json_resp['status']['replicas']
    updated_replicas = json_resp['status']['updatedReplicas']
    available_replicas = json_resp['status']['availableReplicas']

    if current_replicas == 0:
        sys.exit(1)
    elif current_replicas <= updated_replicas \
            and available_replicas >= updated_replicas >= spec_replicas:
        sys.exit(0)
    else:
        sys.exit(1)


def start():
    is_available()


if __name__ == "__main__":
    start()
