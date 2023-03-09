import logging

from prometheus_client import Counter, Histogram

from hubble.config import settings

logger = logging.getLogger(__name__)

METRIC_NAME_PREFIX = "bpl_"


tasks_run_total = Counter(
    name=f"{METRIC_NAME_PREFIX}tasks_run_total",
    documentation="Counter for tasks run.",
    labelnames=("app", "task_name"),
)


tasks_processing_time_histogram = Histogram(
    name=f"{METRIC_NAME_PREFIX}tasks_processing_time",
    documentation="Total time taken by a task to process",
    labelnames=("app", "task_name"),
)


def task_processing_time_callback_fn(task_processing_time: float, task_name: str) -> None:
    logger.info(f"Updating {tasks_processing_time_histogram} metrics...")
    tasks_processing_time_histogram.labels(app=settings.PROJECT_NAME, task_name=task_name).observe(task_processing_time)
