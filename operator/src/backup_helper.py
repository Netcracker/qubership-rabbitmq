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

import logging
import time

import requests
from requests import HTTPError

logger = logging.getLogger(__name__)


class BackupHelper:
    def __init__(self, schema='http', service='rabbitmq-backup-daemon', namespace='rabbitmq', auth=None, verify=None, **kwargs):
        custom_url = kwargs.get('custom_url', None)
        if verify:
            schema = 'https'
            self.verify = verify
            port = "8443"
        else:
            self.verify = None
            port = "8080"
        self.url = f'{schema}://{service}.{namespace}:{port}' if not custom_url else custom_url
        self.auth = auth

    def _read_backup_daemon_health(self) -> dict:
        response = requests.get(f'{self.url}/health', auth=self.auth, verify=self.verify)
        response.raise_for_status()
        return response.json()

    def read_backup_daemon_health(self, timeout=180) -> dict:
        spent = 0
        while spent <= timeout:
            try:
                spent = spent + 10
                result = self._read_backup_daemon_health()
                if result is None:
                    logger.debug(f'read_backup_daemon_health result: {result}')
                    raise ValueError('Backup daemon health is None')
                return result
            except requests.RequestException as e:
                logger.warning(f'Error occurred during reading backup daemon health, retrying in 10 seconds: {e}')
                time.sleep(10)
                continue
            except ValueError as e:
                logger.warning(f'Error occurred during reading backup daemon health: {e}')
                time.sleep(20)
                continue
            
        logger.warning(f'Backup daemon status was not received')
        return None

    def check_backup_daemon_readiness(self, timeout) -> bool:
        health = self.read_backup_daemon_health(timeout)
        logger.debug(f'Backup daemon health: {health}')
        if health is None:
            return False
        status: str = health['status']
        logger.debug(f'Backup daemon status: {status}')
        if status == 'UP':
            return True
        elif status == 'Warning':
            dump_count = int(health['storage']['dump_count'])
            return dump_count == 0
        return False

    def list_backups(self) -> list:
        response = requests.get(f'{self.url}/listbackups', auth=self.auth, verify=self.verify)
        response.raise_for_status()
        return response.json()

    def read_backup_info(self, backup_id: str) -> dict:
        response = requests.get(f'{self.url}/listbackups/{backup_id}', auth=self.auth, verify=self.verify)
        response.raise_for_status()
        return response.json()

    def read_job_status(self, id: str) -> dict:
        response = requests.get(f'{self.url}/jobstatus/{id}', auth=self.auth, verify=self.verify)
        response.raise_for_status()
        return response.json()

    def get_latest_backup_id_from_another_cluster(self, region: str) -> str:
        region = region.lower()
        logger.info(f"Look for latest backup from another cluster. Current region: {region}")
        backups: list = self.list_backups()
        backups.reverse()
        logger.info(f"Full list of backups: {backups}")
        for backup_id in backups:
            try:
                backup: dict = self.read_backup_info(backup_id)
            except HTTPError as e:
                logger.error(f"Error occurred during get info from backup id {backup_id}: {e}")
                continue
            custom_vars = backup.get('custom_vars', None)
            if not custom_vars:
                continue
            backup_region = custom_vars['region'].lower()
            if backup['db_list'] == 'full backup' \
                    and not backup['failed'] \
                    and backup_region != region:
                logger.info(f"Backup ID `{backup_id}` corresponds condition, check for a lock")
                if self._check_backup_unlocked(backup_id):
                    return backup_id
        logger.info("No corresponding backups found")
        return None

    def _check_backup_unlocked(self, id, attemps=3, timeout=10):
        if not attemps:
            return False
        status = self.read_backup_info(id)
        if status['failed']:
            return False
        if not status['locked']:
            return True
        attemps -= 1
        time.sleep(timeout)
        self._check_backup_unlocked(id, attemps)

    def perform_full_backup(self) -> str:
        resp = requests.post(f'{self.url}/backup', auth=self.auth, verify=self.verify)
        resp.raise_for_status()
        return resp.text

    def restore(self, backup_id: str) -> str:
        restore_headers = {'Content-Type': 'application/json'}
        resp = requests.post(f'{self.url}/restore', json={'vault': backup_id}, headers=restore_headers, auth=self.auth, verify=self.verify)
        resp.raise_for_status()
        logger.info(f"Restore task id: {resp.text}")
        return resp.text

    def check_job_status(self, task_id: str, attempts: int = 6, timeout: int = 10) -> bool:
        while attempts:
            status: str = self.read_job_status(task_id)['status']
            if status == 'Successful':
                return True
            elif status == 'Failed':
                return False
            else:
                time.sleep(timeout)
                attempts -= 1
        return False
