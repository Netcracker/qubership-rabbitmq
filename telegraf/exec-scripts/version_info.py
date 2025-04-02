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
import aiohttp
import logging
from logging.handlers import RotatingFileHandler
from functools import wraps
import prometheus_client
from prometheus_client import Gauge

# Configure logging
logger = logging.getLogger(__name__)

CA_CERT_PATH = '/tls/ca.crt'


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

    @retry()
    async def get_rabbitmq_version(self):
        sslcontext = ssl.create_default_context(cafile=CA_CERT_PATH) if self.ssl else None
        async with aiohttp.ClientSession(auth=self._auth) as session:
            try:
                async with session.get(f'{self._host}/api/overview', ssl=sslcontext) as response:
                    response_json = await response.json()
                    version = response_json.get('rabbitmq_version', 'unknown')
                    logger.info(f'Current rabbitmq version: {version}')
                    return prometheus_formatted_metrics(version)
            except Exception as e:
                logger.error(f'Exception occurred: {e}')
                return prometheus_formatted_metrics('unknown')


def prometheus_formatted_metrics(version):
    _gauge = Gauge('rabbitmq_build_info', 'RabbitMQ\'s app version', ['rabbitmq_version'])
    _gauge.labels(version).set(1)
    return prometheus_client.generate_latest(_gauge).decode('utf-8')


def __configure_logging(log):

    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt='[%(asctime)s,%(msecs)03d][%(levelname)s] %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')

    log_handler = RotatingFileHandler(filename='/opt/rabbitmq-monitoring/exec-scripts/version_info.log', maxBytes=50 * 1024, backupCount=5)
    log_handler.setFormatter(formatter)
    log_handler.setLevel(logging.DEBUG if os.getenv('RABBITMQ_MONITORING_SCRIPT_DEBUG') else logging.INFO)
    log.addHandler(log_handler)

    err_handler = RotatingFileHandler(filename='/opt/rabbitmq-monitoring/exec-scripts/version_info.err', maxBytes=50 * 1024, backupCount=5)
    err_handler.setFormatter(formatter)
    err_handler.setLevel(logging.ERROR)
    log.addHandler(err_handler)


def run():
    try:
        logger.info('Start script execution for rabbitmq version...')
        loop = asyncio.get_event_loop()
        rabbitmq_helper = RabbitMQHelper(
            host=os.getenv('RABBITMQ_HOST', '').rstrip('/'),
            user=os.getenv('RABBITMQ_USER', ''),
            password=os.getenv('RABBITMQ_PASSWORD', '')
        )
        version_info = loop.run_until_complete(rabbitmq_helper.get_rabbitmq_version())
        print(version_info)
        logger.info('End script execution!\n')
    except Exception:
        logger.exception('Exception occurred during script execution:')
        raise


if __name__ == "__main__":
    __configure_logging(logger)
    start = time.time()
    run()
    logger.info(f'Time of execution is {time.time() - start}\n')
