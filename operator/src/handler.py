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

import base64
import logging
import os
import pprint
import re
import time
from time import sleep
from unittest import result
from distutils import util

import kopf
import requests
from kubernetes import client as client, config as k8s_config
from kubernetes.client import V1ObjectMeta, V1EnvVar, V1Container, V1PodSpec, \
    V1PodTemplateSpec, V1TCPSocketAction, V1ContainerPort, \
    V1ExecAction, V1EnvVarSource, V1ObjectFieldSelector, V1VolumeMount, \
    V1ResourceRequirements, V1SecretKeySelector, \
    V1Volume, V1ConfigMapVolumeSource, V1KeyToPath, V1ConfigMap, V1Lifecycle, \
    V1Handler, V1Service, V1ServiceSpec, \
    V1ServicePort, V1PersistentVolumeClaim, V1PersistentVolumeClaimSpec, \
    V1PersistentVolumeClaimVolumeSource, V1Secret, V1LabelSelector, \
    V1StatefulSetUpdateStrategy, V1DeploymentStrategy, V1DeploymentSpec, \
    V1ComponentCondition, V1ComponentStatus, V1JobSpec, V1Job, \
    V1SecretVolumeSource, V1PodSecurityContext, \
    V1SecurityContext, V1Capabilities, V1SeccompProfile, V1ContainerStateRunning, V1Probe
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream

import rabbitconstants
from rabbit_helper import RabbitHelper
from rabbit_helper import join_maps
from backup_helper import BackupHelper
from exceptions import DisasterRecoveryException

# fill these variables for dev purpose only
namespace = ""
backup_daemon_url = ""
dev_region = ""

BACKUP_CA_CERT_PATH = '/backupTLS/ca.crt'
CA_CERT_PATH = '/tls/ca.crt'
TLS_CERT_PATH = '/tls/tls.crt'
TLS_KEY_PATH = '/tls/tls.key'

LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
KOPFTIMEOUT = int(os.getenv("OPERATOR_WATCH_TIMEOUT", 300))

