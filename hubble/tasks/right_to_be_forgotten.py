import hashlib
import re

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
from uuid import UUID

from retry_tasks_lib.db.models import RetryTask, RetryTaskStatuses, TaskTypeKey, TaskTypeKeyValue
from retry_tasks_lib.utils.synchronous import retryable_task
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from hubble.config import redis_raw, settings
from hubble.db.models import Activity
from hubble.db.session import SessionMaker
from hubble.tasks.prometheus import task_processing_time_callback_fn, tasks_run_total

from . import logger

if TYPE_CHECKING:

    from sqlalchemy.orm import Session


ACCOUNT_CREDENTIALS = (
    "email",
    "first_name",
    "last_name",
    "date_of_birth",
    "phone",
    "address_line1",
    "address_line2",
    "postcode",
    "city",
    "custom",
)


def _encode_value(account_holder_uuid: str | UUID, value: Any | None) -> str:
    """
    Returns hashlib.sha224 encoded hash str of the input str account_holder_uuid

    If the value to hash isn't the account_holder_uuid, account_holder_uuid is still
    required as it is used as suffix and the combined str is hashed
    """
    identifier = value + str(account_holder_uuid) if value else str(account_holder_uuid)
    return hashlib.sha224((identifier).encode("utf-8")).hexdigest()


def _encode_email_in_string(account_holder_uuid: str, str_val: str) -> str:
    """
    Return the original string with an email with the email replaced with
    a hashed email + account_holder_uuid value

    i.e 'Enrolment Requested for qatest+011@bink.com' becomes
    'Enrolment Requested for 5a8612c878a17ec322d90d6ae2c26007533b4cb4699b4392d44f106d'

    Parameters:
            account_holder_uuid (str): the account holder uuid
            str_val (str): The original string containing an email

    Returns:
            hashed_str (str): Original string with hashed email
    """
    pattern = r"[\w.+-]+@[\w-]+\.[\w.-]+"
    extracted_val = re.findall(pattern, str_val)
    encoded_val = _encode_value(account_holder_uuid, extracted_val[0])
    return re.sub(pattern, encoded_val, str_val)


def _encode_field_values_in_data(account_holder_uuid: str, data: dict) -> dict:
    """
    Returns the input AccountRequestActivityData with the specified
    field values hashed with _encode_value fn

    Parameters:
            account_holder_uuid (str): the account holder uuid
            data (AccountRequestActivityData): The original activity data

    Returns:
            data (AccountRequestActivityData): Original data with hashed field values
    """
    for field in data["fields"]:
        if field["field_name"] in ACCOUNT_CREDENTIALS:
            field["value"] = _encode_value(account_holder_uuid, field["value"])
    return data


def _anonymise_account_request_activity(activity: Activity, account_holder_uuid: str) -> str:
    activity.summary = _encode_email_in_string(account_holder_uuid, activity.summary)
    activity.associated_value = _encode_value(account_holder_uuid, activity.associated_value)
    activity.data = _encode_field_values_in_data(account_holder_uuid, activity.data)
    flag_modified(activity, "data")
    return str(activity.id)


def _get_account_activities(
    db_session: "Session", retailer_slug: str, account_holder_uuid: str, account_holder_email: str, activity_type: str
) -> "Sequence[Activity]":
    return (
        db_session.execute(
            select(Activity)
            .with_for_update(skip_locked=True)
            .where(
                Activity.retailer == retailer_slug,
                Activity.type == activity_type,
                (Activity.associated_value.ilike(account_holder_email)) | (Activity.user_id == account_holder_uuid),
            )
        )
        .scalars()
        .all()
    )


# NOTE: Inter-dependency: If this function's name or module changes, ensure that
# it is relevantly reflected in the TaskType table
@retryable_task(
    db_session_factory=SessionMaker, redis_connection=redis_raw, metrics_callback_fn=task_processing_time_callback_fn
)
def anonymise_activities(retry_task: RetryTask, db_session: "Session") -> None:
    if settings.ACTIVATE_TASKS_METRICS:
        tasks_run_total.labels(app=settings.PROJECT_NAME, task_name=settings.ANONYMISE_ACTIVITIES_TASK_NAME).inc()

    task_params: dict[str, str] = retry_task.get_params()
    account_holder_uuid = task_params["account_holder_uuid"]

    # At the time of writing (09/03/2023). ACCOUNT_REQUEST is the only activity which contains information
    # needing to be hashed
    account_activities = _get_account_activities(
        db_session,
        task_params["retailer_slug"],
        account_holder_uuid,
        task_params["account_holder_email"],
        "ACCOUNT_REQUEST",
    )
    if updated_activities := [
        _anonymise_account_request_activity(activity, account_holder_uuid) for activity in account_activities
    ]:

        db_session.commit()
        logger.info(
            "Successfully anonymised the following activities: %s for account_holder_uuid: %s",
            updated_activities,
            account_holder_uuid,
        )
    else:
        logger.info("No activities to update")

    db_session.execute(
        TaskTypeKeyValue.__table__.delete().where(
            TaskTypeKeyValue.retry_task_id == retry_task.retry_task_id,
            TaskTypeKeyValue.task_type_key_id == TaskTypeKey.task_type_key_id,
            TaskTypeKey.name == "account_holder_email",
        )
    )
    db_session.flush()
    retry_task.update_task(db_session, status=RetryTaskStatuses.SUCCESS, clear_next_attempt_time=True)
