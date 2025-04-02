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

import json
import os
import re

import requests


def is_rabbitmq_pod(podname):
    pattern1 = re.compile(r'^rmqlocal-[0-9]+$')
    pattern2 = re.compile(r'^rmqlocal-[0-9]+-0$')
    return pattern1.match(podname) or pattern2.match(podname)


def main():
    host = os.getenv("KUBERNETES_SERVICE_HOST")
    port = os.getenv("KUBERNETES_SERVICE_PORT_HTTPS")
    verify = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
    token = open("/var/run/secrets/kubernetes.io/serviceaccount/token").read()
    headers = {"Authorization": f"Bearer {token}"}
    namespace = os.getenv("WATCH_NAMESPACE")
    url = f'https://{host}:{port}'
    payload = {"gracePeriodSeconds": 0}
    print(f'Get request URL: {url}/api/v1/namespaces/{namespace}/pods')
    response = requests.get(f'{url}/api/v1/namespaces/{namespace}/pods', verify=verify, headers=headers)
    print(f'Request response code: {response}')
    for pod in response.json()["items"]:
        name = pod["metadata"]["name"]
        if is_rabbitmq_pod(name):
            print(f'Delete request URL: {url}/api/v1/namespaces/{namespace}/pods/{name}')
            response = requests.delete(
                f'{url}/api/v1/namespaces/{namespace}/pods/{name}',
                verify=verify,
                headers=headers,
                data=json.dumps(payload)
            )
            print(f'Request response code: {response}')


if __name__ == '__main__':
    main()