logging.basicConfig(
    filename='/proc/1/fd/1',
    filemode='w',
    level=LOGLEVEL,
    format='[%(asctiivsh0819me)s][%(levelname)-5s][category=%(name)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)

logger = logging.getLogger(__name__)
logger.setLevel(LOGLEVEL)
logger.info("loglevel is set to " + str(LOGLEVEL))


class FakeKubeResponse:
    def __init__(self, obj):
        import json
        self.data = json.dumps(obj)


configmap_name = 'rabbitmq-config'
config_volume = 'config-volume'
ssl_volume = 'ssl-certs'
secret_name = 'rabbitmq-default-secret'
vct_name = 'default-vct-name'
telegraf_name = 'telegraf'
username_change_attr = ('data', 'user')
tests_name = 'rabbitmq-integration-tests'
nodeport_service_name = 'rabbitmq-nodeport'
cr_version = "v2"
api_group = os.getenv("API_GROUP", "netcracker.com")
IN_PROGRESS = "In progress"
SUCCESSFUL = "Successful"
FAILED = "Failed"

TIME_TO_WAIT_SECRET_HANDLER = 20
TIME_TO_WAIT_CONFIGMAP_HANDLER = 45

forbidden_statefulset_fields_update_error = "Forbidden: updates to statefulset spec for fields"

positive_values = ('true', 'True', 'yes', 'Yes', True)
operator_need_to_delete_resources = os.getenv("OPERATOR_DELETE_RESOURCES", "False")
logger.info(f'OPERATOR_DELETE_RESOURCES is set to {operator_need_to_delete_resources}')
optional_delete = True
if operator_need_to_delete_resources in positive_values:
    optional_delete = False
handle_forbidden_update = os.getenv("HANDLE_FORBIDDEN_UPDATE", "True") in positive_values

k8s_client = None

try:
    k8s_config.load_incluster_config()
    k8s_client = client.ApiClient()
except k8s_config.ConfigException as e:
    k8s_client = k8s_config.new_client_from_config()

if k8s_client is None:
    import sys
    logger.exception("Can't load any kubernetes config.")
    sys.exit(1)


class KubernetesHelper:
    SA_NAMESPACE_PATH = '/var/run/secrets/kubernetes.io/serviceaccount/namespace'

    def __init__(self, spec):
        self._api_client = k8s_client
        self._workspace = KubernetesHelper.get_namespace()
        self._apps_v1_api = client.AppsV1Api(self._api_client)
        self._v1_apps_api = client.CoreV1Api(self._api_client)
        self._v1_batch_api = client.BatchV1Api(self._api_client)
        self._custom_objects_api = client.CustomObjectsApi(self._api_client)
        self._spec = spec
        self._res = spec['rabbitmq']['resources']
        self._pvs = self._spec['rabbitmq'].get('volumes')
        self._nodes = self._spec['rabbitmq'].get('nodes')
        self._selectors = self._spec['rabbitmq'].get('selectors')
        logger.info("configuration is: " + str(spec))

    @staticmethod
    def get_namespace():
        if not namespace:
            with open(KubernetesHelper.SA_NAMESPACE_PATH) as namespace_file:
                return namespace_file.read()
        return namespace

    def delete_ignore_not_found(self, function, name, grace_period_seconds=20):
        try:
            return function(name=name, namespace=self._workspace, grace_period_seconds=grace_period_seconds)
        except ApiException as exceptondelete:
            # ignore missing objects
            if exceptondelete.status == 404:
                logger.warning("Can't delete object because it can't be found: " + str(exceptondelete))
            else:
                raise

    def get_stateful_set(self, name='rmqlocal-0'):
        return self._apps_v1_api.read_namespaced_stateful_set(name=name, namespace=self._workspace).to_dict()

    def get_security_context(self, name):
        securitycontext = self._spec[name].get('securityContext')
        if securitycontext:
            deserializedsecuritycontext = self._api_client.deserialize(FakeKubeResponse(securitycontext), 'V1PodSecurityContext')
            logger.debug("got following security context:" + str(deserializedsecuritycontext))
            return deserializedsecuritycontext
        else:
            return None

    def get_liveness_probe(self, name):
        if self.is_hostpath():
            command = rabbitconstants.rabbitmq_hostpath_liveness_probe_command
            oldprobe = rabbitconstants.hostpath_liveness_probe
        else:
            command = rabbitconstants.rabbitmq_storageclass_liveness_probe_command
            oldprobe = rabbitconstants.storageclass_liveness_probe
        livenessprobeparameters = self._spec[name].get('livenessProbe')
        if livenessprobeparameters:
            livenessprobe = V1Probe(failure_threshold=livenessprobeparameters.get('failure_threshold', 30),
                                    initial_delay_seconds=livenessprobeparameters.get('initial_delay_seconds', 10),
                                    period_seconds=livenessprobeparameters.get('period_seconds', 30),
                                    success_threshold=livenessprobeparameters.get('success_threshold', 1),
                                    timeout_seconds=livenessprobeparameters.get('timeout_seconds', 15),
                                    _exec=V1ExecAction(command=command))
            return livenessprobe
        else:
            return oldprobe

    def get_readiness_probe(self, name):
        if self.is_hostpath():
            command = rabbitconstants.rabbitmq_hostpath_readiness_probe_command
            oldprobe = rabbitconstants.hostpath_readiness_probe
        else:
            command = rabbitconstants.rabbitmq_storageclass_readiness_probe_command
            oldprobe = rabbitconstants.storageclass_readiness_probe
        readinessprobeparameters = self._spec[name].get('readinessProbe')
        if readinessprobeparameters:
            readinessprobe = V1Probe(failure_threshold=readinessprobeparameters.get('failure_threshold', 90),
                                     initial_delay_seconds=readinessprobeparameters.get('initial_delay_seconds', 10),
                                     period_seconds=readinessprobeparameters.get('period_seconds', 10),
                                     success_threshold=readinessprobeparameters.get('success_threshold', 1),
                                     timeout_seconds=readinessprobeparameters.get('timeout_seconds', 15),
                                     _exec=V1ExecAction(command=command))
            return readinessprobe
        else:
            return oldprobe

    @staticmethod
    def get_container_security_context():
        return V1SecurityContext(allow_privilege_escalation=False, capabilities=V1Capabilities(drop=["ALL"]))

    def get_affinity_rules(self):
        affinity = self._spec['rabbitmq'].get('affinity')
        if affinity:
            deserializedaffinity = self._api_client.deserialize(FakeKubeResponse(affinity), 'V1Affinity')
            logger.debug("got following affinity:" + str(affinity))
            return deserializedaffinity
        else:
            return None

    def wait_test_result(self):
        if 'tests' in self._spec:
            if 'waitTestResultOnJob' in self._spec['tests']:
                return self._spec['tests']['waitTestResultOnJob'] in positive_values
        return False

    def get_test_timeout(self) -> int:
        if 'tests' in self._spec:
            if 'timeout' in self._spec['tests']:
                return self._spec['tests']['timeout']
        return 1800

    def is_test_deployment_succeeded(self):
        deployment = self._apps_v1_api.read_namespaced_deployment(
            name=tests_name, namespace=self._workspace)

        for i in deployment.status.conditions:
            if i.reason == 'IntegrationTestsExecutionStatus':
                if i.type == 'Ready':
                    return True
                return False

    def is_test_deployment_failed(self):
        deployment = self._apps_v1_api.read_namespaced_deployment(
            name=tests_name, namespace=self._workspace)

        for i in deployment.status.conditions:
            if i.reason == 'IntegrationTestsExecutionStatus':
                if i.type == 'Failed':
                    return True
            return False

    def is_test_deployment_present(self):
        deployment = self._apps_v1_api.read_namespaced_deployment(
            name=tests_name, namespace=self._workspace)
        if deployment:
            return True

    def wait_test_deployment_result(self):
        timeout = self.get_test_timeout()
        time = 0
        while time < timeout and not self.is_test_deployment_present():
            sleep(10)
            time = time + 10
        logger.info("Test deployment is created, waiting for result")
        while time < timeout and not self.is_test_deployment_succeeded() and not self.is_test_deployment_failed():
            sleep(10)
            time = time + 10
        if self.is_test_deployment_succeeded():
            return True
        else:
            return False

    def get_tolerations(self):
        tolerations = self._spec['rabbitmq'].get('tolerations')
        deserializedtolerations = []
        if tolerations:
            for toleration in tolerations:
                deserializedtolerations.append(self._api_client.deserialize(FakeKubeResponse(toleration), 'V1Toleration'))
            logger.debug("got following tolerations:" + str(deserializedtolerations))
            return deserializedtolerations
        else:
            return None

    def exec_command_in_pod(self, pod_name, exec_command):
        v1api = self._v1_apps_api
        resp = stream(v1api.connect_get_namespaced_pod_exec, pod_name, self._workspace,
                      command=exec_command,
                      stderr=True, stdin=False,
                      stdout=True, tty=False, _preload_content=False, _request_timeout=30)
        result = ''
        while resp.is_open():
            resp.update(timeout=30)
            if resp.peek_stdout():
                recv_text = resp.read_stdout()
                logger.info("STDOUT: %s" % recv_text)
                result = result + recv_text
            if resp.peek_stderr():
                logger.info("STDERR: %s" % resp.read_stderr())
            
            if resp.returncode is not None:
                break
        
        resp.close()
        return result
    
    def exec_command_in_pod_interactive(self, pod_name, commands):
        exec_command = ['/bin/sh']
        v1api = self._v1_apps_api
        resp = stream(v1api.connect_get_namespaced_pod_exec, pod_name, self._workspace,
                      command=exec_command,
                      stderr=True, stdin=True,
                      stdout=True, tty=True, _preload_content=False, _request_timeout=30)
        result = ''
        try:
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    recv_text = resp.read_stdout()
                    logger.info("STDOUT: %s" % recv_text)
                    result += recv_text
                if resp.peek_stderr():
                    stderr_text = resp.read_stderr()
                    logger.info("STDERR: %s" % stderr_text)
                if commands:
                    command = commands.pop(0)
                    logger.info(f"Running command... {command}")
                    resp.write_stdin(command + "\n")
                    sleep(5)
                else:
                    break
        finally:
            resp.close()
        logger.info("Executed commands in pod successfully.")
        return result

    def change_password(self):
        podname = 'rmqlocal-0-0' if self.is_hostpath() else 'rmqlocal-0'
        output = self.exec_command_in_pod(pod_name=podname, exec_command=['rabbitmqctl', 'change_password',
                                                                          self.get_user_from_secret(),
                                                                          self.get_password_from_secret()])
        if output.find("does not exist") != -1:
            logger.debug("Can't change password, because there is no user "
                         "with provided creds")

    def list_rmq_pvcs(self, label_selector='app=rmqlocal'):
        return self._v1_apps_api.list_namespaced_persistent_volume_claim(namespace=self._workspace,
                                                                         label_selector=label_selector).items

    def list_stateful_sets(self, label_selector='app=rmqlocal'):
        return self._apps_v1_api.list_namespaced_stateful_set(namespace=self._workspace, label_selector=label_selector)

    def is_rabbitmq_pod(self, podname):
        pattern1 = re.compile(r'^rmqlocal-[0-9]+$')
        pattern2 = re.compile(r'^rmqlocal-[0-9]+-0$')
        if pattern1.match(podname):
            return True
        elif pattern2.match(podname):
            return True
        return False

    def is_rabbitmq_hostpath_service(self, servicename):
        pattern2 = re.compile(r'^rmqlocal-[0-9]+-0$')
        if pattern2.match(servicename):
            return True
        return False

    def is_rabbitmq_hostpath_statefulset(self, statefulsetname):
        pattern1 = re.compile(r'^rmqlocal-[0-9]+$')
        if pattern1.match(statefulsetname):
            return True
        return False

    def delete_hostpath_configs_after_downscaling(self):
        # PVCs aren't deleted to keep the same behaviour as was before operator
        allowed_services = []
        allowed_pods = []
        allowed_statefulsets = []
        for idx in range(0, self._spec['rabbitmq']['replicas']):
            allowed_pods.append(f'rmqlocal-{idx}-0')
            allowed_services.append(f'rmqlocal-{idx}-0')
            allowed_statefulsets.append(f'rmqlocal-{idx}')

        for service in self._v1_apps_api.list_namespaced_service(self._workspace).items:
            if service.metadata.name not in allowed_services and self.is_rabbitmq_hostpath_service(service.metadata.name):
                self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_service, name=service.metadata.name)

        for statefulset in self._apps_v1_api.list_namespaced_stateful_set(self._workspace).items:
            if statefulset.metadata.name not in allowed_statefulsets and self.is_rabbitmq_hostpath_statefulset(statefulset.metadata.name):
                self.delete_ignore_not_found(self._apps_v1_api.delete_namespaced_stateful_set,
                                             name=statefulset.metadata.name)

        for pod in self._v1_apps_api.list_namespaced_pod(self._workspace).items:
            if pod.metadata.name not in allowed_pods and self.is_rabbitmq_pod(pod.metadata.name):
                self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_pod, name=pod.metadata.name)

    def is_rmq_statefulset_present(self, statefulset_name):
        statefulsets = self._apps_v1_api.list_namespaced_stateful_set(namespace=self._workspace)
        exists = list(filter(lambda x: x.metadata.name == statefulset_name, statefulsets.items))
        return len(exists) != 0

    def is_any_rmq_statefulset_present(self):
        if self.is_rmq_statefulset_present("rmqlocal"):
            return True
        else:
            replicas = self._spec['rabbitmq']['replicas']
            for idx in range(0, replicas):
                if self.is_rmq_statefulset_present(f'rmqlocal-{idx}'):
                    return True
        return False

    def is_run_tests(self):
        if 'tests' in self._spec:
            if 'runTests' in self._spec['tests']:
                return self._spec['tests']['runTests'] in positive_values
        return False

    def is_run_tests_only(self):
        if 'tests' in self._spec:
            if 'runTestsOnly' in self._spec['tests']:
                return self._spec['tests']['runTestsOnly'] in positive_values
        return False

    def is_service_present(self, service_name):
        services = self._v1_apps_api.list_namespaced_service(self._workspace)
        exists = list(filter(lambda x: x.metadata.name == service_name, services.items))
        return len(exists) != 0

    def is_pvc_for_pv_present(self, pv_name):
        pvcs = self._v1_apps_api.list_namespaced_persistent_volume_claim(self._workspace)
        exists = list(filter(lambda x: x.metadata.name == f'{pv_name}-rmq-pvc', pvcs.items))
        return len(exists) != 0

    def update_stateful_set(self, name, pv_name=None, node_name=None):
        if self.is_rmq_statefulset_present(name):
            self._update_already_presented_rmq_statefulset(name, pv_name, node_name)
        else:
            logger.info(f'apply stateful set with name: {name}')
            statefulsetbody = self.generate_stateful_set_body(name, pv_name=pv_name, node_name=node_name)
            self._apps_v1_api.create_namespaced_stateful_set(self._workspace, statefulsetbody)

    def _update_already_presented_rmq_statefulset(self, name, pv_name=None, node_name=None):
        logger.info(f'update stateful set with name: {name}')
        statefulset_body = self.generate_stateful_set_body(name, pv_name=pv_name, node_name=node_name)
        need_to_process_forbidden_field_update = False
        try:
            logger.info('Replace already presented statefulset')
            self._apps_v1_api.replace_namespaced_stateful_set(name, self._workspace, statefulset_body)
        except ApiException as exception:
            if handle_forbidden_update and forbidden_statefulset_fields_update_error in exception.body:
                need_to_process_forbidden_field_update = True
            else:
                raise exception
        if need_to_process_forbidden_field_update:
            logger.info('Generated statefulset body has forbidden updated fields. Delete presented statefulset')
            self._apps_v1_api.delete_namespaced_stateful_set(name, self._workspace, propagation_policy="Orphan")
            sleep(5)
            logger.info('Upload generated statefulset')
            self._apps_v1_api.create_namespaced_stateful_set(self._workspace, statefulset_body)

    def apply_pvc(self, pv_name=None, number=None):
        # todo app and rabbitmq-app - params
        logger.info(f'creating pvc, storage class: {self.get_pv_storageclass()}')
        selector = None
        if self._selectors is not None:
            selector_key, selector_value = self._selectors[number].split('=')
            selector = V1LabelSelector(match_labels={selector_key: selector_value})
            pvc_prefix = f'rabbitmq-{number}'
        else:
            pvc_prefix = pv_name
        pvc_labels = self.get_default_labels()
        pvc_labels["app"] = "rmqlocal"
        pvc_labels["rabbitmq-app"] = "rmqlocal"
        pvc = V1PersistentVolumeClaim(api_version='v1', kind='PersistentVolumeClaim',
                                      metadata=V1ObjectMeta(name=f'{pvc_prefix}-rmq-pvc',
                                                            labels=pvc_labels),
                                      spec=V1PersistentVolumeClaimSpec(access_modes=['ReadWriteOnce'],
                                                                       resources=V1ResourceRequirements(
                                                                           requests={'storage': self._res['storage']}),
                                                                       volume_name=pv_name, selector=selector,
                                                                       storage_class_name=self.get_pv_storageclass()))
        logger.debug("pvc config:" + str(pvc))
        self._v1_apps_api.create_namespaced_persistent_volume_claim(self._workspace, pvc)

    def is_hostpath(self):
        return self._spec['rabbitmq']['hostpath_configuration']

    def is_hostpath_installed(self):
        if not self.is_rmq_configmap_present():
            # TODO throw error maybe?
            return False
        v1configmap = self._v1_apps_api.read_namespaced_config_map(name=configmap_name, namespace=self._workspace)
        return 'rabbit_peer_discovery_classic_config' in v1configmap.data['rabbitmq.conf']

    def get_cookie_from_secret(self):
        v1secret = self._v1_apps_api.read_namespaced_secret(name=secret_name, namespace=self._workspace)
        return base64.b64decode(v1secret.data['rmqcookie']).decode()

    def get_user_from_secret(self):
        v1secret = self._v1_apps_api.read_namespaced_secret(name=secret_name, namespace=self._workspace)
        return base64.b64decode(v1secret.data['user']).decode()

    def get_old_user_from_secret(self):
        v1secret = self._v1_apps_api.read_namespaced_secret(name=old_secret_name, namespace=self._workspace)
        return base64.b64decode(v1secret.data['user']).decode()

    def get_password_from_secret(self):
        v1secret = self._v1_apps_api.read_namespaced_secret(name=secret_name, namespace=self._workspace)
        return base64.b64decode(v1secret.data['password']).decode()

    def is_auto_reboot(self):
        if 'auto_reboot' in self._spec['rabbitmq']:
            return self._spec['rabbitmq']['auto_reboot']
        return False

    def is_clean_rabbitmq_pvs(self):
        if 'clean_rabbitmq_pvs' in self._spec['rabbitmq']:
            return self._spec['rabbitmq']['clean_rabbitmq_pvs']
        return False

    def is_ipv6_enabled(self):
        if 'ipv6_enabled' in self._spec['rabbitmq']:
            return self._spec['rabbitmq']['ipv6_enabled']
        return False

    def is_ssl_enabled(self):
        if 'ssl_enabled' in self._spec['rabbitmq']:
            return self._spec['rabbitmq']['ssl_enabled']
        return False

    def is_ldap_enabled(self):
        if 'ldap_enabled' in self._spec['rabbitmq']:
            return self._spec['rabbitmq']['ldap_enabled']
        return False

    def is_ldap_ssl_enabled(self):
        if 'ldap_ssl_enabled' in self._spec['rabbitmq']:
            return self._spec['rabbitmq']['ldap_ssl_enabled']
        return False

    def get_backup_daemon_auth(self):
        return BACKUP_CA_CERT_PATH if os.path.exists(BACKUP_CA_CERT_PATH) else None

    def is_nonencrypted_access(self):
        if 'nonencrypted_access' in self._spec['rabbitmq']:
            return self._spec['rabbitmq']['nonencrypted_access']
        return True

    def get_pv_storageclass(self):
        if 'storageclass' in self._res:
            logger.debug("found storage class element: " + str(self._res['storageclass']))
            return self._res['storageclass']
        return None

    def check_custom_params(self):
        if 'custom_params' in self._spec['rabbitmq']:
            return True
        return False

    def get_user_name(self):
        if self.check_custom_params() and 'rabbitmq_default_user' in self._spec['rabbitmq']['custom_params']:
            return self._spec['rabbitmq']['custom_params']['rabbitmq_default_user']
        return 'guest'

    def get_password(self):
        if self.check_custom_params() and 'rabbitmq_default_password' in self._spec['rabbitmq']['custom_params']:
            return self._spec['rabbitmq']['custom_params']['rabbitmq_default_password']
        return 'guest'

    def get_volume_mounts(self):
        if self.is_hostpath():
            mounts = [V1VolumeMount(name=config_volume, mount_path='/configmap'),
                      V1VolumeMount(name='rmqvolumedatamount', mount_path='/var/lib/rabbitmq')]
        else:
            mounts = [V1VolumeMount(name=config_volume, mount_path='/configmap'),
                      V1VolumeMount(name=vct_name, mount_path='/var/lib/rabbitmq')]
        if self.is_ssl_enabled():
            mounts.append(V1VolumeMount(name=ssl_volume, mount_path='/tls'))
        if self.is_ldap_enabled():
            mounts.append(V1VolumeMount(name='ldap-credentials', mount_path='/ldap-credentials'))
            if self.is_ldap_ssl_enabled():
                mounts.append(V1VolumeMount(name='trusted-certs', mount_path='/trusted-certs'))
        return mounts

    def get_volume_claim_templates(self):
        if self.is_hostpath():
            return None
        else:
            return [V1PersistentVolumeClaim(api_version='v1',
                                            metadata=V1ObjectMeta(annotations={
                                                'volume.beta.kubernetes.io/storage-class': self._res[
                                                    'storageclass']},
                                                name=vct_name,
                                                labels=self.get_default_labels()),
                                            spec=V1PersistentVolumeClaimSpec(
                                                access_modes=['ReadWriteOnce'],
                                                storage_class_name=self._res['storageclass'],
                                                resources=V1ResourceRequirements(
                                                    requests={'storage': self._res['storage']})))]

    def get_volumes(self, pv_name):
        if self.is_hostpath():
            return [V1Volume(name=config_volume,
                             config_map=V1ConfigMapVolumeSource(name=configmap_name,
                                                                default_mode=420, items=[V1KeyToPath(key='rabbitmq.conf', path='rabbitmq.conf'),
                                                                                         V1KeyToPath(key='enabled_plugins', path='enabled_plugins'),
                                                                                         V1KeyToPath(key='advanced.config', path='advanced.config')])),
                    V1Volume(name='rmqvolumedatamount',
                             persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(
                                 claim_name=f'{pv_name}-rmq-pvc'))]
        else:
            return [V1Volume(name=config_volume,
                             config_map=V1ConfigMapVolumeSource(name=configmap_name,
                                                                default_mode=420, items=[V1KeyToPath(key='rabbitmq.conf', path='rabbitmq.conf'),
                                                                                         V1KeyToPath(key='enabled_plugins', path='enabled_plugins'),
                                                                                         V1KeyToPath(key='advanced.config', path='advanced.config')]))]

    def generate_telegraf_deployment_config_body(self):
        telegraf_resources = V1ResourceRequirements(limits={'cpu': '100m', 'memory': '100Mi'},
                                                    requests={'cpu': '100m', 'memory': '100Mi'})

        telegraf_image = self._spec['telegraf']['dockerImage']
        image_pull_policy = 'Always' if 'latest' in telegraf_image.lower() \
            else 'IfNotPresent'

        pod_envs = [
            V1EnvVar(name='INFLUXDB_DEBUG',
                     value_from=V1EnvVarSource(
                         secret_key_ref=V1SecretKeySelector(
                             key='influxdb-debug',
                             name='rabbitmq-monitoring'))),
            V1EnvVar(name='METRIC_COLLECTION_INTERVAL',
                     value_from=V1EnvVarSource(
                         secret_key_ref=V1SecretKeySelector(
                             key='metric-collection-interval',
                             name='rabbitmq-monitoring'))),
            V1EnvVar(name='INFLUXDB_URL',
                     value_from=V1EnvVarSource(
                         secret_key_ref=V1SecretKeySelector(
                             key='influxdb-url',
                             name='rabbitmq-monitoring'))),
            V1EnvVar(name='INFLUXDB_DATABASE',
                     value_from=V1EnvVarSource(
                         secret_key_ref=V1SecretKeySelector(
                             key='influxdb-database',
                             name='rabbitmq-monitoring'))),
            V1EnvVar(name='INFLUXDB_USER',
                     value_from=V1EnvVarSource(
                         secret_key_ref=V1SecretKeySelector(
                             key='influxdb-user',
                             name='rabbitmq-monitoring'))),
            V1EnvVar(name='INFLUXDB_PASSWORD',
                     value_from=V1EnvVarSource(
                         secret_key_ref=V1SecretKeySelector(
                             key='influxdb-password',
                             name='rabbitmq-monitoring'))),
            V1EnvVar(name='RABBITMQ_PASSWORD',
                     value_from=V1EnvVarSource(
                         secret_key_ref=V1SecretKeySelector(
                             key='password',
                             name='rabbitmq-default-secret'))),
            V1EnvVar(name='RABBITMQ_USER',
                     value_from=V1EnvVarSource(
                         secret_key_ref=V1SecretKeySelector(
                             key='user',
                             name='rabbitmq-default-secret'))),
            V1EnvVar(name='RABBITMQ_HOST', value='rabbitmq'),
            V1EnvVar(name='NAMESPACE', value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path='metadata.namespace')))]

        telegraf_labels = {'name': telegraf_name, 'component': telegraf_name}
        telegraf_custom_labels = self.get_custom_labels(telegraf_labels, 'telegraf')

        liveness = V1Probe(
            tcp_socket=V1TCPSocketAction(port=8096),
            initial_delay_seconds=30,
            timeout_seconds=5,
            period_seconds=15,
            success_threshold=1,
            failure_threshold=20,
        )

        readiness = V1Probe(
            tcp_socket=V1TCPSocketAction(port=8096),
            initial_delay_seconds=30,
            timeout_seconds=5,
            period_seconds=15,
            success_threshold=1,
            failure_threshold=20,
        )
        podtemplate = V1PodTemplateSpec(
            metadata=V1ObjectMeta(labels=telegraf_custom_labels),
            spec=V1PodSpec(containers=[V1Container(name=telegraf_name,
                                                   image=telegraf_image,
                                                   env=pod_envs,
                                                   termination_message_path='/dev/termination-log',
                                                   image_pull_policy=image_pull_policy,
                                                   resources=telegraf_resources,
                                                   security_context=self.get_container_security_context(),
                                                   readiness_probe=readiness,
                                                   liveness_probe=liveness,)],
                           security_context=self.get_security_context("telegraf"),
                           affinity=self.get_affinity_rules(),
                           tolerations=self.get_tolerations(),
                           restart_policy='Always',
                           service_account='rabbitmq-operator',  # ToDo maybe need custom SA
                           termination_grace_period_seconds=30))

        spec = V1DeploymentSpec(replicas=1,
                                strategy=V1DeploymentStrategy(type='Recreate'),
                                selector=V1LabelSelector(match_labels={'name': telegraf_name,
                                                                       'component': telegraf_name}),
                                template=podtemplate)

        meta = V1ObjectMeta(name=telegraf_name)

        body = client.V1Deployment(metadata=meta, spec=spec)
        logger.debug("telegraf dc body: " + str(body))
        return body

    def apply_telegraf_dc(self):
        dcbody = self.generate_telegraf_deployment_config_body()
        self._apps_v1_api.create_namespaced_deployment(self._workspace, dcbody)

    def get_rabbit_pods(self):
        return self._v1_apps_api.list_namespaced_pod(
            namespace=self._workspace,
            label_selector='app=rmqlocal'
        )

    def check_rabbit_pods_readiness(self) -> bool:
        logger.info(f'Checking rabbit pods readiness ...')
        if not self._check_required_rabbit_pods_presented():
            return False
        pods_ready = self._check_rabbit_pods_running()
        logger.info(f'Rabbit pods ready: {pods_ready}')
        return pods_ready

    def _check_required_rabbit_pods_presented(self) -> bool:
        replicas_count = self._spec['rabbitmq']['replicas']
        pods = []
        for i in range(0, 30):
            time.sleep(30)
            pods = (self.get_rabbit_pods()).items
            if len(pods) == replicas_count:
                break
        if len(pods) != replicas_count:
            logger.info(f'There is not enough rabbit pods. Specified: '
                        f'{replicas_count}, presented: {len(pods)}')
            return False
        else:
            return True

    def _check_rabbit_pods_running(self) -> bool:
        for i in range(0, 30):
            pods_ready = True
            pods = (self.get_rabbit_pods()).items
            for pod in pods:
                statuses = pod.status.container_statuses
                all_containers_running = all([status.ready for status in statuses]) if statuses else False
                pods_ready &= all_containers_running
            if pods_ready is False:
                logger.debug('Rabbit pods are not ready yet. Wait 30 seconds.')
                time.sleep(30)
            else:
                break
        return pods_ready

    def get_rabbit_pods_count(self):
        return len((self.get_rabbit_pods()).items)

    def is_deployment_present(self, name):
        deployments = self._apps_v1_api.list_namespaced_deployment(
            namespace=self._workspace)
        exists = list(
            filter(lambda x: x.metadata.name == name,
                   deployments.items))
        return len(exists) != 0

    def update_telegraf_deployment(self):
        logger.debug("updating telegraf deployment ...")
        deployment_body = self.generate_telegraf_deployment_config_body()
        if self.is_deployment_present(telegraf_name):
            self._apps_v1_api.patch_namespaced_deployment(
                name=telegraf_name,
                namespace=self._workspace,
                body=deployment_body)
        else:
            self._apps_v1_api.create_namespaced_deployment(
                namespace=self._workspace,
                body=deployment_body)
        for pod in self._v1_apps_api.list_namespaced_pod(self._workspace).items:
            if telegraf_name in pod.metadata.name:
                self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_pod, name=pod.metadata.name)

    def is_telegraf_enabled(self):
        if 'telegraf' in self._spec and self._spec['telegraf'].get('install') in positive_values:
            return True
        return False

    def generate_stateful_set_body(self, name, pv_name=None, node_name=None):
        livenessprobe = self.get_liveness_probe('rabbitmq')
        readinessprobe = self.get_readiness_probe('rabbitmq')
        rabbit_replicas = self._spec['rabbitmq']['replicas']
        longname = 'true'
        in_pod_node_name = 'rabbit@$(MY_POD_NAME).$(BROKER_NAME_INTERNAL).$(MY_POD_NAMESPACE).svc.cluster.local'
        nodeselector = None
        lifecycle = V1Lifecycle(pre_stop=V1Handler(_exec=V1ExecAction(
            command=rabbitconstants.rabbitmq_storage_class_pre_stop_command)))

        if self.is_hostpath():
            longname = 'false'
            in_pod_node_name = 'rabbit@$(BROKER_NAME_INTERNAL)-0'
            rabbit_replicas = 1
            nodeselector = {'kubernetes.io/hostname': node_name}
            lifecycle = None

        logger.debug("resources:" + str(self._res))
        sts_labels = self.get_default_labels()
        sts_labels["app"] = "rmqlocal"
        sts_labels["rabbitmq-app"] = name
        sts_labels["name"] = "rabbitmq"
        sts_labels["app.kubernetes.io/name"] = "rabbitmq"
        sts_labels["app.kubernetes.io/instance"] = f'rabbitmq-{self._workspace}'
        meta = V1ObjectMeta(labels=sts_labels, name=name, namespace=self._workspace)
        rabbitmq_image = self._spec['rabbitmq']['dockerImage']
        image_pull_policy = 'Always' if 'latest' in rabbitmq_image.lower() else 'IfNotPresent'
        if self.is_ipv6_enabled():
            volumes = self.get_volumes(pv_name)
            volumes[0].config_map.items.extend([V1KeyToPath(key='erl_inetrc', path='erl_inetrc')])
        else:
            volumes = self.get_volumes(pv_name)
        if self.is_ssl_enabled():
            ssl_secret_name = self._spec['rabbitmq']['ssl_secret_name']
            volumes.append(V1Volume(name=ssl_volume,
                                    secret=V1SecretVolumeSource(secret_name=ssl_secret_name, default_mode=420)))
        if self.is_ldap_enabled():
            volumes.append(V1Volume(name='ldap-credentials',
                                    secret=V1SecretVolumeSource(secret_name='ldap-credentials',
                                                                items=[V1KeyToPath(key='LDAP_ADMIN_USER', path='LDAP_ADMIN_USER'),
                                                                       V1KeyToPath(key='LDAP_ADMIN_PASSWORD', path='LDAP_ADMIN_PASSWORD')])))
        if self.is_ldap_enabled() and self.is_ldap_ssl_enabled():
            volumes.append(V1Volume(name='trusted-certs',
                                    secret=V1SecretVolumeSource(secret_name='rabbitmq-trusted-certs')))
        rabbit_labels = {'app': 'rmqlocal', 'deploymentconfig': name}
        rabbit_custom_labels = self.get_custom_labels(rabbit_labels, 'rabbitmq')
        rabbit_annotations = {'pre.hook.backup.velero.io/command': '["sync"]'}
        rabbit_custom_annotations = self.get_custom_annotations(rabbit_annotations, 'rabbitmq')
        pod_template_spec = V1PodTemplateSpec(
            metadata=V1ObjectMeta(labels=rabbit_custom_labels, annotations=rabbit_custom_annotations),
            spec=V1PodSpec(volumes=volumes, node_selector=nodeselector,
                           affinity=self.get_affinity_rules(),
                           tolerations=self.get_tolerations(),
                           service_account_name='rabbitmq',
                           containers=[V1Container(image=rabbitmq_image, name=name,
                                                   resources=V1ResourceRequirements(
                                                       limits={'cpu': self._res['limits']['cpu'],
                                                               'memory': self._res['limits']['memory']},
                                                       requests={'cpu': self._res['requests']['cpu'],
                                                                 'memory': self._res['requests']['memory']}),
                                                   volume_mounts=self.get_volume_mounts(),
                                                   env=[V1EnvVar(name='BROKER_NAME_INTERNAL', value=name),
                                                        V1EnvVar(name='AUTOCLUSTER_DELAY', value='2000'),
                                                        V1EnvVar(name='MY_NODE_NAME', value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path='spec.nodeName'))),
                                                        V1EnvVar(name='MY_POD_NAME', value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path='metadata.name'))),
                                                        V1EnvVar(name='MY_POD_NAMESPACE', value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path='metadata.namespace'))),
                                                        V1EnvVar(name='MY_POD_IP', value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path='status.podIP'))),
                                                        V1EnvVar(name='MY_POD_SERVICE_ACCOUNT', value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path='spec.serviceAccountName'))),
                                                        V1EnvVar(name='RABBITMQ_USE_LONGNAME', value=longname),
                                                        V1EnvVar(name='RABBITMQ_NODENAME', value=in_pod_node_name),
                                                        V1EnvVar(name='K8S_HOSTNAME_SUFFIX', value='.' + name + '.$(MY_POD_NAMESPACE).svc.cluster.local'),
                                                        V1EnvVar(name='K8S_SERVICE_NAME', value=name),
                                                        V1EnvVar(name='CLEANUP_WARN_ONLY', value='true'),
                                                        V1EnvVar(name='AUTOCLUSTER_CLEANUP', value='false'),
                                                        V1EnvVar(name='RABBITMQ_DEFAULT_USER', value_from=V1EnvVarSource(secret_key_ref=V1SecretKeySelector(key='user', name=secret_name))),
                                                        V1EnvVar(name='RABBITMQ_DEFAULT_PASS', value_from=V1EnvVarSource(secret_key_ref=V1SecretKeySelector(key='password', name=secret_name))),
                                                        V1EnvVar(name='RABBITMQ_COOKIE', value_from=V1EnvVarSource(secret_key_ref=V1SecretKeySelector(key='rmqcookie', name=secret_name))),
                                                        V1EnvVar(name='RABBITMQ_ENABLE_IPV6', value=str(self.is_ipv6_enabled())),
                                                        *self.get_additional_environment_variables()
                                                        ],
                                                   ports=[V1ContainerPort(container_port=15672, protocol='TCP'),
                                                          V1ContainerPort(container_port=4369, protocol='TCP'),
                                                          V1ContainerPort(container_port=5671, protocol='TCP'),
                                                          V1ContainerPort(container_port=5672, protocol='TCP'),
                                                          V1ContainerPort(container_port=15671, protocol='TCP'),
                                                          V1ContainerPort(container_port=25672, protocol='TCP'),
                                                          V1ContainerPort(container_port=15692, protocol='TCP')
                                                          ],
                                                   image_pull_policy=image_pull_policy,
                                                   lifecycle=lifecycle,
                                                   readiness_probe=readinessprobe,
                                                   liveness_probe=livenessprobe,
                                                   security_context=self.get_container_security_context()
                                                   )],
                           security_context=self.get_security_context("rabbitmq"),
                           priority_class_name=self._spec['rabbitmq'].get('priorityClassName')
                           )
        )
        if self.is_ipv6_enabled():
            pod_template_spec.spec.containers[0].env.extend(
                [
                    V1EnvVar(name='RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS', value="-kernel inetrc '/etc/rabbitmq/erl_inetrc' -proto_dist inet6_tcp"),
                    V1EnvVar(name='RABBITMQ_CTL_ERL_ARGS', value="-proto_dist inet6_tcp"),
                ]
            )

        if self.is_ldap_enabled():
            pod_template_spec.spec.containers[0].env.extend(
                [
                    V1EnvVar(name='LDAP_ADMIN_USER', value_from=V1EnvVarSource(secret_key_ref=V1SecretKeySelector(key='LDAP_ADMIN_USER', name='ldap-credentials'))),
                    V1EnvVar(name='LDAP_ADMIN_PASSWORD', value_from=V1EnvVarSource(secret_key_ref=V1SecretKeySelector(key='LDAP_ADMIN_PASSWORD', name='ldap-credentials')))
                ]
            )

        spec = client.V1StatefulSetSpec(
            replicas=rabbit_replicas,
            template=pod_template_spec, update_strategy=V1StatefulSetUpdateStrategy(type='OnDelete'),
            service_name=name,
            selector=client.V1LabelSelector(match_labels={'app': 'rmqlocal', 'deploymentconfig': name}),
            volume_claim_templates=self.get_volume_claim_templates()

        )
        body = client.V1StatefulSet(metadata=meta, spec=spec)
        logger.debug("statefulset body: " + str(body))
        return body

    def get_additional_environment_variables(self) -> list:
        variables_map = {}
        if 'environmentVariables' in self._spec['rabbitmq']:
            for variable in self._spec['rabbitmq']['environmentVariables']:
                parts = variable.split('=')
                if len(parts) != 2:
                    logger.error(f'Environment variable "{variable}" is incorrect')
                else:
                    name = parts[0].strip()
                    value = parts[1].strip()
                    variables_map[name] = value
        return [V1EnvVar(name=name, value=value) for name, value in variables_map.items()]

    def get_custom_labels(self, own_labels: dict, spec_path: str) -> dict:
        _global = self._spec.get('global', None)
        global_labels = _global.get('customLabels', None) if _global is not None else None
        custom_labels = self._spec[spec_path].get('customLabels', None)
        return join_maps(join_maps(global_labels, custom_labels), join_maps(own_labels, self.get_default_labels()))

    def get_custom_annotations(self, own_annotations: dict, spec_path: str) -> dict:
        custom_annotations = self._spec[spec_path].get('customAnnotations', None)
        return join_maps(own_annotations, custom_annotations)

    def get_default_labels(self) -> dict:
        _global = self._spec.get('global', None)
        default_labels = _global.get('defaultLabels', None) if _global is not None else None
        return default_labels

    def update_hostpath_stateful_sets(self):
        replicas = self._spec['rabbitmq']['replicas']
        if self._selectors is not None:
            for idx in range(0, replicas):
                if not self.is_pvc_for_pv_present(f'rabbitmq-{idx}'):
                    if self._pvs is not None:
                        self.apply_pvc(pv_name=self._pvs[idx], number=idx)
                    else:
                        self.apply_pvc(number=idx)
                self.update_stateful_set(f'rmqlocal-{idx}', f'rabbitmq-{idx}', self._nodes[idx])
        else:
            for idx in range(0, replicas):
                if not self.is_pvc_for_pv_present(self._pvs[idx]):
                    self.apply_pvc(pv_name=self._pvs[idx])
                self.update_stateful_set(f'rmqlocal-{idx}', self._pvs[idx], self._nodes[idx])

    def is_rmq_configmap_present(self):
        configmaps = self._v1_apps_api.list_namespaced_config_map(namespace=self._workspace)
        exists = list(filter(lambda x: x.metadata.name == configmap_name, configmaps.items))
        return len(exists) != 0

    def is_secret_present(self, target_secret_name: str) -> bool:
        secrets = self._v1_apps_api.list_namespaced_secret(namespace=self._workspace)
        exists = list(filter(lambda x: x.metadata.name == target_secret_name, secrets.items))
        return len(exists) != 0

    def is_rmq_secret_present(self):
        return self.is_secret_present(secret_name)

    def deactivate_old_user(self, old_username):
        logger.debug("Deactivating old user...")
        podname = 'rmqlocal-0-0' if self.is_hostpath() else 'rmqlocal-0'
        self.exec_command_in_pod(pod_name=podname,
                                 exec_command=['rabbitmqctl', 'delete_user',
                                               old_username])
        logger.debug("Deactivating old user finished")

    def update_services(self):
        if self.is_hostpath():
            replicas = self._spec['rabbitmq']['replicas']
            for idx in range(0, replicas):
                # TODO configure_local_service function input parameter is not service name
                self.configure_local_service(f'rmqlocal-{idx}')
        else:
            self.configure_local_service('rmqlocal')
        self.configure_ext_service('rabbitmq')

    def reboot_pods(self, old_pods_count=None):
        if old_pods_count:
            if self._spec['rabbitmq']['replicas'] > old_pods_count:
                replicas = old_pods_count
            else:
                replicas = self._spec['rabbitmq']['replicas']
        else:
            replicas = self._spec['rabbitmq']['replicas']
        for idx in range(0, replicas):
            if self.is_hostpath():
                self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_pod, name=f'rmqlocal-{idx}-0')
            else:
                self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_pod, name=f'rmqlocal-{idx}')
                self.check_cluster_state()
            logger.info(f'pod {idx} rebooted successfully')
        if self.is_hostpath():
            self.check_cluster_state()

    def set_clean_pv_flag_and_delete_pods(self):
        replicas = self._spec['rabbitmq']['replicas']
        for idx in range(0, replicas):
            if self.is_hostpath():
                self.exec_command_in_pod(pod_name=f'rmqlocal-{idx}-0',
                                         exec_command=['touch', '/var/lib/rabbitmq/delete_all'])
                sleep(5)
                self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_pod, name=f'rmqlocal-{idx}-0')
            else:
                self.exec_command_in_pod(pod_name=f'rmqlocal-{idx}',
                                         exec_command=['touch', '/var/lib/rabbitmq/delete_all'])
                sleep(5)
                self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_pod, name=f'rmqlocal-{idx}')
            logger.info(f'clean pv flag in pod {idx} was set successfully')

    def apply_services(self):
        if self.is_hostpath():
            replicas = self._spec['rabbitmq']['replicas']
            for idx in range(0, replicas):
                self.configure_local_service(f'rmqlocal-{idx}')
        else:
            self.configure_local_service('rmqlocal')
        self.configure_ext_service('rabbitmq')

    def configure_local_service(self, deploymentconfigname, update=False):
        serviceports = [V1ServicePort(name='15672-tcp-local', port=15672, protocol='TCP', target_port=15672),
                        V1ServicePort(name='4369-tcp-local', port=4369, protocol='TCP', target_port=4369),
                        V1ServicePort(name='5671-tcp-local', port=5671, protocol='TCP', target_port=5671),
                        V1ServicePort(name='5672-tcp-local', port=5672, protocol='TCP', target_port=5672),
                        V1ServicePort(name='15671-tcp-local', port=15671, protocol='TCP', target_port=15671),
                        V1ServicePort(name='25672-tcp-local', port=25672, protocol='TCP', target_port=25672),
                        V1ServicePort(name='15692-tcp-local', port=15692, protocol='TCP', target_port=15692)]
        servicespec = V1ServiceSpec(cluster_ip='None', ports=serviceports,
                                    selector={'deploymentconfig': deploymentconfigname})
        servicename = deploymentconfigname
        if self.is_hostpath():
            servicespec = V1ServiceSpec(ports=serviceports, selector={'deploymentconfig': deploymentconfigname})
            servicename = deploymentconfigname + "-0"
        service_labels = self.get_default_labels()
        service_labels["app"] = "rmqlocal"
        service_labels["rabbitmq-app"] = deploymentconfigname
        service_labels["name"] = "rabbitmq"
        service_labels["app.kubernetes.io/name"] = "rabbitmq"
        rmqlocal_service = V1Service(api_version='v1', kind='Service',
                                     metadata=V1ObjectMeta(name=servicename,
                                                           labels=service_labels),
                                     spec=servicespec)
        if self.is_service_present(service_name=servicename):
            logger.debug("service is being patched")
            self._v1_apps_api.patch_namespaced_service(servicename, self._workspace, rmqlocal_service)
        else:
            logger.debug("service is being created")
            self._v1_apps_api.create_namespaced_service(self._workspace, rmqlocal_service)

    def get_ssl_ports(self) -> list:
        if self.is_ssl_enabled():
            ports = [
                V1ServicePort(name='5671-tcp',
                              port=5671,
                              protocol='TCP',
                              target_port=5671),
                V1ServicePort(name='15671-tcp',
                              port=15671,
                              protocol='TCP',
                              target_port=15671)
            ]
        else:
            ports = []
        return ports

    def get_non_ssl_ports(self) -> list:
        if self.is_nonencrypted_access():
            ports = [
                V1ServicePort(name='5672-tcp',
                              port=5672,
                              protocol='TCP',
                              target_port=5672),
                V1ServicePort(name='15672-tcp',
                              port=15672,
                              protocol='TCP',
                              target_port=15672)
            ]
        else:
            ports = []
        return ports

    def configure_ext_service(self, name, update=False):
        logger.info("configuring external-service")
        service_labels = self.get_default_labels()
        service_labels["app"] = "rmqlocal"
        service_labels["name"] = "rabbitmq"
        service_labels["app.kubernetes.io/name"] = "rabbitmq"
        rabbitmq_service = V1Service(api_version='v1', kind='Service',
                                     metadata=V1ObjectMeta(name=name,
                                                           labels=service_labels),
                                     spec=V1ServiceSpec(ports=[*self.get_non_ssl_ports(),
                                                               V1ServicePort(name='15692-tcp',
                                                                             port=15692,
                                                                             protocol='TCP',
                                                                             target_port=15692),
                                                               *self.get_ssl_ports()],
                                                        selector={'app': 'rmqlocal'}))
        if self.is_service_present(service_name=name):
            logger.debug("external-service is being replaced")
            self._v1_apps_api.replace_namespaced_service(name, self._workspace, rabbitmq_service)
            return
        logger.debug("external-service is being created")
        self._v1_apps_api.create_namespaced_service(self._workspace, rabbitmq_service)

    def get_replicas_from_stateful_set(self, name):
        stateful_set = self.get_stateful_set(name)
        status = stateful_set['status']
        return min(int(status.get('readyReplicas', "0")),
                   int(status.get('updatedReplicas', "0")))

    def get_existing_volumes(self, name):
        stateful_set = self.get_stateful_set(name)
        volumes = stateful_set['spec'].get('template').get('spec').get('volumes')
        return volumes

    def wait_till_replicas_count(self, name, replicas=1):
        for _ in range(1, 100):
            time.sleep(1)
            ready_replicas = self.get_replicas_from_stateful_set(name)
            if replicas == ready_replicas:
                return

    def delete_resources(self):
        # ToDo delete monitoring and nodeport
        self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_config_map, name=configmap_name)
        self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_service, name='rabbitmq')
        self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_secret, name=secret_name)
        replicas = self._spec['rabbitmq']['replicas']
        if self.is_hostpath():
            for idx in range(0, replicas):
                self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_service, name=f'rmqlocal-{idx}-0')
                self.delete_ignore_not_found(self._apps_v1_api.delete_namespaced_stateful_set, name=f'rmqlocal-{idx}')
                self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_pod, name=f'rmqlocal-{idx}-0')
                self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_persistent_volume_claim,
                                             name=f'{self._pvs[idx]}-rmq-pvc')
        else:
            self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_service, name='rmqlocal')
            self.delete_ignore_not_found(self._apps_v1_api.delete_namespaced_stateful_set, name='rmqlocal')
            for idx in range(0, replicas):
                self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_pod, name=f'rmqlocal-{idx}')
                self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_persistent_volume_claim,
                                             name=f'{vct_name}-rmqlocal-{idx}')
        # in case rabbit was downscaled or upscaled
        for pvc in self.list_rmq_pvcs():
            self.delete_ignore_not_found(self._v1_apps_api.delete_namespaced_persistent_volume_claim, pvc.metadata.name)

    def update_config(self):
        if self.is_hostpath():
            self.update_hostpath_stateful_sets()
            self.delete_hostpath_configs_after_downscaling()
        else:
            self.update_stateful_set("rmqlocal")

    def check_cluster_state(self):
        if self.is_ssl_enabled():
            rabbit_helper = RabbitHelper(self.get_user_from_secret(), self.get_password_from_secret(),
                                         'https://rabbitmq.' + self._workspace + '.svc:15671', ssl=CA_CERT_PATH)
        else:
            rabbit_helper = RabbitHelper(self.get_user_from_secret(), self.get_password_from_secret(),
                                         'http://rabbitmq.' + self._workspace + '.svc:15672')
        for i in range(0, 30):
            time.sleep(30)
            if rabbit_helper.is_cluster_alive(self._spec['rabbitmq']['replicas']):
                return
        self.update_status(
            FAILED,
            "Error",
            "RabbitMQ cluster fails to come up"
        )
        time.sleep(5)
        raise kopf.PermanentError("RabbitMQ cluster fails to come up.")
    
    def check_shovel_state(self, alive_percentage=0.8):
        if self.is_ssl_enabled():
            rabbit_helper = RabbitHelper(self.get_user_from_secret(), self.get_password_from_secret(),
                                         'https://rabbitmq.' + self._workspace + '.svc:15671', ssl=CA_CERT_PATH)
        else:
            rabbit_helper = RabbitHelper(self.get_user_from_secret(), self.get_password_from_secret(),
                                         'http://rabbitmq.' + self._workspace + '.svc:15672')
    
        return rabbit_helper.is_shovel_alive(alive_percentage)

    
    def restart_shovel_plugin(self, pod_name):
        logger.info(f"Restarting shovel plugin in pod {pod_name}...")
        output = self.exec_command_in_pod(
            pod_name=pod_name,
            exec_command = [
                "/bin/sh",
                "-c",
                """
                if rabbitmq-plugins list -E | grep -q rabbitmq_shovel; then
                    if rabbitmq-plugins disable rabbitmq_shovel rabbitmq_shovel_management 2>&1 \
                        | grep -q "The following plugins have been disabled:"; then
                        echo "plugins disabled"
                    fi
                fi
                """
]
        )
        logger.debug("Disable shovel plugin output: {}".format(output))
        if output.find('plugins disabled') == -1:
            raise RuntimeError("Failed to disable shovel plugin in pod {}".format(pod_name))
       
        time.sleep(10)
        output = self.exec_command_in_pod(
            pod_name=pod_name,
            exec_command = [
                "/bin/sh",
                "-c",
                """
                    if ! rabbitmq-plugins list -E | grep -q rabbitmq_shovel; then
                        if rabbitmq-plugins enable rabbitmq_shovel rabbitmq_shovel_management 2>&1 \
                            | grep -q "The following plugins have been enabled:"; then
                            echo "plugins enabled"
                        fi
                    fi
                """
            ]

        )
        logger.debug("Enable shovel plugin output: {}".format(output))
        if output.find('plugins enabled') == -1:
            raise RuntimeError("Failed to enable shovel plugin in pod {}".format(pod_name))
    
    def nodes_restart_shovel_plugin(self):
        if self._check_rabbit_pods_running() is False:
            raise RuntimeError("Cannot restart shovel plugin because not all RabbitMQ pods are running")
        
        logger.info("Restarting shovel plugin...")
        pods = (self.get_rabbit_pods()).items
        for pod in pods:
            pod_name = pod.metadata.name
            for attempt in range(3):
                try:
                    self.restart_shovel_plugin(pod_name)
                    logger.info(f"Successfully restarted shovel plugin in pod {pod_name}")
                    break
                except RuntimeError as e:
                    if attempt < 2:
                        logger.warning(f"Attempt {attempt + 1}/3 failed for pod {pod_name}: {e}. Retrying...")
                        time.sleep(5)
                    else:
                        logger.error(f"Failed to restart shovel plugin in pod {pod_name} after 3 attempts")
                        raise

        logger.info("Shovel plugin restarted successfully")

    def enable_feature_flags(self):
        if self.is_hostpath():
            self.exec_command_in_pod(pod_name='rmqlocal-0-0',
                                     exec_command=['rabbitmqctl', 'enable_feature_flag', 'all'])
        else:
            self.exec_command_in_pod(pod_name='rmqlocal-0',
                                     exec_command=['rabbitmqctl', 'enable_feature_flag', 'all'])
        logger.info("Feature flags are enabled successfully")

    def is_nodeport_required(self):
        if 'nodePortService' in self._spec['rabbitmq']:
            if 'install' in self._spec['rabbitmq']['nodePortService']:
                return self._spec['rabbitmq']['nodePortService']['install'] in positive_values
        return False

    def configure_nodeport_service(self):
        logger.info("configuring nodeport service")
        amqpnodeport, mgmtnodeport = None, None
        if 'amqpNodePort' in self._spec['rabbitmq']['nodePortService']:
            amqpnodeport = int(self._spec['rabbitmq']['nodePortService']['amqpNodePort'])
        if 'mgmtNodePort' in self._spec['rabbitmq']['nodePortService']:
            mgmtnodeport = int(self._spec['rabbitmq']['nodePortService']['mgmtNodePort'])
        if self.is_ssl_enabled():
            ports = [V1ServicePort(name='15671-tcp',
                                   port=15671,
                                   protocol='TCP',
                                   target_port=15671,
                                   node_port=mgmtnodeport),
                     V1ServicePort(name='5671-tcp',
                                   port=5671,
                                   protocol='TCP',
                                   target_port=5671,
                                   node_port=amqpnodeport)]
        else:
            ports = [V1ServicePort(name='15672-tcp',
                                   port=15672,
                                   protocol='TCP',
                                   target_port=15672,
                                   node_port=mgmtnodeport),
                     V1ServicePort(name='5672-tcp',
                                   port=5672,
                                   protocol='TCP',
                                   target_port=5672,
                                   node_port=amqpnodeport)]
        service_labels = self.get_default_labels()
        service_labels["app"] = "rmqlocal"
        service_labels["name"] = "rabbitmq"
        service_labels["app.kubernetes.io/name"] = "rabbitmq"
        nodeport_service = V1Service(api_version='v1', kind='Service',
                                     metadata=V1ObjectMeta(name=nodeport_service_name,
                                                           labels=service_labels),
                                     spec=V1ServiceSpec(ports=ports,
                                                        external_traffic_policy="Cluster",
                                                        type="NodePort",
                                                        selector={'app': 'rmqlocal'}))
        if self.is_service_present(service_name=nodeport_service_name):
            logger.debug("nodeport service is being replaced")
            self._v1_apps_api.replace_namespaced_service(nodeport_service_name, self._workspace, nodeport_service)
        else:
            logger.debug("nodeport service is being created")
            self._v1_apps_api.create_namespaced_service(self._workspace, nodeport_service)
        return

    def scale_down_backup_daemon(self,
                                 namespace: str,
                                 name: str = 'rabbitmq-backup-daemon',
                                 attempts: int = 6,
                                 timeout: int = 10):
        logger.info("Backup Daemon scale-down started")
        scale = self._apps_v1_api.read_namespaced_deployment_scale(name, namespace)
        scale.spec.replicas = 0
        self._apps_v1_api.patch_namespaced_deployment_scale(name, namespace, scale)
        while attempts:
            dp_status = self._apps_v1_api.read_namespaced_deployment_status(name, namespace)
            status_replicas = dp_status.status.replicas
            if not status_replicas:
                logger.info("Backup Daemon scale-down completed")
                return
            attempts -= 1
            time.sleep(timeout)
        logger.info("RabbitMQ Backup Daemon was not scaled down during switchover process")

    def scale_up_backup_daemon(self,
                               namespace: str,
                               name='rabbitmq-backup-daemon',
                               attempts: int = 12,
                               timeout: int = 10):
        logger.info("Backup Daemon scale-up started")
        scale = self._apps_v1_api.read_namespaced_deployment_scale(name, namespace)
        scale.spec.replicas = 1
        self._apps_v1_api.patch_namespaced_deployment_scale(name, namespace, scale)
        full_time = attempts * timeout
        while attempts:
            time.sleep(timeout)
            dp_status = self._apps_v1_api.read_namespaced_deployment_status(name, namespace)
            available_replicas = dp_status.status.available_replicas
            if available_replicas and available_replicas == 1:
                logger.info("Backup Daemon scale-up completed")
                return
            attempts -= 1
        raise DisasterRecoveryException(message=f'RabbitMQ Backup daemon is not up after {full_time} seconds')

    def get_custom_resource(self):
        cr = self._custom_objects_api.get_namespaced_custom_object(
            group=api_group, version=cr_version,
            namespace=self._workspace,
            plural='rabbitmqservices',
            name='rabbitmq-service'
        )
        return cr

    def update_custom_resource(self, body):
        self._custom_objects_api.patch_namespaced_custom_object(
            group=api_group,
            version=cr_version,
            namespace=self._workspace,
            plural='rabbitmqservices',
            name='rabbitmq-service',
            body=body
        )

    def get_custom_resource_status(self):
        return self._custom_objects_api.get_namespaced_custom_object_status(
            group=api_group,
            version=cr_version,
            namespace=self._workspace,
            plural='rabbitmqservices',
            name='rabbitmq-service'
        )

    def update_custom_resource_status(self, body):
        self._custom_objects_api.patch_namespaced_custom_object_status(
            group=api_group,
            version=cr_version,
            namespace=self._workspace,
            plural='rabbitmqservices',
            name='rabbitmq-service',
            body=body
        )

    def initiate_status(self):
        cr_status = self.get_custom_resource_status()
        logger.info(cr_status)
        conditions = []
        in_progress = V1ComponentCondition(
            type=IN_PROGRESS,
            status=True,
            message="RabbitMQ operator started deploy process",
        )
        conditions.append(in_progress)
        status = V1ComponentStatus(conditions=conditions)
        cr_status['status'] = status
        self.update_custom_resource_status(cr_status)

    def update_status(self, status_type, error, message):
        cr_status = self.get_custom_resource_status()
        conditions = cr_status['status']['conditions']
        new_condition = V1ComponentCondition(
            type=status_type,
            status=True,
            message=message,
            error=error,
        )
        conditions.append(new_condition)
        cr_status['status']['conditions'] = conditions
        self.update_custom_resource_status(cr_status)

    def update_disaster_recovery_status(self, mode=None, status=None, message=None):
        disaster_recovery_status = {key: value for key, value in zip(['mode', 'status', 'message'],
                                                                     [mode, status, message]) if value is not None}
        cr_status = self.get_custom_resource_status()
        status = cr_status.get('status')
        if not status:
            status = {'disasterRecoveryStatus': disaster_recovery_status}
        else:
            status['disasterRecoveryStatus'] = disaster_recovery_status
        cr_status['status'] = status
        self.update_custom_resource_status(cr_status)

    def check_backup_daemon(self, name: str = 'rabbitmq-backup-daemon') -> bool:
        backup_daemon_enabled = os.getenv("BACKUP_DAEMON_ENABLED")
        logger.debug(f'Backup daemon enabled: {backup_daemon_enabled}')
        if self._spec.get('disasterRecovery'):
            mode = self._spec.get('disasterRecovery').get('mode', None)
        else:
            mode = 'None'
        timeout = self._spec.get('global').get('podReadinessTimeout', 180)
        if (backup_daemon_enabled in positive_values) and mode != 'standby':
            deployment = self._apps_v1_api.read_namespaced_deployment(name=name, namespace=self._workspace)
            if deployment is not None:
                backup_helper = BackupHelper(namespace=self._workspace, custom_url=backup_daemon_url, verify=self.get_backup_daemon_auth())
                result = backup_helper.check_backup_daemon_readiness(timeout)
                logger.debug(f'Backup daemon is ready: {result}')
                return result
        return True


