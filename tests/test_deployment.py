"""Проверки серверного запуска на отдельной копии учебной базы."""

import hashlib
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "instance" / "demo.sqlite3"


def run_entrypoint(path, script, **overrides):
    env = os.environ.copy()
    env.update(
        INFOSEC_SECRET_KEY=secrets.token_urlsafe(32),
        INFOSEC_DEMO_PASSWORD=secrets.token_urlsafe(24),
        INFOSEC_DB_PATH=str(path),
        PYTHONPATH=str(ROOT / "src"),
    )
    env.update(overrides)
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_wsgi_uses_separate_database_and_replaces_demo_passwords(tmp_path):
    before = hashlib.sha256(SOURCE.read_bytes()).digest()
    result = run_entrypoint(
        tmp_path / "demo.sqlite3",
        """
import os
import wsgi
from infosec_desk.service import authenticate
client = wsgi.app.test_client()
assert client.get('/health').status_code == 200
assert client.get('/public/overview').status_code == 200
for username in ('admin', 'operator', 'employee'):
    assert authenticate(wsgi.app.db_path, username, 'DemoPass123!') is None
    assert authenticate(wsgi.app.db_path, username, os.environ['INFOSEC_DEMO_PASSWORD'])
""",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "demo.sqlite3").is_file()
    assert hashlib.sha256(SOURCE.read_bytes()).digest() == before


@pytest.mark.parametrize("key,password", [("", "x" * 20), ("short", "x" * 20), ("x" * 32, "short")])
def test_invalid_secrets_fail_before_database_creation(tmp_path, key, password):
    path = tmp_path / "demo.sqlite3"
    result = run_entrypoint(
        path, "import wsgi", INFOSEC_SECRET_KEY=key, INFOSEC_DEMO_PASSWORD=password
    )
    assert result.returncode != 0
    assert "must be set" in result.stderr
    assert not path.exists()


def test_source_database_cannot_be_used_as_runtime_database():
    before = hashlib.sha256(SOURCE.read_bytes()).digest()
    result = run_entrypoint(SOURCE, "import wsgi")
    assert result.returncode != 0
    assert "separate runtime database" in result.stderr
    assert hashlib.sha256(SOURCE.read_bytes()).digest() == before


def test_restart_preserves_runtime_data(tmp_path):
    path = tmp_path / "demo.sqlite3"
    first = run_entrypoint(
        path,
        """
import wsgi
from contextlib import closing
from infosec_desk.db import connect
with closing(connect(wsgi.app.db_path)) as db:
    db.execute("INSERT INTO feedback_messages(sender_name,sender_email,subject,body) "
               "VALUES('Test','test@example.org','Restart','Saved before restart')")
    db.commit()
""",
    )
    assert first.returncode == 0, first.stderr
    second = run_entrypoint(
        path,
        """
import wsgi
from contextlib import closing
from infosec_desk.db import connect
with closing(connect(wsgi.app.db_path)) as db:
    assert db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 501
    row = db.execute("SELECT body FROM feedback_messages WHERE subject='Restart'").fetchone()
    assert row[0] == 'Saved before restart'
""",
    )
    assert second.returncode == 0, second.stderr
