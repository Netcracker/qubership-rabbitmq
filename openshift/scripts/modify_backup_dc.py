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

import argparse
import sys

import yaml


def inject_nodeselector(template_backuper):
    template_backuper["objects"][2]["spec"]["template"]["spec"]["nodeSelector"] = {"kubernetes.io/hostname": "${BACKUP_STORAGE_NODE}"}


def inject_rabbitmq_sa(template_backuper):
    template_backuper["objects"][2]["spec"]["template"]["spec"]["serviceAccount"] = "backuper-rabbitmq"


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process the backup_template.yaml file')
    parser.add_argument('--template-folder', dest='path_to_template', help="Path to the rabbitmq.json")
    parser.add_argument('command', choices=['inject_nodeselector', 'inject_rabbitmq_sa'])

    args = parser.parse_args()

    if not args.path_to_template:
        print('Specify path to RabbitMQ template')
        sys.exit(1)

    path_to_rabbitmq = args.path_to_template + 'backup_template.yaml'

    with open(path_to_rabbitmq, 'r') as f:
        template_yaml = yaml.load(f)

    if args.command == 'inject_nodeselector':
        inject_nodeselector(template_yaml)
    elif args.command == 'inject_rabbitmq_sa':
        inject_rabbitmq_sa(template_yaml)
    else:
        print('Unexpected command: {}'.format(args.command))
        sys.exit(1)

    with open(path_to_rabbitmq, 'w') as f:
        yaml.dump(template_yaml, f)
