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

import time
import urllib3
import hashlib
from robot.api import logger
import base64
import os
from PlatformLibrary import PlatformLibrary
from kubernetes import client as client, config as k8s_config
from kubernetes.client import V1ObjectMeta, V1Secret

try:
    k8s_config.load_incluster_config()
    k8s_client = client.ApiClient()
except k8s_config.ConfigException as e:
    k8s_client = k8s_config.new_client_from_config()

secret_name = 'rabbitmq-default-secret'
cr_version = "v2"


class CloudResourcesLibrary(object):

    def __init__(self, managed_by_operator="true"):

        urllib3.disable_warnings()
        self._api_client = k8s_client
        self.k8s_lib = PlatformLibrary(managed_by_operator)
        self.namespace = os.environ.get("NAMESPACE")
        self._v1_apps_api = client.CoreV1Api(self._api_client)
        self._custom_objects_api = client.CustomObjectsApi(self._api_client)

    def change_rabbitmq_password_with_operator(self, username, password):
        secret = self.k8s_lib.get_secret(secret_name, self.namespace)

        secret.data['user'] = base64.b64encode(username.encode()).decode()
        secret.data['password'] = base64.b64encode(password.encode()).decode()

        self._v1_apps_api.patch_namespaced_secret(name=secret_name, namespace=self.namespace, body=secret)

        cr = self.get_custom_resource()
        secret_change = hashlib.sha256(base64.b64encode(str(secret.data).encode())).hexdigest()
        cr['spec']['rabbitmq']['secret_change'] = secret_change
        self.update_custom_resource(cr)

    def get_custom_resource(self):
        return self.k8s_lib.get_namespaced_custom_object_status(
            group='qubership.org',
            version=cr_version,
            namespace=self.namespace,
            plural='rabbitmqservices',
            name='rabbitmq-service'
        )

    def set_secret_change_field(self, secret_change):
        cr = self.get_custom_resource()
        cr['spec']['rabbitmq']['secret_change'] = secret_change
        self.update_custom_resource(cr)

    def update_custom_resource(self, body):

        self._custom_objects_api.patch_namespaced_custom_object(
            group='qubership.org',
            version=cr_version,
            namespace=self.namespace,
            plural='rabbitmqservices',
            name='rabbitmq-service',
            body=body
        )

    def get_secret_change_value(self):
        cr = self.get_custom_resource()
        return cr['spec']['rabbitmq']['secret_change']

    def get_password_from_secret(self, secret):

        return str(base64.b64decode(secret.data.get('password')), 'utf-8')

    def get_stateful_sets(self):

        return self.k8s_lib.get_stateful_set_names_by_label(
            namespace=self.namespace,
            label_value='rmqlocal',
            label_name='app'
        )

    def is_statefulset_single(self, statefulsets):

        if 'rmqlocal-' in statefulsets[0]:
                return False
        elif 'rmqlocal' == statefulsets[0]:
                return True

    def get_pods_by_mask(self, pods: list, mask: str):

        masked_pods = []
        for pod in pods:
            if mask in pod.metadata.name:
                masked_pods.append(pod.metadata.name)
        return masked_pods

    def get_rabbitmq_ready_replicas(self):

        statefulsets = self.get_stateful_sets()
        sum = 0
        for ss in statefulsets:
            replicas = self.k8s_lib.get_stateful_set_ready_replicas_count(ss, self.namespace)
            if replicas is None:
                time.sleep(15)
                replicas = self.k8s_lib.get_stateful_set_ready_replicas_count(ss, self.namespace)
            sum += replicas
        return sum

    def get_rabbitmq_replicas(self):

        statefulsets = self.get_stateful_sets()
        status = self.is_statefulset_single(statefulsets)
        if status:
            replicas = self.k8s_lib.get_stateful_set_replicas_count(
                statefulsets[0],
                self.namespace
            )
            return replicas
        else:
            sum = 0
            for ss in statefulsets:
                replicas = self.k8s_lib.get_stateful_set_replicas_count(ss, self.namespace)
                if replicas is None:
                    time.sleep(8)
                    replicas = self.k8s_lib.get_stateful_set_replicas_count(ss, self.namespace)
                sum += replicas
            return sum

    def change_rabbitmq_password_with_function(
            self,
            pod_name: str,
            new_password: str
    ):

        command = ['/bin/sh', '-c', 'change_password  $RABBITMQ_DEFAULT_USER ' + str(new_password)]
        resp, error = self.k8s_lib.execute_command_in_pod(
            name=pod_name,
            namespace=self.namespace,
            command=command,
            shell='/bin/sh'
        )
        time.sleep(10)
        return resp, error

    def force_kill(self, pod_name: str):

        self.k8s_lib.delete_pod_by_pod_name(
            name=pod_name,
            namespace=self.namespace
        )

    def force_kill_all_pods(self, pod_names: list, order: str):

        if order == 'at_once':
            pod_name = self.get_random_pod(pod_names)
            self.force_kill(pod_name)
            return

        elif order not in ['asc', 'desc', 'part']:
            raise ValueError(order)

        pod_names = sorted(pod_names)

        logger.debug(f'Sorted pod names: {pod_names}')

        if order == 'desc':
            pod_names = list(reversed(pod_names))
        elif order == 'part':
            pod_names = pod_names[:1]

        for pod_name in pod_names:
            self.force_kill(pod_name)
            time.sleep(60)

    def get_number_of_statefulsets(self, app_label=''):

        label_selector = ''
        if app_label:
            label_selector = f'app={app_label}'

        return len(
            self.k8s_lib.list_namespaced_stateful_set(
                namespace=self._os_workspace,
                label_selector=label_selector).items
        )

    def check_number_of_statefulsets(self, expected_number, app_label=''):

        number_of_statefulsets = self.get_number_of_statefulsets(app_label)
        if number_of_statefulsets != expected_number:
            raise Exception(
                f'Expected {expected_number} statfulsets,'
                f'but got {number_of_statefulsets}'
            )

    def get_random_pod(self, pod_names: list):

        return pod_names[len(pod_names) - 1]

    def start_node(self, pod_name: str):

        command = 'rabbitmqctl start_app'
        return self.k8s_lib.execute_command_in_pod(
            name=pod_name,
            namespace=self.namespace,
            command=command,
            shell='/bin/sh'
        )

    def stop_node(self, pod_name: str):

        command = 'rabbitmqctl stop_app'
        return self.k8s_lib.execute_command_in_pod(
            name=pod_name,
            namespace=self.namespace,
            command=command,
            shell='/bin/sh'
        )

    def set_policy_ha_all(self, pod_name: str, vhost: str):

        command = 'rabbitmqctl set_policy --vhost ' + vhost + \
                  ' ha-all \".*\" \'{"ha-mode":"all","ha-sync-mode":"automatic"}\''

        return self.k8s_lib.execute_command_in_pod(
            name=pod_name,
            namespace=self.namespace,
            command=command,
            shell='/bin/sh'
        )

    def kill_pod_multiple_times(self, pod_name: str, kill_number: int, period: int):

        for i in range(kill_number):
            self.force_kill(pod_name)
            time.sleep(period)
