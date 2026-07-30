from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from schemas.plan import PlanCreate, PlanUpdate
from schemas.task import TaskCreate, TaskUpdate


def test_plan_time_is_normalized_to_utc_naive():
    china_time = timezone(timedelta(hours=8))

    plan = PlanCreate(
        title="Plan",
        start_time=datetime(
            2026,
            7,
            5,
            10,
            tzinfo=china_time,
        ),
    )

    assert plan.start_time == datetime(2026, 7, 5, 2)


def test_request_time_without_timezone_is_rejected():
    with pytest.raises(ValidationError):
        TaskCreate(
            title="Task",
            due_time=datetime(2026, 7, 5, 10),
        )


def test_patch_distinguishes_omitted_and_explicit_null():
    assert PlanUpdate().model_dump(exclude_unset=True) == {}
    assert PlanUpdate(
        description=None,
    ).model_dump(exclude_unset=True) == {
        "description": None,
    }
    assert TaskUpdate(
        acceptance_criteria=None,
    ).model_dump(exclude_unset=True) == {
        "acceptance_criteria": None,
    }
