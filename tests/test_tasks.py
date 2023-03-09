from random import choice
from typing import TYPE_CHECKING
from uuid import uuid4

from retry_tasks_lib.enums import RetryTaskStatuses

from hubble.db.models import Activity
from hubble.tasks.right_to_be_forgotten import ACCOUNT_CREDENTIALS, anonymise_activities

if TYPE_CHECKING:
    from collections.abc import Callable

    from retry_tasks_lib.db.models import RetryTask
    from sqlalchemy.orm import Session


def test_anonymise_activities(
    db_session: "Session", create_activity: "Callable[..., Activity]", anonymise_activities_task: "RetryTask"
) -> None:

    task_params = anonymise_activities_task.get_params()

    non_releavant_activities = [create_activity(id=uuid4(), type="OTHER") for _ in range(2)]

    releavant_activities = [
        create_activity(
            id=uuid4(),
            type="ACCOUNT_REQUEST",
            retailer=task_params["retailer_slug"],
            associated_value=task_params["account_holder_email"] if (is_even := i % 2 == 0) else "N/A",
            user_id="N/A" if is_even else task_params["account_holder_uuid"],
            summary=f"test summary {task_params['account_holder_email']}",
            data={
                "fields": [
                    {
                        "field_name": "email",
                        "value": task_params["account_holder_email"],
                    },
                    {"field_name": "first_name", "value": f"Test {i}"},
                    {"field_name": "last_name", "value": "User"},
                    {
                        "field_name": choice(ACCOUNT_CREDENTIALS[3:]),
                        "value": "sample value",
                    },
                ],
            },
        )
        for i in range(4)
    ]

    anonymise_activities(anonymise_activities_task.retry_task_id)

    db_session.refresh(anonymise_activities_task)
    assert anonymise_activities_task.status == RetryTaskStatuses.SUCCESS
    assert "account_holder_email" not in anonymise_activities_task.get_params()

    def compare_activities(activity_list: list["Activity"], expect_anon: bool) -> None:
        def get_sorting_key(item: dict) -> str:
            return item["field_name"]

        for act in activity_list:

            summary = act.summary
            associated_value = act.associated_value
            data = act.data.copy()

            db_session.refresh(act)

            if expect_anon:
                assert summary != act.summary
                assert task_params["account_holder_email"] not in act.summary
                assert task_params["account_holder_uuid"] not in act.summary
                assert associated_value != act.associated_value
                assert task_params["account_holder_uuid"] not in act.associated_value
                assert task_params["account_holder_email"] not in act.associated_value

                for old_val, new_val in zip(
                    sorted(data["fields"], key=get_sorting_key),
                    sorted(act.data["fields"], key=get_sorting_key),
                    strict=True,
                ):

                    assert old_val["value"] != new_val["value"]
                    if new_val["field_name"] == "email":
                        assert task_params["account_holder_email"] not in new_val["value"]

            else:
                assert summary == act.summary
                assert associated_value == act.associated_value
                assert data == act.data

    compare_activities(non_releavant_activities, expect_anon=False)
    compare_activities(releavant_activities, expect_anon=True)
