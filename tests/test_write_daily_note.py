from datetime import datetime
from pathlib import Path


NOW = datetime(2026, 7, 28, 9, 5, 0)
SECTION = "## Claude Code ログ"


class TestAppendUnderSection:
    def test_creates_file_with_heading_when_absent(self, tmp_path: Path):
        from write_daily_note import append_under_section

        path = append_under_section(
            SECTION, "到着遅延アラート (2件)",
            ["- Y0806-001 商品A 購入 02-26（152日経過・未到着）"],
            NOW, tmp_path,
        )
        text = path.read_text(encoding="utf-8")
        assert path.name == "2026-07-28.md"
        assert "# 2026-07-28" in text
        assert SECTION in text
        assert "### 09:05 - 到着遅延アラート (2件)" in text
        assert "- Y0806-001 商品A 購入 02-26（152日経過・未到着）" in text

    def test_appends_section_when_missing(self, tmp_path: Path):
        from write_daily_note import append_under_section

        p = tmp_path / "2026-07-28.md"
        p.write_text("# 2026-07-28\n\n## 別セクション\n- 既存\n", encoding="utf-8")
        append_under_section(SECTION, "到着遅延アラート (1件)", ["- x"], NOW, tmp_path)
        text = p.read_text(encoding="utf-8")
        assert "## 別セクション" in text
        assert "- 既存" in text
        assert SECTION in text
        assert "### 09:05 - 到着遅延アラート (1件)" in text

    def test_appends_entry_under_existing_section(self, tmp_path: Path):
        from write_daily_note import append_under_section

        p = tmp_path / "2026-07-28.md"
        p.write_text(
            "# 2026-07-28\n\n## Claude Code ログ\n\n### 08:00 - 既存作業\n- 既存結果\n",
            encoding="utf-8",
        )
        append_under_section(SECTION, "到着遅延アラート (1件)", ["- y"], NOW, tmp_path)
        text = p.read_text(encoding="utf-8")
        assert "### 08:00 - 既存作業" in text
        assert "- 既存結果" in text
        assert "### 09:05 - 到着遅延アラート (1件)" in text
        # 既存エントリが新エントリより前にある
        assert text.index("08:00") < text.index("09:05")

    def test_appended_entry_has_no_blank_lines(self, tmp_path: Path):
        from write_daily_note import append_under_section

        path = append_under_section(
            SECTION, "アラート", ["- b", "   ", "", "- c"], NOW, tmp_path
        )
        text = path.read_text(encoding="utf-8")
        entry = text[text.index("### 09:05 - アラート") :]
        assert entry.splitlines() == ["### 09:05 - アラート", "- b", "- c"]

    def test_preserves_existing_blank_lines_written_by_others(self, tmp_path: Path):
        from write_daily_note import append_under_section

        p = tmp_path / "2026-07-28.md"
        original = "# 2026-07-28\n\n## Claude Code ログ\n\n### 08:00 - 既存\n- a\n\n## 他人のセクション\n\n- 人間が書いた行\n"
        p.write_text(original, encoding="utf-8")
        append_under_section(SECTION, "アラート", ["- b"], NOW, tmp_path)
        text = p.read_text(encoding="utf-8")
        assert "# 2026-07-28\n\n## Claude Code ログ\n" in text
        assert "## 他人のセクション\n\n- 人間が書いた行\n" in text
        assert text.count("\n\n") == original.count("\n\n")

    def test_inserts_within_section_before_following_section(self, tmp_path: Path):
        from write_daily_note import append_under_section

        p = tmp_path / "2026-07-28.md"
        p.write_text(
            "# 2026-07-28\n\n## Claude Code ログ\n- 旧\n\n## あとのセクション\n- z\n",
            encoding="utf-8",
        )
        append_under_section(SECTION, "到着遅延アラート", ["- new"], NOW, tmp_path)
        text = p.read_text(encoding="utf-8")
        # 新エントリは Claude Code ログ 内（あとのセクションより前）に入る
        assert text.index("- new") < text.index("## あとのセクション")
        assert text.index("- 旧") < text.index("- new")


class TestDefaultDailyDir:
    def test_points_to_main_daily(self):
        from write_daily_note import DEFAULT_DAILY_DIR

        assert DEFAULT_DAILY_DIR.parts[-3:] == ("obsidian", "main", "daily")


class TestLocking:
    def test_uses_shared_lock_file_in_daily_dir(self, tmp_path: Path):
        from write_daily_note import LOCK_FILENAME, append_under_section

        append_under_section(SECTION, "アラート", ["- b"], NOW, tmp_path)
        assert (tmp_path / LOCK_FILENAME).exists()
        assert LOCK_FILENAME == ".daily_note.lock"

    def test_concurrent_appends_do_not_lose_entries(self, tmp_path: Path):
        from concurrent.futures import ThreadPoolExecutor

        from write_daily_note import append_under_section

        def run(minute: int) -> None:
            append_under_section(
                SECTION, f"アラート{minute}", [f"- {minute}"], NOW.replace(minute=minute), tmp_path
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(run, range(8)))

        text = (tmp_path / "2026-07-28.md").read_text(encoding="utf-8")
        assert all(f"アラート{minute}" in text for minute in range(8))

    def test_holds_lock_across_read_and_write(self, tmp_path: Path):
        import fcntl

        import write_daily_note

        observed: list[bool] = []
        original = write_daily_note._insert_under_section

        def spy(doc_lines: list[str], section_title: str, entry: list[str]) -> list[str]:
            with (tmp_path / write_daily_note.LOCK_FILENAME).open("r") as probe:
                try:
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    observed.append(False)
                    fcntl.flock(probe, fcntl.LOCK_UN)
                except BlockingIOError:
                    observed.append(True)
            return original(doc_lines, section_title, entry)

        write_daily_note._insert_under_section = spy
        try:
            write_daily_note.append_under_section(SECTION, "アラート", ["- b"], NOW, tmp_path)
        finally:
            write_daily_note._insert_under_section = original

        assert observed == [True]