def with_attempts(attempts=3, timeout=10, not_found_reason='not found'):
    def decorator(func):
        def wrapper(*args, attempts=attempts, timeout=timeout, **kwargs):
            reason = None
            while attempts:
                try:
                    return func(*args, **kwargs)
                except requests.RequestException:
                    reason = None
                    attempts -= 1
                    time.sleep(timeout)
                except DisasterRecoveryException:
                    reason = not_found_reason
                    attempts -= 1
                    time.sleep(timeout)
            return reason
        return wrapper
    return decorator


def perform_backup(namespace: str, backup_daemon_auth) -> None:
    logger.info("Perform backup operation")
    backup_helper = BackupHelper(namespace=namespace, custom_url=backup_daemon_url, verify=backup_daemon_auth)
    backup_id = _perform_backup_with_retry(backup_helper)
    if backup_id is None:
        raise DisasterRecoveryException(message='can not perform full backup')
    logger.info(f"Backup was performed: {backup_id}, check job status")
    if not backup_helper.check_job_status(backup_id):
        raise DisasterRecoveryException(message='full backup was performed but was not succeeded')
    logger.info(f"Backup {backup_id} was performed successfully")


@with_attempts(attempts=3, timeout=10)
def _perform_backup_with_retry(backup_helper):
    backup_id = backup_helper.perform_full_backup()
    return backup_id


