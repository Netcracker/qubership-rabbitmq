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

import os

DEFAULT_SECRETS_DIR = '/etc/secrets/rabbitmq-integration-tests-pod-secrets'


def _secrets_dir(environ) -> str:
    return environ.get('INTEGRATION_TESTS_SECRETS_DIR', DEFAULT_SECRETS_DIR)


def secret_is_present(environ, name) -> bool:
    path = os.path.join(_secrets_dir(environ), name)
    return os.path.isfile(path) and os.path.getsize(path) > 0


def get_excluded_tags(environ) -> list:
    excluded_tags = []
    if not environ.get('RABBITMQ_BACKUP_DAEMON'):
        excluded_tags.append('backup')
    if environ.get('S3_ENABLED') != 'true' or not (
            secret_is_present(environ, 'S3_KEY_ID')
            and secret_is_present(environ, 'S3_KEY_SECRET')):
        excluded_tags.append('s3_storage')
        excluded_tags.append('backup_v2')
    return excluded_tags
