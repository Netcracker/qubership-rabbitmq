#!/usr/bin/python

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
import multiprocessing
import json
import ast
import argparse
import requests
import os


RABBITMQ_URL = os.environ['RABBITMQ_URL']
RABBITMQ_PASSWORD = os.environ['RABBITMQ_PASSWORD']
RABBITMQ_USER = os.environ['RABBITMQ_USER']
CA_CERT_PATH = '/tls/ca.crt'


loggingLevel = logging.DEBUG if os.getenv(
    'RABBITMQ_BACKUP_DAEMON_DEBUG') else logging.INFO
logging.basicConfig(level=loggingLevel,
                    format='[%(asctime)s,%(msecs)03d][%(levelname)s][category=Backup] %(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S')


def make_rabbitmq_backup(folder, vhosts):
    rabbit_cafile = CA_CERT_PATH if os.path.exists(CA_CERT_PATH) else None
    logging.info(f"Make backup for vhosts: {vhosts} to folder: {folder}")
    for vhost in vhosts:
        rabbit_url = f"{RABBITMQ_URL}/api/definitions/{vhost}"
        try:
            response = requests.get(rabbit_url, auth=(RABBITMQ_USER, RABBITMQ_PASSWORD), verify=rabbit_cafile)

        except Exception as e:
            logging.error(f"Can not get backup json from: {rabbit_url} with error {str(e)}")
            exit(1)

        backup = response.json()
        if backup.get("error"):
            logging.error(f"Can not get backup json from: {rabbit_url} with error: {backup['reason']}")
            exit(1)
        if vhost == "":
            vhost = "allrabbitmqvhosts"
        with open(folder + "/" + vhost, "w+") as output:
            json.dump(backup, output, ensure_ascii=False, indent=4)
    logging.info("backup_result: 0")
    exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('folder')
    parser.add_argument('-d', '--vhosts')
    args = parser.parse_args()
    folder = args.folder
    vhosts = ast.literal_eval(args.vhosts) if args.vhosts else [""]

    make_rabbitmq_backup(folder, vhosts)
