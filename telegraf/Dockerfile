FROM telegraf:1.37-alpine

ENV RABBITMQ_MONITORING_HOME=/opt/rabbitmq-monitoring \
    USER_UID=1000

RUN mkdir -p ${RABBITMQ_MONITORING_HOME}

COPY config/requirements.txt ${RABBITMQ_MONITORING_HOME}/requirements.txt
COPY exec-scripts/ ${RABBITMQ_MONITORING_HOME}/exec-scripts/
COPY telegraf.conf /etc/telegraf/telegraf.conf

# Avoiding vulnerabilities
RUN set -x \
    && apk add --upgrade --no-cache apk-tools

RUN set -x \
    && apk add --upgrade --no-cache bash shadow python3 python3-dev vim rsync ttyd build-base

RUN set -x \
    && apk add --upgrade --no-cache openssl-dev cyrus-sasl-dev lz4-dev zlib-dev libsasl

RUN rm /usr/lib/python3.12/EXTERNALLY-MANAGED

# Install misc tools
RUN set -x \
    && apk add --upgrade --no-cache curl tini python3 apk-tools \
    && python3 -m ensurepip \
    && rm -r /usr/lib/python*/ensurepip \
    && pip3 install --upgrade pip setuptools==80.9.0 \
    && pip3 install -r ${RABBITMQ_MONITORING_HOME}/requirements.txt \
    && chmod -R 777 ${RABBITMQ_MONITORING_HOME}/exec-scripts

# Upgrade all tools to avoid vulnerabilities
RUN set -x && apk upgrade --no-cache --available

WORKDIR ${RABBITMQ_MONITORING_HOME}

USER ${USER_UID}

ENTRYPOINT ["/sbin/tini", "--", "/entrypoint.sh"]
CMD ["telegraf"]
