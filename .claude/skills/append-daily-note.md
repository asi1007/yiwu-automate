---
name: append-daily-note
description: /append-daily-note コマンド - Obsidian daily note の指定セクション見出しの下へ内容を追記する（実行本体は write_daily_note.py）
user_invocable: true
---

# daily note 追記コマンド

Obsidian daily note（`daily/YYYY-MM-DD.md`）の指定セクション見出しの下へ、タイトル付きエントリを追記する。

このスキルは **入口（正規の使い方の定義）** であり、実際の書き込みは python 実行本体 `write_daily_note.py` が行う。同じ本体を毎朝6時の自動実行（yiwu_scraper）からも import して再利用する。

## 実行手順

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/automate-yiwu
python write_daily_note.py \
  --section "## Claude Code ログ" \
  --title "エントリのタイトル" \
  --line "- 1行目" \
  --line "- 2行目"
```

## 引数

- `--section`：追記先のセクション見出し（例 `## Claude Code ログ`）。無ければ新規作成する
- `--title`：エントリ見出し。`### HH:MM - <title>` として追記される（時刻は実行時刻）
- `--line`：本文の行。複数指定可（順序どおり）
- `--daily-dir`：daily ディレクトリ（省略時は `~/Documents/automation/obsidian/main/daily`）

## 処理内容

1. 実行日の `daily/YYYY-MM-DD.md` を解決（無ければ `# YYYY-MM-DD` 見出し付きで新規作成）
2. `--section` の見出しが無ければファイル末尾に追加
3. セクションの範囲内（次の `## ` 見出しの直前、または末尾）へ `### HH:MM - <title>` と本文行を追記

## 注意事項

- コア関数は `write_daily_note.append_under_section(section_title, entry_title, lines, now, daily_dir)`。python から直接呼べる
- Vault は Google Drive 同期フォルダのシンボリックリンク（`~/Documents/automation/obsidian`）。未マウント時は書き込み失敗しうるため、自動実行側は例外を握って本処理を止めない
