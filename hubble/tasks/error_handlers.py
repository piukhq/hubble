from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import rq

from retry_tasks_lib.db.models import RetryTask, RetryTaskStatuses
from retry_tasks_lib.utils import UnresolvableHandlerPathError, resolve_callable_from_path

from hubble.db.session import SessionMaker

from . import logger

if TYPE_CHECKING:
    from inspect import Traceback


def default_handler(
    job: rq.job.Job, exc_type: type, exc_value: Exception, traceback: "Traceback"  # noqa: ARG001
) -> Any:  # noqa: ANN401

    # set task's status to FAILED
    with SessionMaker() as db_session:
        if retry_task := db_session.get(RetryTask, job.kwargs.get("retry_task_id", -1)):
            retry_task.update_task(db_session, status=RetryTaskStatuses.FAILED, clear_next_attempt_time=True)

    return True  # defer to the RQ default handler


def job_meta_handler(job: rq.job.Job, exc_type: type, exc_value: Exception, traceback: "Traceback") -> Callable | bool:
    """Resolves any error handler stored in job.meta.

    Falls back to the default RQ error handler (unless worker
    disable_default_exception_handler flag is set)"""
    if error_handler_path := job.meta.get("error_handler_path"):
        try:
            error_handler = resolve_callable_from_path(error_handler_path)
            return error_handler(job, exc_type, exc_value, traceback)
        except UnresolvableHandlerPathError as ex:
            logger.warning(f"Could not import error handler for job {job} (meta={job.meta}): {ex}")
    return True
