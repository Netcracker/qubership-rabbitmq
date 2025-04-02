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


def make_rabbitmq_restore(folder, vhosts):
    logging.info(f"Restore backup for vhosts: {vhosts} to folder: {folder}")
    rabbit_cafile = CA_CERT_PATH if os.path.exists(CA_CERT_PATH) else None
    for vhost in vhosts:
        rabbit_url = f"{RABBITMQ_URL}/api/definitions/{vhost}"
        rabbit_url_create_vhost = f"{RABBITMQ_URL}/api/vhosts/{vhost}"
        if vhost == "":
            vhost = "allrabbitmqvhosts"
        try:
            with open(folder + "/" + vhost) as f:
                backup = json.load(f)
        except Exception as e:
            logging.error(f"Can not get backup json from: {vhost} with error: {str(e)}")
        if vhost != "allrabbitmqvhosts":
            try:
                response = requests.put(rabbit_url_create_vhost, auth=(RABBITMQ_USER, RABBITMQ_PASSWORD), json=backup, verify=rabbit_cafile)
            except Exception as e:
                logging.error(f"Can not create vhost with: {rabbit_url} with error: {str(e)}")
                return 1
            if not ((response.status_code == 201) or (response.status_code == 204)):
                logging.error(f"Can not create vhost with: {rabbit_url} with error code: {str(response.status_code)}")
                return 1
        try:
            response = requests.post(rabbit_url, auth=(RABBITMQ_USER, RABBITMQ_PASSWORD), json=backup, verify=rabbit_cafile)
        except Exception as e:
            logging.error(f"Can not get backup json from: {rabbit_url} with error: {str(e)}")
            return 1

        if response.status_code != 204:
            logging.error(f"Can not post backup json to:  {rabbit_url}  with error code: {str(response.status_code)}")
            return 1

    logging.info("restore_result: 0")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('folder')
    parser.add_argument('-d', '--vhosts')
    args = parser.parse_args()
    folder = args.folder
    vhosts = ast.literal_eval(args.vhosts) if args.vhosts else [""]

    make_rabbitmq_restore(folder, vhosts)
