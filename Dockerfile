FROM ghcr.io/binkhq/python:3.10

WORKDIR /app
ADD . .
RUN pipenv install --deploy --system --ignore-pipfile

ENV PROMETHEUS_MULTIPROC_DIR=/dev/shm
ENTRYPOINT [ "linkerd-await", "--" ]
CMD [ "python", "-m", "app.cli", "activity-consumer" ]
