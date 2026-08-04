import argparse
import fcntl
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

DEFAULT_DAILY_DIR = Path(
    os.path.expanduser("~/Documents/automation/obsidian/main/daily")
)
LOCK_FILENAME = ".daily_note.lock"


def daily_note_path(daily_dir: Path, day: datetime) -> Path:
    return Path(daily_dir) / f"{day:%Y-%m-%d}.md"


def _insert_under_section(
    doc_lines: list[str], section_title: str, entry: list[str]
) -> list[str]:
    lines = list(doc_lines)
    section_idx = next(
        (i for i, line in enumerate(lines) if line.strip() == section_title), None
    )
    if section_idx is None:
        lines.append(section_title)
        lines.extend(entry)
        return lines

    section_end = len(lines)
    for i in range(section_idx + 1, len(lines)):
        if lines[i].startswith("## "):
            section_end = i
            break
    lines[section_end:section_end] = list(entry)
    return lines


@contextmanager
def _locked(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _entry_lines(entry_title: str, lines: list[str], now: datetime) -> list[str]:
    entry = [f"### {now:%H:%M} - {entry_title}", *lines]
    return [line for line in entry if line.strip() != ""]


def append_under_section(
    section_title: str,
    entry_title: str,
    lines: list[str],
    now: datetime,
    daily_dir: Path = DEFAULT_DAILY_DIR,
) -> Path:
    path = daily_note_path(daily_dir, now)
    entry = _entry_lines(entry_title, lines, now)
    with _locked(Path(daily_dir) / LOCK_FILENAME):
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        doc_lines = existing.splitlines() or [f"# {now:%Y-%m-%d}"]
        updated = _insert_under_section(doc_lines, section_title, entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Obsidian daily note の指定セクションへ追記する"
    )
    parser.add_argument("--section", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--line", action="append", default=[])
    parser.add_argument("--daily-dir", default=str(DEFAULT_DAILY_DIR))
    args = parser.parse_args()
    path = append_under_section(
        args.section, args.title, args.line, datetime.now(), Path(args.daily_dir)
    )
    print(str(path))


if __name__ == "__main__":
    main()
