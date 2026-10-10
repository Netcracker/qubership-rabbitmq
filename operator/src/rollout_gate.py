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

import os
import sys
import time

from kubernetes import client, config
from kubernetes.stream import stream

from upgrade_path import (
    VERSION_UNREADABLE,
    default_properties_path,
    has_intermediate_step,
    images_by_version,
    load_properties,
    parse_major_minor,
    plan_upgrade,
    target_from_properties,
)

DEPLOYMENT = "rabbitmq-operator"
POLL_SECONDS = 5
VERSION_ATTEMPTS = 6
ROLLOUT_TIMEOUT_SECONDS = 300


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
    return str(min(versions)), None


def _roll_deployment(apps, namespace, operator_image):
    apps.patch_namespaced_deployment(
        DEPLOYMENT,
        namespace,
        {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {"name": DEPLOYMENT, "image": operator_image},
                        ]
                    }
                }
            }
        },
    )
    deadline = time.time() + ROLLOUT_TIMEOUT_SECONDS
    while time.time() < deadline:
        deployment = apps.read_namespaced_deployment(DEPLOYMENT, namespace)
        status = deployment.status
        desired = deployment.spec.replicas or 1
        image = next(
            (container.image for container in deployment.spec.template.spec.containers if container.name == DEPLOYMENT),
            None,
        )
        ready = (
            image == operator_image
            and (status.observed_generation or 0) >= deployment.metadata.generation
            and (status.updated_replicas or 0) >= desired
            and (status.ready_replicas or 0) >= desired
            and not status.unavailable_replicas
        )
        if ready:
            print("operator rolled to the chart image", flush=True)
            return
        time.sleep(POLL_SECONDS)
    sys.exit("operator rollout did not become Ready")


def main():
    namespace = os.environ["NAMESPACE"]
    operator_image = os.environ["OPERATOR_IMAGE"]
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

    properties = load_properties(default_properties_path())
    target = target_from_properties(properties["lines"], docker_image)
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

    plan = plan_upgrade(
        running,
        target,
        properties["intermediateVersions"],
        images_by_version(intermediate_images),
        docker_image,
    )
    if not has_intermediate_step(plan):
        print(f"running {running}, target {plan.target}, no intermediate step, leaving the operator", flush=True)
        return
    print(f"running {running}, target {plan.target}, rolling the operator before the custom resource changes", flush=True)
    _roll_deployment(apps, namespace, operator_image)


if __name__ == "__main__":
    main()