def restore_last_backup(namespace: str, region: str, no_wait: bool, backup_daemon_auth) -> None:
    logger.info("Perform restore operation")
    backup_helper = BackupHelper(namespace=namespace, custom_url=backup_daemon_url, verify=backup_daemon_auth)
    task_id = _restore_last_backup_with_retry(backup_helper, region)
    if no_wait and task_id == 'not found':
        logger.info("There is no backup from another region to restore. "
                    "Switchover process will be continued because noWait parameter is True")
        return
    if task_id is None or task_id == 'not found':
        raise DisasterRecoveryException(message='can not restore last full backup')
    logger.info(f"Backup was restored: {task_id}, check job status")
    if not backup_helper.check_job_status(task_id):
        raise DisasterRecoveryException(message='backup was restored but restore task was not succeeded')
    logger.info(f"Backup was restored successfully")

@with_attempts(attempts=3, timeout=10, not_found_reason='not found')
def _restore_last_backup_with_retry(backup_helper: BackupHelper, region: str) -> str:
    backup_id = backup_helper.get_latest_backup_id_from_another_cluster(region)
    if backup_id is None:
        raise DisasterRecoveryException(message="last backup from another region is not found")
    logger.info(f"Restore backup {backup_id}")
    task_id = backup_helper.restore(backup_id)
    return task_id


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.watching.server_timeout = KOPFTIMEOUT
    settings.watching.client_timeout = KOPFTIMEOUT + 60
    settings.scanning.disabled = True
    settings.posting.enabled = False


