FROM ghcr.io/netcracker/qubership-backup-daemon-go:0.1.20

ENV RABBITMQ_HOME=/opt/rabbitmq \
    RABBITMQ_BACKUP=/opt/rabbitmq/backup-storage/ \
    USER_UID=1000


COPY backup-daemon.conf /etc/backup-daemon.conf
COPY scripts/ ${RABBITMQ_HOME}/scripts/
COPY requirements.txt ${RABBITMQ_HOME}/requirements.txt
RUN chmod +x ${RABBITMQ_HOME}/scripts/*.py

RUN set -x \
    && apk add --no-cache wget py3-pip python3 python3-dev apk-tools curl \
    && apk upgrade --no-cache --available \
    && if python3 -m pip install --help | grep -q -- '--break-system-packages'; then PIP_BREAK_FLAG='--break-system-packages'; else PIP_BREAK_FLAG=''; fi \
    && python3 -m pip install --no-cache-dir ${PIP_BREAK_FLAG} --upgrade "pip>=26.0" \
    && python3 -m pip install --no-cache-dir ${PIP_BREAK_FLAG} "setuptools==80.10.1" "jaraco.context>=6.1.0" \
    && python3 -m pip install --no-cache-dir ${PIP_BREAK_FLAG} -r ${RABBITMQ_HOME}/requirements.txt \
    && rm -rf /var/cache/apk/*



VOLUME ["${RABBITMQ_BACKUP}"]

