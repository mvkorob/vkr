"""Проверки доступа, показателей и пользовательских страниц."""

import sys

import pytest

from infosec_desk import __main__
from infosec_desk.db import connect, initialize
from infosec_desk.service import (
    authenticate,
    create_user,
    reset_admin_password,
    statistics,
)


def test_password_reset_changes_existing_admin(tmp_path, monkeypatch):
    path = tmp_path / "service.sqlite3"
    initialize(path)
    user_id = create_user(path, "admin", "Администратор", "OldPassword123!", "admin")
    monkeypatch.setattr(sys, "argv", ["run.py", "reset-password", "--db", str(path)])
    passwords = iter(["NewPassword123!", "NewPassword123!"])
    monkeypatch.setattr(__main__.getpass, "getpass", lambda prompt: next(passwords))
    __main__.main()

    assert authenticate(path, "admin", "OldPassword123!") is None
    assert authenticate(path, "admin", "NewPassword123!")["id"] == user_id
    with connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert db.execute("SELECT action FROM audit_events").fetchone()[0] == "password_reset"


def test_password_reset_rejects_mismatch(tmp_path, monkeypatch):
    path = tmp_path / "service.sqlite3"
    initialize(path)
    create_user(path, "admin", "Администратор", "OldPassword123!", "admin")
    monkeypatch.setattr(sys, "argv", ["run.py", "reset-password", "--db", str(path)])
    passwords = iter(["NewPassword123!", "WrongPassword123!"])
    monkeypatch.setattr(__main__.getpass, "getpass", lambda prompt: next(passwords))

    with pytest.raises(SystemExit):
        __main__.main()
    assert authenticate(path, "admin", "OldPassword123!") is not None


def test_password_reset_only_for_admin(tmp_path):
    path = tmp_path / "service.sqlite3"
    initialize(path)
    create_user(path, "employee", "Сотрудник", "OldPassword123!", "requester")
    with pytest.raises(ValueError, match="администратор"):
        reset_admin_password(path, "employee", "NewPassword123!")
    assert authenticate(path, "employee", "OldPassword123!") is not None


@pytest.mark.parametrize("role", ["requester", "operator", "admin"])
def test_statistics_empty_registry_has_zero_counts(db_path, role):
    stats = statistics(db_path, {"id": 3, "role": role})
    assert stats == {
        "total": 0,
        "open": 0,
        "resolved": 0,
        "critical": 0,
        "by_status": {
            "new": 0, "in_progress": 0, "on_hold": 0, "resolved": 0, "closed": 0,
        },
    }


def test_statistics_empty_requester_ignores_other_users_tickets(db_path):
    with connect(db_path) as db:
        db.execute(
            "INSERT INTO tickets(title,description,category,priority,author_id) "
            "VALUES(?,?,?,?,?)",
            ("Чужая заявка", "Проверка пустой статистики", "access", "critical", 3),
        )
        db.commit()
    stats = statistics(db_path, {"id": 4, "role": "requester"})
    assert all(stats[key] == 0 for key in ("total", "open", "resolved", "critical"))
    assert all(value == 0 for value in stats["by_status"].values())
    assert statistics(db_path, {"id": 1, "role": "admin"})["critical"] == 1


def test_statistics_not_limited_to_first_500_tickets(db_path):
    user = {"id": 3, "role": "requester"}
    with connect(db_path) as db:
        db.executemany(
            """INSERT INTO tickets(title,description,category,priority,author_id)
               VALUES(?,?,?,?,?)""",
            [(f"Test {i}", "Проверка счетчиков", "access", "normal", 3) for i in range(513)],
        )
        db.commit()
    stats = statistics(db_path, user)
    assert stats["total"] == 513
    assert stats["open"] == 513
    assert stats["resolved"] == 0
    assert stats["by_status"]["new"] == 513


def test_unprivileged_dashboard_hides_admin_navigation(client):
    from conftest import login

    login(client)
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/users"' not in response.get_data(as_text=True)
    assert "Локальная система" not in response.get_data(as_text=True)
    assert 'aria-current="page"' in response.get_data(as_text=True)


def test_favicon_and_403_page(client):
    from conftest import login

    favicon = client.get("/favicon.ico", follow_redirects=True)
    assert favicon.status_code == 200
    assert "svg" in favicon.headers["content-type"]
    login(client)
    forbidden = client.get("/users")
    assert forbidden.status_code == 403
    assert "Недостаточно прав" in forbidden.get_data(as_text=True)