@kopf.timer(api_group, cr_version, 'rabbitmqservices', interval=900, initial_delay=900)
def shovel_monitoring(spec,retry,  **kwargs):
    kub_helper = KubernetesHelper(spec)
    enabled = False
    try:
        enabled = bool(util.strtobool(os.getenv("ENABLE_SHOVEL_MONITORING", "false")))
    except Exception:
        enabled = False

    if enabled:
        if not kub_helper.check_shovel_state():
            logger.warning("Shovel monitoring detected that some shovels are not running properly. Restarting shovel plugin...")
            kub_helper.nodes_restart_shovel_plugin()
            if not kub_helper.check_shovel_state():
                logger.warning("Some shovels are not running properly after restart.")
            else:
                logger.info("All shovels are running properly after restart.")


@kopf.on.create(api_group, cr_version, 'rabbitmqservices')
def on_create(body, meta, spec, status, **kwargs):
    kub_helper = KubernetesHelper(spec)
    logger.info("New CRD is created")
    validate_spec(spec)
    kub_helper.initiate_status()
    # kopf.event(body, type='Warning', reason='SomeReason', message="Cannot do something")
    # todo create config map only when it doesn't exist or remove previous one
    # we do not need to create secret - it should be already present
    rabbit_exist_before = kub_helper.is_any_rmq_statefulset_present()
    if kub_helper.is_ipv6_enabled() and kub_helper.is_hostpath():
        kub_helper.update_status(
            FAILED,
            "Error",
            "Hostpath configuration in IPv6 environment is not supported"
        )
        time.sleep(5)
        raise kopf.PermanentError("Hostpath configuration in IPv6 environment is not supported.")
    if not kub_helper.is_rmq_secret_present():
        kub_helper.update_status(
            FAILED,
            "Error",
            "please create RabbitMQ secret"
        )
        time.sleep(5)
        raise kopf.PermanentError("please create RabbitMQ secret.")
    if not kub_helper.is_hostpath() and (kub_helper._pvs or kub_helper._nodes or kub_helper._selectors):
        kub_helper.update_status(
            FAILED,
            "Error",
            "Rabbitmq nodes, pvs or selectors must be specified only in hostpath configuration"
        )
        time.sleep(5)
        raise kopf.PermanentError("Rabbitmq nodes, pvs or selectors must be specified only in hostpath configuration.")

    kub_helper.update_config()
    kub_helper.update_services()
    if kub_helper.is_nodeport_required():
        kub_helper.configure_nodeport_service()
    if kub_helper.is_telegraf_enabled():
        kub_helper.update_telegraf_deployment()
    if kub_helper.is_clean_rabbitmq_pvs() and rabbit_exist_before:
        kub_helper.set_clean_pv_flag_and_delete_pods()
    if not kub_helper.is_auto_reboot():
        perform_rabbit_pods_readiness_check(kub_helper)
        kub_helper.check_cluster_state()
    elif rabbit_exist_before and not kub_helper.is_clean_rabbitmq_pvs():
        kub_helper.reboot_pods()
    else:
        perform_rabbit_pods_readiness_check(kub_helper)
    kub_helper.enable_feature_flags()
    if not kub_helper.check_backup_daemon():
        kub_helper.update_status(
            FAILED,
            "Error",
            "RabbitMQ backup daemon is not ready"
        )
        time.sleep(5)
        raise kopf.PermanentError("RabbitMQ backup daemon is not ready.")
    if not kub_helper.wait_test_result() or not kub_helper.is_run_tests():
        kub_helper.update_status(
            SUCCESSFUL,
            "None",
            "RabbitMQ service installed successfully"
        )
    if kub_helper.is_run_tests():
        logger.info("Wait running tests...")
        if kub_helper.wait_test_result():
            if kub_helper.wait_test_deployment_result():
                kub_helper.update_status(
                    SUCCESSFUL,
                    "None",
                    "RabbitMQ service installed and tested successfully"
                )
            else:
                kub_helper.update_status(
                    FAILED,
                    "Error",
                    "RabbitMQ tests failed"
                )
                time.sleep(5)
                raise kopf.PermanentError("RabbitMQ tests failed.")


