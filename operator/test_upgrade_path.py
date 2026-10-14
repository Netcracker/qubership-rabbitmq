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

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import upgrade_path


TARGET_IMAGE = "line-image"
INTERMEDIATE = {
    "4.2": "intermediate-4.2",
    "4.7": "intermediate-4.7",
    "5.0": "intermediate-5.0",
}


def _versions(plan):
    return [step.version for step in plan.steps]


class UpgradePathTest(unittest.TestCase):
    def test_shipped_file_skips_intermediate_equal_to_target(self):
        for initial in ("4.0.1", "4.1.2"):
            plan = upgrade_path.plan_upgrade(initial, "4.2", ["4.2"], INTERMEDIATE, TARGET_IMAGE)
            self.assertTrue(plan.accepted)
            self.assertEqual(_versions(plan), ["4.2"])
            self.assertFalse(plan.steps[0].intermediate)
            self.assertEqual(plan.steps[0].image, TARGET_IMAGE)

    def test_initial_equal_to_intermediate_skips_that_image(self):
        plan = upgrade_path.plan_upgrade(
            "4.2", "5.1", ["4.2", "4.7", "5.0"], INTERMEDIATE, TARGET_IMAGE
        )
        self.assertEqual(_versions(plan), ["4.7", "5.0", "5.1"])
        self.assertTrue(plan.steps[0].intermediate)
        self.assertEqual(plan.steps[0].image, "intermediate-4.7")
        self.assertFalse(plan.steps[-1].intermediate)

    def test_walks_declared_stops_then_target(self):
        plan = upgrade_path.plan_upgrade(
            "4.0", "5.1", ["4.2", "4.7", "5.0"], INTERMEDIATE, TARGET_IMAGE
        )
        self.assertEqual(_versions(plan), ["4.2", "4.7", "5.0", "5.1"])
        self.assertTrue(all(step.intermediate for step in plan.steps[:-1]))
        self.assertEqual(plan.steps[0].image, "intermediate-4.2")
        self.assertFalse(plan.steps[-1].intermediate)
        self.assertEqual(plan.steps[-1].image, TARGET_IMAGE)

    def test_later_source_skips_earlier_stops(self):
        plan = upgrade_path.plan_upgrade(
            "4.7.1", "5.1", ["4.2", "4.7", "5.0"], INTERMEDIATE, TARGET_IMAGE
        )
        self.assertEqual(_versions(plan), ["5.0", "5.1"])
        self.assertNotIn("4.2", _versions(plan))

    def test_no_intermediate_between_uses_target_only(self):
        plan = upgrade_path.plan_upgrade("5.0.0", "5.1", ["4.2", "4.7", "5.0"], INTERMEDIATE, TARGET_IMAGE)
        self.assertEqual(_versions(plan), ["5.1"])
        self.assertFalse(plan.steps[0].intermediate)

    def test_downgrade_is_rejected(self):
        plan = upgrade_path.plan_upgrade("4.3.6", "4.2", ["4.2"], INTERMEDIATE, TARGET_IMAGE)
        self.assertFalse(plan.accepted)
        self.assertEqual(plan.steps, [])
        self.assertIn("downgrade", plan.error)
        self.assertFalse(upgrade_path.operator_must_stop(plan))

    def test_direct_minor_upgrade_stops_the_operator(self):
        plan = upgrade_path.plan_upgrade("4.2.9", "4.3", ["4.2"], INTERMEDIATE, TARGET_IMAGE)
        self.assertTrue(plan.accepted)
        self.assertEqual(_versions(plan), ["4.3"])
        self.assertFalse(plan.steps[0].intermediate)
        self.assertTrue(upgrade_path.operator_must_stop(plan))

    def test_patch_does_not_change_identity(self):
        self.assertEqual(upgrade_path.parse_major_minor("4.2.1"), upgrade_path.parse_major_minor("4.2.9"))
        plan = upgrade_path.plan_upgrade("4.2.1", "4.2.9", ["4.2"], INTERMEDIATE, TARGET_IMAGE)
        self.assertEqual(plan.steps, [])

    def test_fresh_install_does_not_walk_the_list(self):
        plan = upgrade_path.plan_upgrade(
            None, "4.2", ["4.2", "4.7"], INTERMEDIATE, TARGET_IMAGE, fresh_install=True
        )
        self.assertEqual(_versions(plan), ["4.2"])
        self.assertFalse(plan.steps[0].intermediate)

    def test_missing_image_rejects_before_a_step_can_be_applied(self):
        plan = upgrade_path.plan_upgrade("4.0", "5.1", ["4.2", "4.7", "5.0"], {}, TARGET_IMAGE)
        self.assertFalse(plan.accepted)
        self.assertIn("4.0", plan.error)
        self.assertIn("5.1", plan.error)
        self.assertIn("4.2", plan.error)
        self.assertEqual(plan.steps, [])
        self.assertFalse(upgrade_path.may_apply_step(plan, [], 0))

    def test_empty_target_is_rejected(self):
        plan = upgrade_path.plan_upgrade("4.0.1", "", ["4.2"], INTERMEDIATE, TARGET_IMAGE)
        self.assertFalse(plan.accepted)
        self.assertIn("4.0", plan.error)
        self.assertIn("absent", plan.error)

    def test_line_major_must_match_the_key(self):
        self.assertIsNone(upgrade_path.validate_line_versions({3: "3.13", 4: "4.2"}))
        error = upgrade_path.validate_line_versions({4: "5.1"})
        self.assertIsNotNone(error)
        self.assertIn("4", error)
        self.assertIn("5.1", error)

    def test_unreadable_pod_version_is_rejected(self):
        self.assertIsNone(upgrade_path.resolve_pod_version("not a version", None))
        recovered = upgrade_path.resolve_pod_version(
            "error",
            '{"rabbitmq_version": "4.0.1"}',
        )
        self.assertEqual(str(recovered), "4.0")
        oldest, error = upgrade_path.oldest_running([recovered, None])
        self.assertIsNone(oldest)
        self.assertIn("could not be determined", error)

    def test_oldest_node_wins_when_nodes_disagree(self):
        older = upgrade_path.parse_major_minor("4.0.1")
        newer = upgrade_path.parse_major_minor("4.2.9")
        oldest, error = upgrade_path.oldest_running([newer, older])
        self.assertIsNone(error)
        self.assertEqual(str(oldest), "4.0")

    def test_three_line_is_not_an_implicit_stop(self):
        plan = upgrade_path.plan_upgrade("4.0", "4.2", ["4.2"], INTERMEDIATE, TARGET_IMAGE)
        self.assertNotIn("3.13", _versions(plan))

    def test_one_node_still_old_blocks_the_next_image(self):
        plan = upgrade_path.plan_upgrade(
            "4.0", "5.1", ["4.2", "4.7", "5.0"], INTERMEDIATE, TARGET_IMAGE
        )
        current = upgrade_path.parse_major_minor("4.2")
        stale = upgrade_path.parse_major_minor("4.0")
        self.assertFalse(upgrade_path.nodes_reached([current, stale], "4.2"))
        self.assertFalse(upgrade_path.may_apply_step(plan, [current, stale], 1))

    def test_removing_a_stop_joins_its_neighbors(self):
        source = Path(__file__).resolve().parent.joinpath("src", "upgrade_path.py").read_text(encoding="utf-8")
        self.assertNotIn("4.7", source)
        plan = upgrade_path.plan_upgrade(
            "4.0", "5.1", ["4.2", "5.0"], INTERMEDIATE, TARGET_IMAGE
        )
        self.assertEqual(_versions(plan), ["4.2", "5.0", "5.1"])

    def test_version_is_taken_from_the_image_name(self):
        image = "ghcr.io/netcracker/qubership-rabbitmq-image-4.2:main@sha256:abc"
        self.assertEqual(str(upgrade_path.version_from_image_name(image)), "4.2")
        self.assertIsNone(upgrade_path.version_from_image_name(
            "ghcr.io/netcracker/qubership-rabbitmq-image:main"
        ))
        indexed = upgrade_path.images_by_version([
            "ghcr.io/netcracker/qubership-rabbitmq-image-4.2:main",
            "ghcr.io/netcracker/qubership-rabbitmq-image-4.7:main",
        ])
        self.assertEqual(indexed["4.2"], "ghcr.io/netcracker/qubership-rabbitmq-image-4.2:main")
        self.assertEqual(indexed["4.7"], "ghcr.io/netcracker/qubership-rabbitmq-image-4.7:main")

    def test_target_comes_from_the_properties_file_only(self):
        values_text = (
            Path(__file__).resolve().parent / "charts" / "helm" / "rabbitmq" / "values.yaml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("rabbitmqVersion", values_text)
        self.assertNotIn("intermediateVersions", values_text)
        lines = {3: "3.13", 4: "4.2"}
        self.assertEqual(
            upgrade_path.target_from_properties(lines, "ghcr.io/netcracker/qubership-rabbitmq-image:main"),
            "4.2",
        )
        self.assertEqual(
            upgrade_path.target_from_properties(lines, "ghcr.io/netcracker/qubership-rabbitmq-image-3:main"),
            "3.13",
        )
        self.assertEqual(
            upgrade_path.target_from_properties({3: "3.13", 4: "4.2", 5: "5.1"}, "ghcr.io/netcracker/qubership-rabbitmq-image:main"),
            "5.1",
        )

    def test_operator_rolls_only_when_an_intermediate_step_remains(self):
        direct = upgrade_path.plan_upgrade("4.0.1", "4.2", ["4.2"], {"4.2": "img"}, "line")
        self.assertFalse(upgrade_path.has_intermediate_step(direct))
        same = upgrade_path.plan_upgrade("4.2.9", "4.2", ["4.2"], {"4.2": "img"}, "line")
        self.assertFalse(upgrade_path.has_intermediate_step(same))
        multi = upgrade_path.plan_upgrade(
            "4.0.1", "5.1", ["4.2", "4.7", "5.0"],
            {"4.2": "a", "4.7": "b", "5.0": "c"}, "line",
        )
        self.assertTrue(upgrade_path.has_intermediate_step(multi))
        missing = upgrade_path.plan_upgrade("4.0", "5.1", ["4.7"], {}, "line")
        self.assertTrue(upgrade_path.has_intermediate_step(missing))

    def test_shipped_intermediate_directory_exists_and_a_missing_one_fails(self):
        shipped = None
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "rabbitmq-docker" / "intermediate-versions"
            if candidate.is_dir():
                shipped = candidate
                break
        if shipped is not None:
            self.assertEqual(upgrade_path.missing_intermediate_directories(["4.2"], shipped), [])
        with tempfile.TemporaryDirectory() as temporary:
            missing = upgrade_path.missing_intermediate_directories(["4.2"], temporary)
            self.assertEqual(missing, ["4.2"])


if __name__ == "__main__":
    unittest.main()
