FROM python:3.10-alpine3.23

ENV WORKDIR=/opt/operator/ \
    USER_UID=1000 \
    USER_NAME=rabbitmq-operator

COPY build/requirements.txt requirements.txt
COPY src/handler.py ${WORKDIR}
COPY src/rabbitconstants.py ${WORKDIR}
COPY src/rabbit_helper.py ${WORKDIR}
COPY src/backup_helper.py ${WORKDIR}
COPY src/exceptions.py ${WORKDIR}
COPY src/velero_delete_pods_rmqlocal.py ${WORKDIR}
COPY build/user_setup /usr/local/bin
COPY build/entrypoint /usr/local/bin

RUN apk add --update --no-cache bash build-base apk-tools \
    && apk upgrade --no-cache --available \
    && apk add --no-cache \
        --repository=https://dl-cdn.alpinelinux.org/alpine/edge/main \
        binutils=2.45.1-r1

RUN python -m pip install --no-cache-dir --upgrade "pip>=26.0" "setuptools==80.10.1" "jaraco.context>=6.1.0" \
    && pip install --no-cache-dir -r requirements.txt

RUN chmod 777 /usr/local/bin/user_setup && \
chmod 777 /usr/local/bin/entrypoint && \
chmod 777 /opt/operator/rabbitconstants.py && \
chmod 777 /opt/operator/rabbit_helper.py && \
chmod 777 /opt/operator/handler.py && \
chmod 777 /opt/operator/velero_delete_pods_rmqlocal.py
RUN /usr/local/bin/user_setup

ENTRYPOINT ["/usr/local/bin/entrypoint"]

CMD ["sh", "-c", "kopf run -n ${WATCH_NAMESPACE} --liveness=http://0.0.0.0:8081/healthz --standalone /opt/operator/handler.py"]

USER ${USER_UID}
