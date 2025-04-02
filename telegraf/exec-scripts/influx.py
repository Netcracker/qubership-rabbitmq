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

import asyncio
import logging
import operator
import os
import time
from distutils import util
from functools import reduce, wraps
from typing import Dict, Union, List

import aiohttp

debug_enabled_error = None

try:
    debug_enabled = util.strtobool(os.environ.get('INFLUXDB_DEBUG', 'false'))
except ValueError as e:
    debug_enabled_error = e
    debug_enabled = False

level = logging.DEBUG if debug_enabled else logging.INFO

logging.basicConfig(filename='/proc/1/fd/1', filemode='w', level=level,
                    format='%(asctime)s %(message)s')

if debug_enabled_error:
    logging.error(debug_enabled_error)


class Metric(object):

    def __init__(self, name: str, fields: Dict[str, Union[float, int]],
                 tags: Dict[str, str] = None):
        if tags is None:
            tags = {}
        self.name = name
        self.tags = tags
        self.fields = fields

    def influx_format(self) -> str:
        tags = ",".join(f"{k}={v}" for k, v in self.tags.items())
        fields = ",".join(f"{k}={v}" for k, v in self.fields.items())

        is_tags = ',' if tags else ''
        is_fields = ' ' if fields else ''

        return f"{self.name}{is_tags}{tags}{is_fields}{fields}"


def convert_metrics(metrics: List[Metric]) -> str:
    all_replicas = None
    current_replicas = 0

    for metric in metrics:
        if metric.name == 'rabbitmq_all_replicas':
            all_replicas = metric.fields['number']
        elif metric.name == 'rabbitmq_current_replicas':
            current_replicas = metric.fields['number']

    if all_replicas:
        metrics.append(Metric(name='rabbitmq_cluster_state',
                              fields={
                                  'status': current_replicas / all_replicas}))
    else:
        metrics.append(Metric(name='rabbitmq_cluster_state',
                              fields={
                                  'status': 0.0}))

    metric_result = '\n'.join([x.influx_format() for x in metrics])
    logging.debug(f'Metrics: {metric_result}')

    return metric_result


def suppress_errors(return_func=lambda: []):
    def wrapper(f):

        @wraps(f)
        def internal_wrapper(*args, **kwargs):
            async def async_await():
                try:
                    return await f(*args, **kwargs)
                except BaseException as e:
                    logging.error(e)
                    return return_func()

            return async_await()

        return internal_wrapper

    return wrapper


class RetryExhaustedError(IOError):
    pass


def retry(retries=5, cooldown=0):
    def wrap(func):

        @wraps(func)
        async def inner(*args, **kwargs):
            retries_count = 0

            while True:
                try:
                    result = await func(*args, **kwargs)
                except Exception:
                    retries_count += 1

                    if retries_count > retries:
                        raise RetryExhaustedError(
                            func.__qualname__, args, kwargs)

                    await asyncio.sleep(cooldown)
                else:
                    return result

        return inner

    return wrap


class OpenshiftHelper(object):

    def __init__(self):
        # token location inside kubernetes pod by default
        sa_dir_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        self._exists = os.path.exists(sa_dir_path)

        # skip openshift metric collection outside Openshift
        if self._exists:
            self._namespace = os.environ['NAMESPACE']
            self._url = f'https://{os.environ["KUBERNETES_SERVICE_HOST"]}:{os.environ["KUBERNETES_PORT_443_TCP_PORT"]}/'
            with open(sa_dir_path) as f:
                self._headers = {"authorization": "Bearer " + f.read()}

    @suppress_errors()
    async def get_number_of_dc_replicas(self, dc_name: str) -> List[Metric]:
        if not self._exists:
            return []

        async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
            async with session.get(
                    url=f'{self._url}apis/apps/v1beta1/namespaces/{self._namespace}/statefulsets/{dc_name}',
                    headers=self._headers) as resp:
                if resp.status != 404:
                    statefulset = await resp.json()

                    return [Metric(
                        name='rabbitmq_all_replicas',
                        fields={'number': statefulset['spec']['replicas']},
                    )]

            async with session.get(
                    url=f'{self._url}apis/apps/v1beta1/namespaces/{self._namespace}/statefulsets',
                    headers=self._headers) as resp:
                statefulset = await resp.json()

                return [Metric(
                    name='rabbitmq_all_replicas',
                    fields={'number': len(statefulset['items'])},
                )]


