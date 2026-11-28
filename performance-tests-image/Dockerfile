FROM eclipse-temurin:21-jdk-alpine@sha256:c07bb82e004a166b5d3d63b84ad70e2e822f228505e2e0c0b8dfdc2890d22f13

ADD https://github.com/rabbitmq/rabbitmq-perf-test/releases/download/v2.2.0/rabbitmq-perf-test-2.2.0-bin.tar.gz /PERFORMANCETEST/

RUN tar -xzf ./PERFORMANCETEST/rabbitmq-perf-test-2.2.0-bin.tar.gz -C ./PERFORMANCETEST && \
chmod -R 777 /PERFORMANCETEST && \
echo "alias perftest='bin/runjava -cp \"lib/*\" com.rabbitmq.perf.PerfTest'" >> ~/.bashrc
    

ENTRYPOINT ["sleep", "10000000"]
