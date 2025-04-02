FROM ghcr.io/netcracker/qubership-backup-daemon:main_alpine
ENV RABBITMQ_HOME=/opt/rabbitmq \
    RABBITMQ_BACKUP=/opt/rabbitmq/backup-storage/ \
    USER_UID=1000

COPY backup-daemon.conf /etc/backup-daemon.conf
COPY scripts/ ${RABBITMQ_HOME}/scripts/
COPY requirements.txt ${RABBITMQ_HOME}/requirements.txt
RUN chmod +x ${RABBITMQ_HOME}/scripts/*.py

RUN set -x \
    && apk add --update --no-cache curl apk-tools \
    && pip3 install setuptools==70.0.0 \
    && pip3 install -r ${RABBITMQ_HOME}/requirements.txt \
    && rm -rf /var/cache/apk/*

# Upgrade all tools to avoid vulnerabilities
RUN set -x && apk upgrade --no-cache --available

WORKDIR ${RABBITMQ_HOME}

VOLUME ["${RABBITMQ_BACKUP}"]

USER ${USER_UID}
