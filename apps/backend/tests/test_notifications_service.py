import pytest
from fastapi import HTTPException

from app.auth import CurrentUser
from app.notifications import service
from tests.fakes import FakeDb

USER = CurrentUser(user_id="user-1", household_id=42)


def notification(id, user_id="user-1", read=False, created_at="2026-08-05T10:00:00Z", **extra):
    row = {
        "id": id,
        "user_id": user_id,
        "type": "budget_ceiling",
        "severity": "warning",
        "title": "Perto do teto",
        "message": "Já usou 96%",
        "read": read,
        "reference_month": "2026-08-01",
        "subject": "necessidades",
        "created_at": created_at,
    }
    row.update(extra)
    return row


def install(monkeypatch, rows):
    db = FakeDb({"notifications": rows})
    monkeypatch.setattr(service, "get_db", lambda: db)
    return db


async def test_only_returns_own_notifications(monkeypatch):
    install(monkeypatch, [notification(1), notification(2, user_id="outro")])

    result = await service.list_notifications(USER)

    assert [row["id"] for row in result["items"]] == [1]


async def test_unread_filter(monkeypatch):
    install(monkeypatch, [notification(1, read=False), notification(2, read=True)])

    result = await service.list_notifications(USER, unread=True)

    assert [row["id"] for row in result["items"]] == [1]


async def test_without_filter_returns_read_and_unread(monkeypatch):
    install(monkeypatch, [notification(1, read=False), notification(2, read=True)])

    result = await service.list_notifications(USER)

    assert len(result["items"]) == 2
    assert result["unread_count"] == 1


async def test_newest_first(monkeypatch):
    install(
        monkeypatch,
        [
            notification(1, created_at="2026-08-01T10:00:00Z"),
            notification(2, created_at="2026-08-09T10:00:00Z"),
            notification(3, created_at="2026-08-05T10:00:00Z"),
        ],
    )

    result = await service.list_notifications(USER)

    assert [row["id"] for row in result["items"]] == [2, 3, 1]


async def test_unread_count_is_not_limited_by_the_page(monkeypatch):
    """Contar sobre a página truncada faria o badge do sino mostrar menos
    alertas do que realmente existem."""
    install(monkeypatch, [notification(i, read=False) for i in range(1, 61)])

    result = await service.list_notifications(USER, limit=10)

    assert len(result["items"]) == 10
    assert result["unread_count"] == 60


async def test_unread_count_ignores_read_and_other_users(monkeypatch):
    install(
        monkeypatch,
        [
            notification(1, read=False),
            notification(2, read=True),
            notification(3, user_id="outro", read=False),
        ],
    )

    result = await service.list_notifications(USER)

    assert result["unread_count"] == 1


async def test_limit_is_capped(monkeypatch):
    db = install(monkeypatch, [])

    await service.list_notifications(USER, limit=10_000)

    listing = next(q for q in db.queries if not q.count_only)
    assert listing.limit_value == service.MAX_LIMIT


async def test_response_does_not_leak_user_id(monkeypatch):
    install(monkeypatch, [notification(1)])

    result = await service.list_notifications(USER)

    assert "user_id" not in service.NOTIFICATION_COLUMNS
    assert result["items"][0]["id"] == 1


async def test_mark_read_flips_the_flag(monkeypatch):
    db = install(monkeypatch, [notification(1, read=False)])

    await service.mark_read(USER, 1)

    assert db.rows("notifications")[0]["read"] is True


async def test_mark_read_of_another_user_is_404(monkeypatch):
    db = install(monkeypatch, [notification(1, user_id="outro", read=False)])

    with pytest.raises(HTTPException) as exc_info:
        await service.mark_read(USER, 1)

    assert exc_info.value.status_code == 404
    assert db.rows("notifications")[0]["read"] is False


async def test_mark_read_of_missing_notification_is_404(monkeypatch):
    install(monkeypatch, [])

    with pytest.raises(HTTPException) as exc_info:
        await service.mark_read(USER, 404)
    assert exc_info.value.status_code == 404
