FROM ghcr.io/binkhq/python:3.11
ARG PIP_INDEX_URL
ARG APP_NAME
ARG APP_VERSION
WORKDIR /app
RUN pip install --no-cache ${APP_NAME}==$(echo ${APP_VERSION} | cut -c 2-)

ENV PROMETHEUS_MULTIPROC_DIR=/dev/shm
CMD [ "python", "-m", "hubble.cli", "activity-consumer" ]
