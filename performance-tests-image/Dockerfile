FROM eclipse-temurin:21-jdk-alpine

ADD https://github.com/rabbitmq/rabbitmq-perf-test/releases/download/v2.2.0/rabbitmq-perf-test-2.2.0-bin.tar.gz /PERFORMANCETEST/

RUN tar -xzf ./PERFORMANCETEST/rabbitmq-perf-test-2.2.0-bin.tar.gz -C ./PERFORMANCETEST && \
chmod -R 777 /PERFORMANCETEST && \
echo "alias perftest='bin/runjava -cp \"lib/*\" com.rabbitmq.perf.PerfTest'" >> ~/.bashrc
    

ENTRYPOINT ["sleep", "10000000"]
