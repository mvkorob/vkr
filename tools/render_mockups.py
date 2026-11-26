"""Сохраняет статические макеты из текущих шаблонов на временной базе."""

import argparse
import hashlib
import html
import re
import secrets
import shutil
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PAGES = {
    "login": "/login",
    "dashboard": "/",
    "tickets": "/tickets",
    "ticket_new": "/tickets/new",
    "ticket_detail": "/tickets/1",
    "public_overview": "/public/overview",
    "public_services": "/public/services",
    "public_submit": "/public/submit",
    "public_categories": "/public/categories",
    "public_priorities": "/public/priorities",
    "public_status": "/public/status",
    "public_tracking": "/public/tracking",
    "public_faq": "/public/faq",
    "public_security": "/public/security",
    "public_help": "/public/help",
    "public_contacts": "/public/contacts",
    "public_rules": "/public/rules",
    "feedback": "/feedback",
    "profile": "/profile",
    "my_help": "/my-help",
    "my_activity": "/my-activity",
    "notifications": "/notifications",
}
LINKS = {route: name + ".html" for name, route in PAGES.items()}


class StaticPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []

    def handle_decl(self, decl):
        self.parts.append("<!" + decl + ">")

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            attrs.update(action="#", method="get", onsubmit="return false")
        if tag == "input" and attrs.get("name") == "csrf_token":
            attrs["value"] = ""
        for key in ("href", "src"):
            value = attrs.get(key, "")
            if value.startswith("/static/"):
                asset = value.split("/static/", 1)[1].split("?")[0]
                attrs[key] = "../../src/infosec_desk/static/" + asset
            elif key == "href" and value.startswith("/"):
                attrs[key] = LINKS.get(value, "#")
                if attrs[key] == "#":
                    attrs["aria-disabled"] = "true"
        attributes = "".join(
            " " + key if value is None else f' {key}="{html.escape(value, quote=True)}"'
            for key, value in attrs.items()
        )
        self.parts.append("<" + tag + attributes + ">")

    def handle_endtag(self, tag):
        self.parts.append("</" + tag + ">")

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append("&" + name + ";")

    def handle_charref(self, name):
        self.parts.append("&#" + name + ";")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", nargs="+", choices=PAGES, default=list(PAGES))
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    from infosec_desk import service
    from infosec_desk.web import create_app

    source = ROOT / "instance" / "demo.sqlite3"
    digest = hashlib.sha256(source.read_bytes()).digest()
    output = ROOT / "docs" / "mockups"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="infosec-mockups-") as folder:
        database = Path(folder) / "demo.sqlite3"
        shutil.copy2(source, database)
        app = create_app(database, secret_key=secrets.token_urlsafe(32))
        app.testing = True
        original_list = service.list_tickets

        def preview_tickets(*a, **kw):
            kw["limit"] = min(kw.get("limit") or 25, 25)
            return original_list(*a, **kw)

        with app.test_client() as client:
            for name in args.pages:
                with client.session_transaction() as session:
                    session.clear()
                    if name not in ("login", "feedback") and not name.startswith("public_"):
                        session["user_id"] = 3
                with patch.object(service, "list_tickets", side_effect=preview_tickets):
                    response = client.get(PAGES[name])
                assert response.status_code == 200, name
                renderer = StaticPage()
                renderer.feed(response.get_data(as_text=True))
                result = "".join(renderer.parts)
                result = re.sub(r"[ \t]+\n", "\n", result)
                (output / (name + ".html")).write_text(result, encoding="utf-8")
                print(name + ".html: готов")
    assert hashlib.sha256(source.read_bytes()).digest() == digest


if __name__ == "__main__":
    main()
