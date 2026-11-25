"""Подсчёт непустых строк отслеживаемых файлов проекта по категориям."""

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = {".py", ".html", ".css", ".sql"}


def category(path):
    if path in (Path("run.py"), Path("wsgi.py")) or path.parts[0] in {"src", "sql"}:
        return "application"
    if path.parts[0] == "tests" and path.suffix == ".py":
        return "tests"
    if path.parts[0] == "tools" and path.suffix == ".py":
        return "tools"
    return None


def count_lines(path):
    text = path.read_text(encoding="utf-8")
    if path.suffix in {".css", ".html"}:
        pattern = r"/\*.*?\*/" if path.suffix == ".css" else r"<!--.*?-->"
        text = re.sub(pattern, lambda m: "\n" * m.group().count("\n"), text, flags=re.S)
    prefix = "#" if path.suffix == ".py" else "--" if path.suffix == ".sql" else None
    return sum(
        bool(line.strip()) and not (prefix and line.lstrip().startswith(prefix))
        for line in text.splitlines()
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="вывести результат в JSON")
    args = parser.parse_args()
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    files = []
    totals = dict.fromkeys(("application", "tests", "tools"), 0)
    for name in sorted(filter(None, tracked)):
        path = Path(name)
        group = category(path)
        if group is None or path.suffix not in EXTENSIONS:
            continue
        count = count_lines(ROOT / path)
        files.append({"path": path.as_posix(), "category": group, "lines": count})
        totals[group] += count
    result = {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "metric": "nonempty_physical_lines_excluding_comments",
        "totals": totals,
        "total": sum(totals.values()),
        "files": files,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in files:
            print(f"{item['lines']:5} {item['category']:12} {item['path']}")
        for group, count in totals.items():
            print(f"{group}: {count}")
        print(f"Total: {result['total']}")


if __name__ == "__main__":
    main()
