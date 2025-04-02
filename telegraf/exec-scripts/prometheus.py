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
import os
import time
import ssl

import requests
from functools import wraps
import aiohttp
import logging
from logging.handlers import RotatingFileHandler

import channel_parser
import connection_parser
import node_parser
import queue_parser

logger = logging.getLogger(__name__)

CA_CERT_PATH = '/tls/ca.crt'


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


class RabbitMQHelper(object):

    def __init__(self, host: str, user: str, password: str):
        self._host = host
        self._auth = aiohttp.BasicAuth(user, password)
        self.ssl = CA_CERT_PATH if os.path.exists(CA_CERT_PATH) else None
        response = requests.get(f'{self._host}/api/overview',
                                auth=(user, password), verify=self.ssl)
        overview = response.json()
        self._cluster_name = overview['cluster_name']

    @retry()
    async def _request(self, url: str):
        if self.ssl:
            sslcontext = ssl.create_default_context(
                cafile=CA_CERT_PATH)
        else:
            sslcontext = None
        async with aiohttp.ClientSession(auth=self._auth) as session:
            async with session.get(
                    url=f'{self._host}/api/{url}', ssl=sslcontext) as resp:
                return await resp.json()

    @suppress_errors()
    async def nodes(self):
        nodes = await self._request('nodes')
        return node_parser.parse_nodes(nodes=nodes,
                                       cluster_name=self._cluster_name)

    @suppress_errors()
    async def connections(self):
        connections = await self._request('connections')
        nodes = await self._request('nodes')
        return connection_parser.parse_connections(
            connections=connections,
            nodes=nodes,
            cluster_name=self._cluster_name
        )

    @suppress_errors()
    async def queues(self):
        queues = await self._request('queues')
        nodes = await self._request('nodes')
        return queue_parser.parse_queues(queues=queues,
                                         nodes=nodes,
                                         cluster_name=self._cluster_name)

    @suppress_errors()
    async def channels(self):
        channels = await self._request('channels')
        nodes = await self._request('nodes')
        return channel_parser.parse_channels(channels=channels,
                                             nodes=nodes,
                                             cluster_name=self._cluster_name)


def get_prometheus_metrics(metrics):
    res = ''
    for batch in metrics:
        res = res + ''.join([line.decode('utf-8') for line in batch])
    return res


def __configure_logging(log):
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt='[%(asctime)s,%(msecs)03d][%(levelname)s] %(message)s',
                                  datefmt='%Y-%m-%dT%H:%M:%S')

    log_handler = RotatingFileHandler(filename='/opt/rabbitmq-monitoring/exec-scripts/rabbitmq_metric.log',
                                      maxBytes=50 * 1024,
                                      backupCount=5)
    log_handler.setFormatter(formatter)
    log_handler.setLevel(logging.DEBUG if os.getenv('RABBITMQ_MONITORING_SCRIPT_DEBUG') else logging.INFO)
    log.addHandler(log_handler)
    err_handler = RotatingFileHandler(filename='/opt/rabbitmq-monitoring/exec-scripts/rabbitmq_metric.err',
                                      maxBytes=50 * 1024,
                                      backupCount=5)
    err_handler.setFormatter(formatter)
    err_handler.setLevel(logging.ERROR)
    log.addHandler(err_handler)


def run():
    try:
        logger.info('Start script execution...')
        loop = asyncio.get_event_loop()
        rabbitmq_helper = RabbitMQHelper(
            host=os.getenv('RABBITMQ_HOST', '').rstrip('/'),
            user=os.getenv('RABBITMQ_USER', ''),
            password=os.getenv('RABBITMQ_PASSWORD', '')
        )
        tasks = [asyncio.ensure_future(x)
                 for x in [rabbitmq_helper.nodes(),
                           rabbitmq_helper.queues(),
                           rabbitmq_helper.channels(),
                           rabbitmq_helper.connections()
                           ]]
        metrics = loop.run_until_complete(asyncio.gather(*tasks))
        prometheus_formatted_metrics = get_prometheus_metrics(metrics)
        logger.debug('Message to send:\n%s', prometheus_formatted_metrics)
        logger.info('End script execution!\n')
        print(prometheus_formatted_metrics)
    except Exception:
        logger.exception('Exception occurred during script execution:')
        raise


if __name__ == "__main__":
    __configure_logging(logger)
    start = time.time()
    run()
    logger.info(f'Time of execution is {time.time() - start}\n')