def validate_spec(spec):
    pass


# @kopf.on.field(api_group, 'v1', 'rabbitmqservices', field='spec.rabbitmq.replicas')
# def update_lst(body, meta, spec, status, old, new, **kwargs):
#     print(f'Handling the FIELD = {old} -> {new}')

def spec_filter_with_excluded_field(diff, excluded_field: str) -> bool:
    events = [event for event in diff if event[1][0] == 'spec']
    for event in events:
        if event[0] == 'change' and event[1][1] == excluded_field:
            continue
        else:
            return True
    return False


def exclude_disaster_recovery_field(diff, **kwargs):
    return spec_filter_with_excluded_field(diff, 'disasterRecovery')


def change_rabbitmq_config(meta, **kwargs):
    return meta['name'] == configmap_name


def change_rabbitmq_secret(meta, **kwargs):
    return meta['name'] == secret_name


def check_cluster_state(spec, v1_apps_api, namespace):
    if 'ssl_enabled' in spec['rabbitmq'] and spec['rabbitmq']['ssl_enabled']:
        rabbit_helper = RabbitHelper(get_user_from_secret(v1_apps_api, namespace), get_password_from_secret(v1_apps_api, namespace),
                                     'https://rabbitmq.' + namespace + '.svc:15671', ssl=CA_CERT_PATH)
    else:
        rabbit_helper = RabbitHelper(get_user_from_secret(v1_apps_api, namespace), get_password_from_secret(v1_apps_api, namespace),
                                     'http://rabbitmq.' + namespace + '.svc:15672')
    for i in range(0, 30):
        time.sleep(30)
        if rabbit_helper.is_cluster_alive(spec['rabbitmq']['replicas']):
            return
    time.sleep(5)
    raise kopf.PermanentError("RabbitMQ cluster fails to come up.")


