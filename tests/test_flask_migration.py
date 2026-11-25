"""Переход со старой базы без потери данных и доступа к заявкам."""

import sqlite3
from pathlib import Path

from conftest import csrf, login

from infosec_desk.db import connect, initialize
from infosec_desk.security import password_hash
from infosec_desk.web import create_app


def test_existing_database_remains_usable_after_flask_migration(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    schema = (Path(__file__).parent / "fixtures" / "schema_v1.sql").read_text(encoding="utf-8")
    tables = ("users", "assets", "tickets", "comments", "audit_events")
    with sqlite3.connect(path) as db:
        db.executescript(schema)
        db.execute(
            "INSERT INTO users(username,full_name,password_hash,role) VALUES(?,?,?,?)",
            ("alice", "Заявитель", password_hash("AliceTest123!"), "requester"),
        )
        db.execute(
            "INSERT INTO assets(inventory_no,name,location,protection_class) VALUES(?,?,?,?)",
            ("FW-01", "Межсетевой экран", "Серверная", "Сетевой"),
        )
        db.execute(
            "INSERT INTO tickets(title,description,category,priority,asset_id,author_id) "
            "VALUES(?,?,?,?,?,?)",
            ("Заявка до переноса", "Описание сохранённой заявки", "network", "high", 1, 1),
        )
        db.execute(
            "INSERT INTO comments(ticket_id,author_id,body) VALUES(?,?,?)",
            (1, 1, "Комментарий до переноса"),
        )
        db.execute(
            "INSERT INTO audit_events(actor_id,ticket_id,action,details) VALUES(?,?,?,?)",
            (1, 1, "created", "Заявка зарегистрирована до переноса"),
        )
        original = {
            table: db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall() for table in tables
        }

    app = create_app(path, secret_key="migration-test-secret")
    app.testing = True
    initialize(path)
    with connect(path) as db:
        for table in tables:
            actual = [tuple(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY id")]
            assert actual == original[table]
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []

    with app.test_client() as client:
        assert login(client).status_code == 200
        page = client.get("/tickets/1")
        assert page.status_code == 200
        assert "Заявка до переноса" in page.get_data(as_text=True)
        assert "Комментарий до переноса" in page.get_data(as_text=True)
        assert client.get("/users").status_code == 403
        response = client.post(
            "/tickets",
            data={
                "csrf_token": csrf(client, "/tickets/new"),
                "title": "Заявка после переноса",
                "description": "Проверка регистрации новой заявки на Flask",
                "category": "network",
                "priority": "normal",
                "asset_id": "1",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "Заявка после переноса" in response.get_data(as_text=True)

    with connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 2
        assert (
            db.execute("SELECT new_status FROM ticket_status_history WHERE ticket_id=2").fetchone()[
                0
            ]
            == "new"
        )
