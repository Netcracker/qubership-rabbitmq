FROM ghcr.io/netcracker/qubership-backup-daemon-go:main

ENV RABBITMQ_HOME=/opt/rabbitmq \
    RABBITMQ_BACKUP=/opt/rabbitmq/backup-storage/ \
    USER_UID=1000


COPY backup-daemon.conf /etc/backup-daemon.conf
COPY scripts/ ${RABBITMQ_HOME}/scripts/
COPY requirements.txt ${RABBITMQ_HOME}/requirements.txt
RUN chmod +x ${RABBITMQ_HOME}/scripts/*.py

RUN echo "https://dl-cdn.alpinelinux.org/alpine/v3.23/main" > /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/v3.23/community" >> /etc/apk/repositories

# Prefer v3.23 for most packages; pull curl/libcurl from edge (v3.23 stops at 8.17.x; CVE fixes need 8.19+).
# Install the curl stack after `apk upgrade` so it is not downgraded back to 8.17.x.

RUN apk add --no-cache wget python3 python3-dev py3-pip \
    && apk update \
    && apk upgrade

RUN set -x \
    && apk update \
    && apk upgrade --no-cache --available \
    && apk add --no-cache apk-tools \
    && apk add --no-cache \
        --repository=https://dl-cdn.alpinelinux.org/alpine/edge/main \
        curl=8.19.0-r0 libcurl=8.19.0-r0 \
    && if python3 -m pip install --help | grep -q -- '--break-system-packages'; then PIP_BREAK_FLAG='--break-system-packages'; else PIP_BREAK_FLAG=''; fi \
    && python3 -m pip install --no-cache-dir ${PIP_BREAK_FLAG} --upgrade "pip>=26.0" \
    && python3 -m pip install --no-cache-dir ${PIP_BREAK_FLAG} "setuptools==80.10.1" "jaraco.context>=6.1.0" \
    && python3 -m pip install --no-cache-dir ${PIP_BREAK_FLAG} -r ${RABBITMQ_HOME}/requirements.txt \
    && rm -rf /var/cache/apk/*



VOLUME ["${RABBITMQ_BACKUP}"]