def get_user_from_secret(v1_apps_api, namespace):
    v1secret = v1_apps_api.read_namespaced_secret(name=secret_name, namespace=namespace)
    return base64.b64decode(v1secret.data['user']).decode()


def get_password_from_secret(v1_apps_api, namespace):
    v1secret = v1_apps_api.read_namespaced_secret(name=secret_name, namespace=namespace)
    return base64.b64decode(v1secret.data['password']).decode()


@kopf.on.update('v1', "configmap", when=change_rabbitmq_config)
def on_update_configmap(diff, **kwargs):
    sleep(TIME_TO_WAIT_CONFIGMAP_HANDLER)
    custom_objects_api = client.CustomObjectsApi()
    namespace = KubernetesHelper.get_namespace()
    cr = custom_objects_api.get_namespaced_custom_object(
        group=api_group,
        version=cr_version,
        namespace=namespace,
        plural='rabbitmqservices',
        name='rabbitmq-service'
    )

    status = cr.get('status')
    is_not_in_progress = len(status['conditions']) > 1 and any(condition.get('type') in [SUCCESSFUL, FAILED] for condition in status['conditions'])

    if is_not_in_progress:
        logger.info("rabbitmq configmap changes: %s" % diff)
        spec = cr.get('spec')
        if 'auto_reboot' in spec['rabbitmq'] and spec['rabbitmq']['auto_reboot'] is True:
            v1_apps_api = client.CoreV1Api()
            pods = v1_apps_api.list_namespaced_pod(namespace)
            for pod in pods.items:
                if "rmqlocal" in pod.metadata.name:
                    v1_apps_api.delete_namespaced_pod(pod.metadata.name, namespace)
                    check_cluster_state(spec, v1_apps_api, namespace)
        logger.info("all pods have been rebooted")


