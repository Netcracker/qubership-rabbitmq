FROM ghcr.io/netcracker/qubership-backup-daemon-go:main

ENV RABBITMQ_HOME=/opt/rabbitmq \
    RABBITMQ_BACKUP=/opt/rabbitmq/backup-storage/ \
    USER_UID=1000:0

    #test 
    
COPY backup-daemon.conf /etc/backup-daemon.conf
COPY scripts/ ${RABBITMQ_HOME}/scripts/
COPY requirements.txt ${RABBITMQ_HOME}/requirements.txt
RUN chmod +x ${RABBITMQ_HOME}/scripts/*.py

RUN echo "https://dl-cdn.alpinelinux.org/alpine/v3.23/main" > /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/v3.23/community" >> /etc/apk/repositories

RUN set -x \
    && apk add --update --no-cache curl apk-tools python3 \
    py3-requests \
    py3-pip \
    && if pip3 install --help | grep -q -- '--break-system-packages'; then PIP_BREAK_FLAG='--break-system-packages'; else PIP_BREAK_FLAG=''; fi \
    && pip3 install --no-cache-dir ${PIP_BREAK_FLAG} setuptools \
    && pip3 install --no-cache-dir ${PIP_BREAK_FLAG} -r ${RABBITMQ_HOME}/requirements.txt \
    && rm -rf /var/cache/apk/*


# Upgrade all tools to avoid vulnerabilities
RUN set -x && apk upgrade --no-cache --available


USER ${USER_UID}

VOLUME ["${RABBITMQ_BACKUP}"]

