import logging
import os

import sentry_sdk
import typer

from cosmos_message_lib.connection import get_connection_and_exchange
from prometheus_client import CollectorRegistry
from prometheus_client import start_http_server as start_prometheus_server
from prometheus_client import values
from prometheus_client.multiprocess import MultiProcessCollector
from rq import Worker

from hubble.config import redis_raw, settings
from hubble.messaging.consumer import ActivityConsumer
from hubble.scheduled_tasks.scheduler import cron_scheduler as scheduler
from hubble.scheduled_tasks.task_cleanup import cleanup_old_tasks
from hubble.tasks.error_handlers import job_meta_handler
from hubble.version import __version__

cli = typer.Typer()
logger = logging.getLogger(__name__)

if settings.SENTRY_DSN:  # pragma: no cover
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENV,
        release=__version__,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )


@cli.command()
def activity_consumer() -> None:
    rmq_conn, exchange = get_connection_and_exchange(
        rabbitmq_dsn=settings.RABBIT_DSN, message_exchange_name=settings.MESSAGE_EXCHANGE
    )
    ActivityConsumer(
        rmq_conn,
        exchange,
        queue_name=settings.MESSAGE_QUEUE_NAME,
        routing_key=settings.MESSAGE_ROUTING_KEY,
    ).run()


@cli.command()
def task_worker(burst: bool = False) -> None:  # pragma: no cover

    if settings.ACTIVATE_TASKS_METRICS:
        # -------- this is the prometheus monkey patch ------- #
        values.ValueClass = values.MultiProcessValue(os.getppid)
        # ---------------------------------------------------- #
        registry = CollectorRegistry()
        MultiProcessCollector(registry)
        logger.info("Starting prometheus metrics server...")
        start_prometheus_server(settings.PROMETHEUS_HTTP_SERVER_PORT, registry=registry)

    worker = Worker(
        queues=settings.TASK_QUEUES,
        connection=redis_raw,
        log_job_description=True,
        exception_handlers=[job_meta_handler],
    )
    logger.info("Starting task worker...")
    worker.work(burst=burst, with_scheduler=True)


@cli.command()
def cron_scheduler(
    task_cleanup: bool = True,
) -> None:

    logger.info("Initialising scheduler...")
    if task_cleanup:
        scheduler.add_job(
            cleanup_old_tasks,
            schedule_fn=lambda: settings.TASK_CLEANUP_SCHEDULE,
            coalesce_jobs=True,
        )

    logger.info(f"Starting scheduler {cron_scheduler}...")
    scheduler.run()


@cli.callback()
def callback() -> None:
    """
    hubble command line interface
    """


if __name__ == "__main__":
    cli()