class RabbitMQHelper(object):

    def __init__(self, host: str, user: str, password: str):
        self._host = host
        self._auth = aiohttp.BasicAuth(user, password)

        self._object_keys_overview = ["connections", "consumers"]

        self._keys_node = ['disk_free', 'disk_free_limit', 'fd_total',
                           'fd_used', 'mem_limit', 'mem_used', 'proc_total',
                           'proc_used', 'sockets_total', 'sockets_used',
                           'uptime', 'mnesia_disk_tx_count',
                           'mnesia_ram_tx_count', 'gc_num',
                           'gc_bytes_reclaimed', 'io_read_avg_time',
                           'io_read_bytes', 'io_write_avg_time',
                           'io_write_bytes']
        self._rate_keys_node = ['mnesia_disk_tx_count', 'mnesia_ram_tx_count',
                                'gc_num', 'gc_bytes_reclaimed',
                                'io_read_avg_time', 'io_read_bytes',
                                'io_write_bytes']
        self._bool_keys_node = ['disk_free_alarm', 'mem_alarm', 'running']

        self._keys_queue = ['memory', 'message_bytes', 'message_bytes_ready',
                            'message_bytes_ram']

        self._messages_stats_rate = ['messages_deliver',
                                     'messages_publish', 'messages_redeliver']

    @retry()
    async def _request(self, url: str):
        async with aiohttp.ClientSession(auth=self._auth) as session:
            async with session.get(
                    url=f'http://{self._host}:15672/api/{url}') as resp:
                return await resp.json()

    @suppress_errors()
    async def smoketest(self) -> List[Metric]:
        start = time.time()
        res = await self._request('aliveness-test/%2F')
        end = time.time()

        fields = {}
        if res['status'] == 'ok':
            fields['duration'] = end - start
        else:
            fields['duration'] = -1

        return [Metric(name='rabbitmq_smoketest', fields=fields)]

    @suppress_errors()
    async def nodes(self) -> List[Metric]:
        nodes = await self._request('nodes')
        metrics = {}

        for node in nodes:
            node_name = node['name']
            healthcheck = node['running']
            fields = {
                **{x: node.get(x, -1) for x in self._keys_node},
                **{f'{x}_rate': node.get(f'{x}_details', {}).get('rate', -1) for x in
                   self._rate_keys_node},
                **{x: int(-1 if node.get(x) is None else node.get(x)) for x in self._bool_keys_node},
            }
            if healthcheck:
                fields['health_check_status'] = 1
            else:
                fields['health_check_status'] = 0
                fields['uptime'] = 0
            metrics[node_name] = Metric(name='rabbitmq_node', fields=fields,
                                        tags={'node': node_name})
        metrics['rabbitmq_current_replicas'] = Metric(
            name='rabbitmq_current_replicas',
            fields={'number': len(list(filter(lambda x: x['running'], nodes)))}
        )
        return list(metrics.values())

    @suppress_errors()
    async def queues(self):
        queues = await self._request('queues')
        metrics = []

        for queue in queues:
            fields = {
                **{x: queue[x] for x in self._keys_queue},
                'message_bytes_unacked': queue[
                    'message_bytes_unacknowledged'],
                'message_bytes_persist': queue['message_bytes_persistent']
            }

            if 'message_stats' in queue:
                message_stats = queue.get('message_stats', {})
                fields.update({
                    'messages_ack_rate': message_stats.get('ack_details', {}).get('rate', 0),
                    'messages_deliver_rate': message_stats.get('deliver_details', {}).get('rate', 0),
                    'messages_publish_rate': message_stats.get('publish_details', {}).get('rate', 0),
                    'messages_redeliver_rate': message_stats.get('redeliver_details', {}).get('rate', 0)
                })

            tags = {
                "queue": queue['name'],
                "vhost": queue['vhost'],
                "node": queue['node']
            }

            metrics.append(Metric(name='rabbitmq_queue', fields=fields,
                                  tags=tags))

        return metrics

    @suppress_errors()
    async def exchanges(self):
        exchanges = await self._request('exchanges')
        metrics = []

        for exchange in exchanges:
            if 'message_stats' in exchange:
                fields = {
                    "messages_publish_in": exchange['message_stats'][
                        'publish_in'],
                    "messages_publish_in_rate":
                        exchange['message_stats']['publish_in_details']['rate'],
                    "messages_publish_out": exchange['message_stats'][
                        'publish_out'],
                    "messages_publish_out_rate":
                        exchange['message_stats']['publish_out_details'][
                            'rate'],
                }
            else:
                continue

            tags = {
                "type": exchange['type'],
                "vhost": exchange['vhost'],
            }
            exchange_name = exchange['name']
            if exchange_name:
                tags['exchange'] = exchange_name

            metrics.append(Metric(name='rabbitmq_exchange', fields=fields,
                                  tags=tags))

        return metrics

    @suppress_errors()
    async def overview(self) -> List[Metric]:
        overview = await self._request('overview')
        fields = {}

        queue_totals = overview['queue_totals']
        if queue_totals:
            fields['messages'] = queue_totals['messages']

        message_stats = overview['message_stats']
        if message_stats:
            fields['return_unroutable_rate'] = \
                message_stats['return_unroutable_details']['rate']

        fields.update({x: overview['object_totals'][x] for x in
                       self._object_keys_overview})

        return [Metric(name='rabbitmq_overview', fields=fields)]

    @suppress_errors()
    async def self_health(self) -> List[Metric]:
        return [Metric(name='telegraf', fields={"status": 1})]


def main():
    loop = asyncio.get_event_loop()
    rabbitmq_helper = RabbitMQHelper(
        host=os.getenv('RABBITMQ_HOST', 'localhost'),
        user=os.getenv('RABBITMQ_USER', 'guest'),
        password=os.getenv('RABBITMQ_PASSWORD', 'guest')
    )
    os_helper = OpenshiftHelper()

    tasks = [asyncio.ensure_future(x)
             for x in [rabbitmq_helper.nodes(),
                       rabbitmq_helper.overview(),
                       rabbitmq_helper.smoketest(),
                       rabbitmq_helper.queues(),
                       rabbitmq_helper.exchanges(),
                       os_helper.get_number_of_dc_replicas('rmqlocal'),
                       rabbitmq_helper.self_health()
                       ]]
    res = loop.run_until_complete(asyncio.gather(*tasks))

    print(convert_metrics(reduce(operator.concat, res)))


if __name__ == "__main__":
    main()
