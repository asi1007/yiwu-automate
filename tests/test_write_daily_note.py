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

    def test_output_has_no_blank_lines(self, tmp_path: Path):
        from write_daily_note import append_under_section

        p = tmp_path / "2026-07-28.md"
        p.write_text(
            "# 2026-07-28\n\n## Claude Code ログ\n\n### 08:00 - 既存\n- a\n\n",
            encoding="utf-8",
        )
        path = append_under_section(SECTION, "アラート", ["- b"], NOW, tmp_path)
        lines = path.read_text(encoding="utf-8").split("\n")
        # 末尾の改行由来の空要素を除き、空白行が1つも無い
        assert [l for l in lines if l.strip() == "" and l != ""] == []
        assert "" not in [l for l in lines[:-1]]

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
