FROM ghcr.io/binkhq/python:3.11-poetry as build

WORKDIR /src
RUN poetry config virtualenvs.create false
RUN poetry self add poetry-dynamic-versioning[plugin]
ADD . .
RUN poetry build

FROM ghcr.io/binkhq/python:3.11
ARG PIP_INDEX_URL

WORKDIR /app
COPY --from=build /src/alembic/ ./alembic/
COPY --from=build /src/alembic.ini .
COPY --from=build /src/dist/*.whl .
# gcc required for hiredis
RUN export wheel=$(find -type f -name "*.whl") && \
    apt update && \
    apt -y install gcc && \
    pip install "$wheel" && \
    rm $wheel && \
    apt -y autoremove gcc

ENV PROMETHEUS_MULTIPROC_DIR=/dev/shm
ENTRYPOINT [ "linkerd-await", "--" ]
CMD [ "python", "-m", "hubble.cli", "activity-consumer" ]
