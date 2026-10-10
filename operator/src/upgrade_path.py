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

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

_VERSION_RE = re.compile(r"(\d+)\.(\d+)")
VERSION_UNREADABLE = "running version could not be determined"


@dataclass(frozen=True)
class MajorMinor:
    major: int
    minor: int

    def __str__(self):
        return f"{self.major}.{self.minor}"

    def __lt__(self, other):
        return (self.major, self.minor) < (other.major, other.minor)


@dataclass(frozen=True)
class UpgradeStep:
    version: str
    image: str
    intermediate: bool


@dataclass
class UpgradePlan:
    steps: list = field(default_factory=list)
    error: str | None = None
    running: str = ""
    target: str = ""

    @property
    def accepted(self):
        return self.error is None


def default_properties_path():
    return os.environ.get("RABBITMQ_PROPERTIES_PATH", "/opt/operator/rabbitmq.properties")


def parse_major_minor(text):
    if text is None:
        return None
    match = _VERSION_RE.search(str(text))
    if not match:
        return None
    return MajorMinor(int(match.group(1)), int(match.group(2)))


def load_properties(path):
    lines = {}
    intermediates = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "intermediateVersions":
            intermediates = [part.strip() for part in value.split(",") if part.strip()]
        elif key.startswith("rabbitmq.") and key.endswith(".version"):
            major_text = key.split(".")[1]
            lines[int(major_text)] = value
    return {"lines": lines, "intermediateVersions": intermediates}


def validate_line_versions(lines):
    for major, value in sorted(lines.items()):
        parsed = parse_major_minor(value)
        if parsed is None or parsed.major != int(major):
            return f"line {major} version {value} does not keep major {major}"
    return None


def version_from_overview(body):
    if not body:
        return None
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return parse_major_minor(payload.get("rabbitmq_version"))


def resolve_pod_version(exec_output, overview_body):
    parsed = parse_major_minor(exec_output)
    if parsed is not None:
        return parsed
    return version_from_overview(overview_body)


def oldest_running(versions):
    if not versions or any(version is None for version in versions):
        return None, VERSION_UNREADABLE
    return min(versions), None


def version_from_image_name(image):
    if not image:
        return None
    without_digest = str(image).split("@", 1)[0]
    slash = without_digest.rfind("/")
    colon = without_digest.rfind(":")
    repository = without_digest[:colon] if colon > slash else without_digest
    name = repository.rsplit("/", 1)[-1]
    marker = "rabbitmq-image-"
    index = name.rfind(marker)
    if index < 0:
        return None
    suffix = name[index + len(marker):]
    parsed = parse_major_minor(suffix)
    if parsed is None or suffix != str(parsed):
        return None
    return parsed


def images_by_version(images):
    indexed = {}
    for image in images or []:
        parsed = version_from_image_name(image)
        if parsed is not None:
            indexed[str(parsed)] = image
    return indexed


def target_from_properties(lines, docker_image):
    if not lines:
        return None
    if docker_image and "rabbitmq-image-3" in docker_image:
        return lines.get(3)
    return lines[max(lines)]


def has_intermediate_step(plan):
    if any(step.intermediate for step in plan.steps):
        return True
    if not plan.error or "missing image " not in plan.error:
        return False
    missing = plan.error.rsplit("missing image ", 1)[-1].strip()
    return missing != plan.target


def missing_intermediate_directories(versions, root):
    base = Path(root)
    return [version for version in versions if not (base / version / "Dockerfile").is_file()]


def nodes_reached(versions, step_version):
    expected = parse_major_minor(step_version)
    if expected is None or not versions:
        return False
    return all(version == expected for version in versions)


def may_apply_step(plan, node_versions, step_index):
    if plan.error or step_index < 0 or step_index >= len(plan.steps):
        return False
    if step_index == 0:
        return True
    previous = plan.steps[step_index - 1]
    return nodes_reached(node_versions, previous.version)


def plan_upgrade(
    initial,
    target,
    intermediate_versions,
    intermediate_images,
    target_image,
    fresh_install=False,
    pods_use_target_image=True,
):
    running_text = "" if initial is None else str(initial)
    target_text = "" if target is None else str(target)
    target_mm = parse_major_minor(target)
    if target_mm is None:
        return UpgradePlan(
            error=f"running {running_text}, target version is absent",
            running=running_text,
            target=target_text,
        )
    target_key = str(target_mm)
    if fresh_install:
        if not target_image:
            return UpgradePlan(
                error=f"running {running_text}, target {target_key}, missing image {target_key}",
                running=running_text,
                target=target_key,
            )
        return UpgradePlan(
            steps=[UpgradeStep(target_key, target_image, False)],
            running=running_text,
            target=target_key,
        )

    initial_mm = parse_major_minor(initial)
    if initial_mm is None:
        return UpgradePlan(
            error=VERSION_UNREADABLE,
            running=running_text,
            target=target_key,
        )
    running_text = str(initial_mm)
    if initial_mm == target_mm and pods_use_target_image:
        return UpgradePlan(steps=[], running=running_text, target=target_key)

    steps = []
    cursor = initial_mm
    images = intermediate_images or {}
    for entry in intermediate_versions:
        entry_mm = parse_major_minor(entry)
        if entry_mm is None:
            continue
        if entry_mm == initial_mm or entry_mm == target_mm:
            continue
        if not (cursor < entry_mm < target_mm):
            continue
        image = images.get(str(entry_mm))
        if not image:
            return UpgradePlan(
                error=f"running {running_text}, target {target_key}, missing image {entry_mm}",
                running=running_text,
                target=target_key,
            )
        steps.append(UpgradeStep(str(entry_mm), image, True))
        cursor = entry_mm

    if cursor < target_mm or (initial_mm == target_mm and not pods_use_target_image):
        if not target_image:
            return UpgradePlan(
                error=f"running {running_text}, target {target_key}, missing image {target_key}",
                running=running_text,
                target=target_key,
            )
        steps.append(UpgradeStep(target_key, target_image, False))
    return UpgradePlan(steps=steps, running=running_text, target=target_key)
