FROM alibrary/rabbitmq:4.0.7-management-alpine

COPY docker-entrypoint.sh /usr/local/bin/
COPY /openshift/scripts/get_user /bin/
COPY /openshift/scripts/get_password /bin/
COPY /openshift/scripts/change_password /bin/

ENV USER_UID=1000

RUN set -x && apk upgrade --no-cache --available

RUN ln -sf usr/local/bin/docker-entrypoint.sh && \
mkdir -p /var/log/rabbitmq && \
chmod -R  777 /var/log/rabbitmq && \
chmod -R  777 /etc/rabbitmq && \
chmod +x /bin/change_password && \
chmod +x /bin/get_user && \
chmod +x /bin/get_password && \
chmod +x /usr/local/bin/docker-entrypoint.sh && \
chmod -R  a+r /opt/rabbitmq/plugins

RUN rm /usr/lib/python3.11/EXTERNALLY-MANAGED

RUN set -x \
    && python3 -m ensurepip \
    && rm -r /usr/lib/python*/ensurepip \
    && apk add --update --no-cache curl \
    && pip3 install --upgrade pip setuptools \
    && rm -rf /var/cache/apk/*

COPY logging_definitions.json /etc/rabbitmq/

VOLUME /etc/rabbitmq
VOLUME /var/log/rabbitmq
VOLUME /tmp

ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 4369 5671 5672 25672

USER ${USER_UID}

CMD ["rabbitmq-server"]
