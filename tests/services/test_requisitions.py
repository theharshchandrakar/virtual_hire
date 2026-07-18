"""Tests for app.services.requisitions (VHIRE-24 / E3): CRUD plus the
I5-style status-transition guard. Uses a fake AsyncSession rather than
live Postgres.
"""

import uuid

import pytest

from app.models.enums import JobRequisitionStatus
from app.models.job_requisition import JobRequisition
from app.services import requisitions


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self):
        self.store: dict[uuid.UUID, JobRequisition] = {}
        self.commit_calls = 0

    def add(self, obj: JobRequisition) -> None:
        self.store[obj.id] = obj

    async def commit(self) -> None:
        self.commit_calls += 1

    async def refresh(self, obj: JobRequisition) -> None:
        return None

    async def execute(self, stmt):
        filtered_id = stmt.whereclause.right.value
        return _FakeResult(self.store.get(filtered_id))


def _requisition(status: JobRequisitionStatus) -> JobRequisition:
    return JobRequisition(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        title="Engineer",
        department=None,
        owner_hr_user_id=uuid.uuid4(),
        status=status,
        scorecard_template={"communication": "1-5"},
    )


async def test_create_requisition_defaults_to_draft():
    session = _FakeSession()

    requisition = await requisitions.create_requisition(
        session,
        organization_id=uuid.uuid4(),
        title="Engineer",
        department="Engineering",
        owner_hr_user_id=uuid.uuid4(),
        scorecard_template={"communication": "1-5"},
    )

    assert requisition.status == JobRequisitionStatus.draft
    assert session.commit_calls == 1


async def test_get_requisition_returns_none_when_missing():
    session = _FakeSession()

    assert await requisitions.get_requisition(session, uuid.uuid4()) is None


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (JobRequisitionStatus.draft, JobRequisitionStatus.open),
        (JobRequisitionStatus.open, JobRequisitionStatus.on_hold),
        (JobRequisitionStatus.open, JobRequisitionStatus.filled),
        (JobRequisitionStatus.open, JobRequisitionStatus.cancelled),
        (JobRequisitionStatus.on_hold, JobRequisitionStatus.open),
    ],
)
async def test_valid_transitions_succeed(from_status, to_status):
    session = _FakeSession()
    requisition = _requisition(from_status)
    session.store[requisition.id] = requisition

    result = await requisitions.transition_requisition_status(
        session, requisition.id, new_status=to_status
    )

    assert result.status == to_status


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (JobRequisitionStatus.draft, JobRequisitionStatus.filled),
        (JobRequisitionStatus.filled, JobRequisitionStatus.open),
        (JobRequisitionStatus.cancelled, JobRequisitionStatus.open),
        (JobRequisitionStatus.on_hold, JobRequisitionStatus.filled),
    ],
)
async def test_invalid_transitions_are_rejected(from_status, to_status):
    session = _FakeSession()
    requisition = _requisition(from_status)
    session.store[requisition.id] = requisition

    with pytest.raises(requisitions.InvalidStatusTransitionError):
        await requisitions.transition_requisition_status(session, requisition.id, new_status=to_status)


async def test_transition_returns_none_when_missing():
    session = _FakeSession()

    result = await requisitions.transition_requisition_status(
        session, uuid.uuid4(), new_status=JobRequisitionStatus.open
    )

    assert result is None
