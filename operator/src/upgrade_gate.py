# Copyright 2024-2026 NetCracker Technology Corporation
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
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

from kubernetes import client, config
from kubernetes.stream import stream

from upgrade_path import (
    VERSION_UNREADABLE,
    default_properties_path,
    images_by_version,
    load_properties,
    operator_must_stop,
    parse_major_minor,
    plan_upgrade,
    target_from_properties,
)

DEPLOYMENT = "rabbitmq-operator"
SECRET = "rabbitmq-default-secret"
POLL_SECONDS = 5
VERSION_ATTEMPTS = 6
ROLLOUT_TIMEOUT_SECONDS = 300
_MIN_LINE_3 = (3, 13)


def _oldest_running(core, namespace):
    pods = core.list_namespaced_pod(namespace, label_selector="app=rmqlocal").items
    if not pods:
        return None, None
    versions = []
    for pod in pods:
        output = stream(
            core.connect_get_namespaced_pod_exec,
            pod.metadata.name,
            namespace,
            command=["rabbitmqctl", "version"],
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
        parsed = parse_major_minor(output)
        if parsed is None:
            return None, VERSION_UNREADABLE
        versions.append(parsed)
    return min(versions), None


def _statefulset_images(apps, namespace):
    statefulsets = apps.list_namespaced_stateful_set(namespace, label_selector="app=rmqlocal").items
    images = []
    for statefulset in statefulsets:
        containers = statefulset.spec.template.spec.containers or []
        if containers and containers[0].image:
            images.append(containers[0].image)
    return images


def _deprecated_features_url():
    return os.environ["RABBITMQ_URL"].rstrip("/") + "/api/deprecated-features/used"


def _classic_mirroring_in_use(core, namespace):
    secret = core.read_namespaced_secret(SECRET, namespace)
    user = base64.b64decode(secret.data["user"]).decode()
    password = base64.b64decode(secret.data["password"]).decode()
    url = _deprecated_features_url()
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    context = ssl.create_default_context()
    if url.startswith("https://"):
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    print(f"checking deprecated features at {url}", flush=True)
    try:
        with urllib.request.urlopen(request, context=context, timeout=60) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        sys.exit(f"deprecated-features/used returned {exc.code}")
    except Exception as exc:
        sys.exit(f"deprecated-features/used failed: {exc}")
    if not isinstance(payload, list):
        sys.exit("deprecated-features/used did not return a list")
    names = [item.get("name") for item in payload if isinstance(item, dict)]
    print(f"deprecated features in use: {names}", flush=True)
    return "classic_queue_mirroring" in names


def _reject_unsafe_major_upgrade(core, namespace, running, target):
    if running is None or target is None or target.major < 4 or running.major >= 4:
        return
    if (running.major, running.minor) < _MIN_LINE_3:
        sys.exit(
            f"running {running}, target {target}, "
            f"upgrade to 4.x requires RabbitMQ 3.13 or newer"
        )
    if (running.major, running.minor) != _MIN_LINE_3:
        return
    if _classic_mirroring_in_use(core, namespace):
        sys.exit(
            f"running {running}, target {target}, "
            f"classic mirrored queues are still in use"
        )


def _scale_operator(apps, namespace, replicas):
    apps.patch_namespaced_deployment(
        DEPLOYMENT,
        namespace,
        [{"op": "replace", "path": "/spec/replicas", "value": replicas}],
    )
    deadline = time.time() + ROLLOUT_TIMEOUT_SECONDS
    while time.time() < deadline:
        deployment = apps.read_namespaced_deployment(DEPLOYMENT, namespace)
        status = deployment.status
        ready = status.ready_replicas or 0
        current = status.replicas or 0
        reached = (deployment.spec.replicas or 0) == replicas and current == ready == (replicas if replicas else 0)
        if replicas == 0:
            reached = (deployment.spec.replicas or 0) == 0 and not current and not ready
        if reached:
            print(f"operator scaled to {replicas}", flush=True)
            return
        time.sleep(POLL_SECONDS)
    raise RuntimeError(f"operator did not scale to {replicas}")


def main():
    namespace = os.environ["NAMESPACE"]
    docker_image = os.environ.get("DOCKER_IMAGE", "")
    intermediate_images = [
        item.strip() for item in os.environ.get("INTERMEDIATE_IMAGES", "").split(",") if item.strip()
    ]
    config.load_incluster_config()
    core = client.CoreV1Api()
    apps = client.AppsV1Api()
    try:
        apps.read_namespaced_deployment(DEPLOYMENT, namespace)
    except client.ApiException as exc:
        if exc.status == 404:
            print("operator deployment is absent, nothing to roll", flush=True)
            return
        raise

    images = _statefulset_images(apps, namespace)
    if docker_image and images and all(image == docker_image for image in images):
        print("RabbitMQ image is unchanged, leaving the operator", flush=True)
        return

    properties = load_properties(default_properties_path())
    target_text = target_from_properties(properties["lines"], docker_image)
    target = parse_major_minor(target_text)
    running = None
    read_error = VERSION_UNREADABLE
    for _ in range(VERSION_ATTEMPTS):
        running, read_error = _oldest_running(core, namespace)
        if read_error is None:
            break
        time.sleep(POLL_SECONDS)
    if running is None and read_error is None:
        print("no RabbitMQ pods, nothing to roll", flush=True)
        return
    if read_error:
        sys.exit(read_error)

    _reject_unsafe_major_upgrade(core, namespace, running, target)
    plan = plan_upgrade(
        str(running),
        target_text or "",
        properties["intermediateVersions"],
        images_by_version(intermediate_images),
        docker_image,
    )
    if plan.error:
        sys.exit(plan.error)
    if not operator_must_stop(plan):
        print(f"running {running}, target {plan.target}, no version step, leaving the operator", flush=True)
        return
    print(f"running {running}, target {plan.target}, scaling the operator to 0 before the custom resource changes", flush=True)
    try:
        _scale_operator(apps, namespace, 0)
    except Exception as exc:
        print(f"{exc}, restoring operator replicas", flush=True)
        try:
            _scale_operator(apps, namespace, 1)
        except Exception as restore_error:
            sys.exit(f"{exc}; failed to restore operator: {restore_error}")
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