@kopf.on.update('v1', "secret", when=change_rabbitmq_secret)
def on_update_secret(diff, **kwargs):
    sleep(TIME_TO_WAIT_SECRET_HANDLER)
    logger.info("starting changing credentials procedure")
    custom_objects_api = client.CustomObjectsApi()
    namespace = KubernetesHelper.get_namespace()
    cr = custom_objects_api.get_namespaced_custom_object(
        group=api_group,
        version=cr_version,
        namespace=namespace,
        plural='rabbitmqservices',
        name='rabbitmq-service'
    )
    spec = cr.get('spec')
    kub_helper = KubernetesHelper(spec)
    status = cr.get('status')
    is_in_progress = not any(condition.get('type') in [SUCCESSFUL, FAILED] for condition in status['conditions'])
    logger.info("waiting for rmq CR to proceed")
    wait_time = 0
    while is_in_progress and wait_time < 900:
        wait_time = wait_time + 15
        sleep(15)
        cr = custom_objects_api.get_namespaced_custom_object(
            group=api_group,
            version=cr_version,
            namespace=namespace,
            plural='rabbitmqservices',
            name='rabbitmq-service'
        )
        status = cr.get('status')
        is_in_progress = not any(condition.get('type') in [SUCCESSFUL, FAILED] for condition in status['conditions'])
    logger.info("rmq CR processing is completed. Rabbitmq secret changes: %s" % diff)
    kub_helper.initiate_status()
    old_username = None
    new_username = None
    for df in diff:
        if len(df) > 1 and df[1] == username_change_attr:
            old_username = base64.b64decode(df[2]).decode()
            new_username = base64.b64decode(df[3]).decode()
    if old_username != new_username and old_username is not None:
        kub_helper.deactivate_old_user(old_username)
    else:
        logger.info("changing password...")
        kub_helper.change_password()
    logger.info("rebooting all pods in rabbitmq namespace")
    v1_apps_api = client.CoreV1Api()
    pods = v1_apps_api.list_namespaced_pod(namespace)
    for pod in pods.items:
        if "rmqlocal" in pod.metadata.name:
            v1_apps_api.delete_namespaced_pod(pod.metadata.name, namespace)
            kub_helper.check_cluster_state()
    pods = v1_apps_api.list_namespaced_pod(namespace)
    for pod in pods.items:
        if "rabbitmq-backup-daemon" in pod.metadata.name:
            v1_apps_api.delete_namespaced_pod(pod.metadata.name, namespace)
    logger.info("all pods have been rebooted, changing credentials completed")
    kub_helper.update_status(SUCCESSFUL,
                             "None",
                             "All pods have been rebooted, changing credentials completed")


@kopf.on.update(api_group, cr_version, 'rabbitmqservices', when=exclude_disaster_recovery_field)
def on_update(body, meta, spec, status, old, new, diff, **kwargs):
    logger.info("cr changes:" + str(diff))
    print('Handling the diff')
    kub_helper = KubernetesHelper(spec)
    kub_helper.initiate_status()
    old_pods_count = kub_helper.get_rabbit_pods_count()
    if kub_helper.is_run_tests_only() and kub_helper.is_run_tests():
        logger.info("Wait running tests...")
        if not kub_helper.wait_test_result():
            kub_helper.update_status(
                SUCCESSFUL,
                "None",
                "RabbitMQ service updated successfully"
            )
        else:
            if kub_helper.wait_test_deployment_result():
                kub_helper.update_status(
                    SUCCESSFUL,
                    "None",
                    "RabbitMQ service updated and tested successfully"
                )
            else:
                kub_helper.update_status(
                    FAILED,
                    "Error",
                    "RabbitMQ tests failed"
                )
                time.sleep(5)
                raise kopf.PermanentError(
                    "RabbitMQ tests failed.")
        return
    if kub_helper.is_ipv6_enabled() and kub_helper.is_hostpath():
        kub_helper.update_status(
            FAILED,
            "Error",
            "Hostpath configuration in IPv6 environment is not supported"
        )
        time.sleep(5)
        raise kopf.PermanentError("Hostpath configuration in IPv6 environment is not supported.")
    if kub_helper.is_hostpath_installed() != kub_helper.is_hostpath():
        kub_helper.update_status(
            FAILED,
            "Error",
            "Changing storage configuration is not allowed"
        )
        time.sleep(5)
        raise kopf.PermanentError("Changing storage configuration is not allowed.")
    # TODO validate that user or secret cookie weren't changed
    if not kub_helper.is_hostpath() and (kub_helper._pvs or kub_helper._nodes or kub_helper._selectors):
        kub_helper.update_status(
            FAILED,
            "Error",
            "Rabbitmq nodes, pvs or selectors must be specified only in hostpath configuration"
        )
        time.sleep(5)
        raise kopf.PermanentError("Rabbitmq nodes, pvs or selectors must be specified only in hostpath configuration.")
    kub_helper.update_config()
    kub_helper.update_services()
    if kub_helper.is_nodeport_required():
        kub_helper.configure_nodeport_service()
    # kub_helper.check_cluster_state()
    if kub_helper.is_telegraf_enabled():
        kub_helper.update_telegraf_deployment()
    if kub_helper.is_clean_rabbitmq_pvs():
        kub_helper.set_clean_pv_flag_and_delete_pods()
    if not kub_helper.is_auto_reboot():
        perform_rabbit_pods_readiness_check(kub_helper)
        kub_helper.check_cluster_state()
    elif not kub_helper.is_clean_rabbitmq_pvs():
        kub_helper.reboot_pods(old_pods_count)
    else:
        perform_rabbit_pods_readiness_check(kub_helper)
    kub_helper.enable_feature_flags()
    pprint.pprint(list(diff))
    if not kub_helper.check_backup_daemon():
        kub_helper.update_status(
            FAILED,
            "Error",
            "RabbitMQ backup daemon is not ready"
        )
        time.sleep(5)
        raise kopf.PermanentError("RabbitMQ backup daemon is not ready.")
    if not kub_helper.wait_test_result() or not kub_helper.is_run_tests():
        kub_helper.update_status(
            SUCCESSFUL,
            "None",
            "RabbitMQ service updated successfully"
        )
    if kub_helper.is_run_tests():
        logger.info("running tests...")
        if kub_helper.wait_test_result():
            if kub_helper.wait_test_deployment_result():
                kub_helper.update_status(
                    SUCCESSFUL,
                    "None",
                    "RabbitMQ service updated and tested successfully"
                )
            else:
                kub_helper.update_status(
                    FAILED,
                    "Error",
                    "RabbitMQ tests failed"
                )
                time.sleep(5)
                raise kopf.PermanentError("RabbitMQ tests failed.")


def perform_rabbit_pods_readiness_check(kub_helper: KubernetesHelper):
    if not kub_helper.check_rabbit_pods_readiness():
        kub_helper.update_status(
            FAILED,
            "Error",
            "RabbitMQ pods are not ready"
        )
        time.sleep(5)
        raise kopf.PermanentError("RabbitMQ pods are not ready")
    else:
        logger.info("RabbitMQ pods are ready")


@kopf.on.delete(api_group, cr_version, 'rabbitmqservices', optional=optional_delete)
def on_delete(spec, **kwargs):
    kub_helper = KubernetesHelper(spec)
    logger.info("Deleting crd")
    kub_helper.delete_resources()


def switchover_annotation_changed(diff, logger, **kwargs):
    for event in diff:
        if event[0] == 'change' \
                and event[1][0] == 'metadata' \
                and event[1][1] == 'annotations' \
                and event[1][2] == 'switchoverRetry':
            return True
    logger.debug("switchover_annotation_changed filter with False")
    return False


@kopf.on.update(api_group,
                cr_version,
                'rabbitmqservices',
                field='metadata.annotations.switchoverRetry',
                old=kopf.ABSENT,
                new=kopf.PRESENT)
@kopf.on.update(api_group, cr_version, 'rabbitmqservices', when=switchover_annotation_changed)
@kopf.on.field(api_group, cr_version, 'rabbitmqservices', field='spec.disasterRecovery.mode')
def set_disaster_recovery_state(spec, status, namespace, diff, **kwargs):
    mode = spec.get('disasterRecovery').get('mode', None)
    if mode is None:
        raise kopf.PermanentError("disaster recovery mode is not specified")
    no_wait: bool = spec.get('disasterRecovery').get('noWait', False)
    status_mode = status.get('disasterRecoveryStatus', None)
    if status_mode is not None:
        status_mode = status_mode.get('mode', None)
    kub_helper = KubernetesHelper(spec)
    kub_helper.update_disaster_recovery_status(mode=mode,
                                               status="running",
                                               message="The switchover process for RabbitMQ Service has been started")

    status = "done"
    message = "replication has finished successfully" if status_mode is not None else "success installation"
    try:
        logger.info(f"Start switchover with mode: {mode} and no-wait: {no_wait}, current status mode is: {status_mode}")
        if mode == 'standby' or mode == 'disable':
            if status_mode is not None and status_mode != 'disable' and status_mode != 'standby':
                perform_backup(namespace, kub_helper.get_backup_daemon_auth())
            kub_helper.scale_down_backup_daemon(namespace)

        if mode == 'active':
            kub_helper.scale_up_backup_daemon(namespace)
            if status_mode is not None:
                region = dev_region if dev_region else spec.get('disasterRecovery').get('region', None)
                restore_last_backup(namespace, region, no_wait, kub_helper.get_backup_daemon_auth())
                logger.info("Switchover finished successfully")
    except DisasterRecoveryException as e:
        status = "failed"
        message = e.message
        logger.error(f"Switchover failed: {message}")
    except Exception as e:
        status = "failed"
        message = e.__str__()
        logger.error(f"Switchover failed: {message}")
    kub_helper.update_disaster_recovery_status(mode=mode, status=status, message=message)
