FROM library/rabbitmq:3.13.7-management-alpine

COPY docker-entrypoint.sh /usr/local/bin/
COPY scripts/get_user /bin/
COPY scripts/get_password /bin/
COPY scripts/change_password /bin/

ARG RABBITMQ_QUEUE_MIGRATION_VERSION="1.0.6"
RUN set -x \
    && wget \
        -nv \
        -O /opt/rabbitmq/plugins/rabbitmq_queue_migration-${RABBITMQ_QUEUE_MIGRATION_VERSION}.ez \
        "https://github.com/amazon-mq/rabbitmq-queue-migration/releases/download/${RABBITMQ_QUEUE_MIGRATION_VERSION}/rabbitmq_queue_migration-${RABBITMQ_QUEUE_MIGRATION_VERSION}.ez"

ENV USER_UID=1000

RUN echo "https://dl-cdn.alpinelinux.org/alpine/v3.23/main" > /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/v3.23/community" >> /etc/apk/repositories

RUN set -x && apk upgrade --no-cache --available

# Upgrade tools from edge to avoid vulnerabilities
RUN apk add --no-cache \
    --repository=https://dl-cdn.alpinelinux.org/alpine/edge/main \
    libssl3=3.5.7-r0 libcrypto3=3.5.7-r0

RUN ln -sf /usr/local/bin/docker-entrypoint.sh && \
mkdir -p /var/log/rabbitmq && \
chmod -R  777 /var/log/rabbitmq && \
chmod +x /bin/change_password && \
chmod +x /bin/get_user && \
chmod +x /bin/get_password && \
chmod +x /usr/local/bin/docker-entrypoint.sh && \
chmod -R  a+r /opt/rabbitmq/plugins

RUN rm /usr/lib/python3.12/EXTERNALLY-MANAGED

RUN set -x \
    && python3 -m ensurepip \
    && rm -r /usr/lib/python*/ensurepip \
    && apk add --update --no-cache curl \
    && pip3 install --upgrade pip "setuptools==80.10.1" \
    && rm -rf /var/cache/apk/*

COPY logging_definitions.json /etc/rabbitmq/

VOLUME /var/log/rabbitmq
VOLUME /tmp

ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 4369 5671 5672 25672

USER ${USER_UID}

CMD ["rabbitmq-server"]