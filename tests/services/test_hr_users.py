"""Tests for app.services.hr_users (VHIRE-24 / E3): invite/activate/
deactivate lifecycle. Uses a fake AsyncSession rather than live Postgres -
these test this module's own logic, not RLS (that's E13's job).
"""

import uuid

from app.models.enums import HRUserRole, HRUserStatus
from app.models.hr_user import HRUser
from app.services import hr_users


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self):
        self.store: dict[uuid.UUID, HRUser] = {}
        self.commit_calls = 0

    def add(self, obj: HRUser) -> None:
        self.store[obj.id] = obj

    async def commit(self) -> None:
        self.commit_calls += 1

    async def refresh(self, obj: HRUser) -> None:
        return None

    async def execute(self, stmt):
        filtered_id = stmt.whereclause.right.value
        return _FakeResult(self.store.get(filtered_id))


async def test_invite_hr_user_creates_invited_status():
    session = _FakeSession()
    org_id = uuid.uuid4()

    hr_user = await hr_users.invite_hr_user(
        session,
        organization_id=org_id,
        email="new@example.test",
        full_name="New Hire",
        role=HRUserRole.recruiter,
    )

    assert hr_user.status == HRUserStatus.invited
    assert hr_user.organization_id == org_id
    assert session.commit_calls == 1


async def test_get_hr_user_returns_none_when_missing():
    session = _FakeSession()

    assert await hr_users.get_hr_user(session, uuid.uuid4()) is None


async def test_activate_hr_user_transitions_invited_to_active():
    session = _FakeSession()
    hr_user = HRUser(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email="x@example.test",
        full_name="X",
        role=HRUserRole.recruiter,
        status=HRUserStatus.invited,
    )
    session.store[hr_user.id] = hr_user

    result = await hr_users.activate_hr_user(session, hr_user.id)

    assert result.status == HRUserStatus.active


async def test_activate_hr_user_returns_none_when_missing():
    session = _FakeSession()

    assert await hr_users.activate_hr_user(session, uuid.uuid4()) is None


async def test_deactivate_hr_user_transitions_to_deactivated():
    session = _FakeSession()
    hr_user = HRUser(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email="x@example.test",
        full_name="X",
        role=HRUserRole.recruiter,
        status=HRUserStatus.active,
    )
    session.store[hr_user.id] = hr_user

    result = await hr_users.deactivate_hr_user(session, hr_user.id)

    assert result.status == HRUserStatus.deactivated
