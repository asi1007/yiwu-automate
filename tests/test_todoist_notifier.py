from __future__ import annotations

import pytest

from todoist_notifier import (
    TASK_MARKER,
    TodoistNotifier,
    build_task_content,
    build_task_description,
    find_existing_task,
)


ORDER = {
    "order_number": "Y0806-260729002",
    "product_name": "[ｂｅｎｒｉｉ] パスポートケース クリアカバー 防水 軽量 薄型",
    "purchase_date": "07-29",
    "days_elapsed": 42,
}


class TestBuildTaskContent:
    def test_注文番号と経過日数を入れる(self) -> None:
        content = build_task_content(ORDER)
        assert "Y0806-260729002" in content
        assert "42日" in content

    def test_識別用のマーカーを含める(self) -> None:
        assert TASK_MARKER in build_task_content(ORDER)

    def test_商品名が長くても切り詰める(self) -> None:
        order = dict(ORDER, product_name="あ" * 200)
        assert len(build_task_content(order)) < 160

    def test_注文番号が空でも商品名で識別できる(self) -> None:
        content = build_task_content(dict(ORDER, order_number=""))
        assert TASK_MARKER in content
        assert "パスポートケース" in content


class TestBuildTaskDescription:
    def test_購入日と経過日数を書く(self) -> None:
        description = build_task_description(ORDER)
        assert "07-29" in description and "42" in description


class TestFindExistingTask:
    def test_同じ注文番号の未完了タスクを見つける(self) -> None:
        tasks = [
            {"id": "1", "content": "[到着遅延] Y0806-260729002 ほか 30日経過"},
            {"id": "2", "content": "無関係なタスク"},
        ]
        assert find_existing_task(tasks, ORDER)["id"] == "1"

    def test_無ければNone(self) -> None:
        assert find_existing_task([{"id": "9", "content": "別件"}], ORDER) is None

    def test_マーカーだけ一致しても注文番号が違えば別タスク(self) -> None:
        tasks = [{"id": "1", "content": "[到着遅延] Y0806-999999999 10日経過"}]
        assert find_existing_task(tasks, ORDER) is None

    def test_注文番号が空なら商品名で照合する(self) -> None:
        order = dict(ORDER, order_number="")
        # 前回の実行で作られたタスク（経過日数だけが違う）
        previous = build_task_content(dict(order, days_elapsed=10))
        tasks = [{"id": "5", "content": previous}]
        assert find_existing_task(tasks, order)["id"] == "5"


class _FakeClient:
    def __init__(self, existing: list[dict] | None = None) -> None:
        self.existing = existing or []
        self.created: list[dict] = []
        self.updated: list[tuple[str, dict]] = []

    def list_tasks(self, project_id: str) -> list[dict]:
        return self.existing

    def create_task(self, payload: dict) -> str:
        self.created.append(payload)
        return "new-id"

    def update_task(self, task_id: str, payload: dict) -> None:
        self.updated.append((task_id, payload))


class TestTodoistNotifier:
    def test_新規なら作成する(self) -> None:
        client = _FakeClient()
        notifier = TodoistNotifier(client=client, project_id="P1")
        notifier.notify([ORDER])
        assert len(client.created) == 1
        assert client.created[0]["project_id"] == "P1"
        assert not client.updated

    def test_既存があれば作らず経過日数を更新する(self) -> None:
        client = _FakeClient([{"id": "1", "content": "[到着遅延] Y0806-260729002 30日経過"}])
        notifier = TodoistNotifier(client=client, project_id="P1")
        notifier.notify([ORDER])
        assert not client.created
        assert client.updated[0][0] == "1"
        assert "42日" in client.updated[0][1]["content"]

    def test_内容が変わっていなければ更新もしない(self) -> None:
        client = _FakeClient([{"id": "1", "content": build_task_content(ORDER)}])
        TodoistNotifier(client=client, project_id="P1").notify([ORDER])
        assert not client.created and not client.updated

    def test_対象が空なら何もしない(self) -> None:
        client = _FakeClient()
        TodoistNotifier(client=client, project_id="P1").notify([])
        assert not client.created and not client.updated

    def test_1件失敗しても残りを処理する(self) -> None:
        class _Boom(_FakeClient):
            def create_task(self, payload: dict) -> str:
                if "壊れる" in payload["content"]:
                    raise RuntimeError("boom")
                return super().create_task(payload)

        client = _Boom()
        orders = [dict(ORDER, product_name="壊れる", order_number="X1"), dict(ORDER, order_number="X2")]
        TodoistNotifier(client=client, project_id="P1").notify(orders)
        assert len(client.created) == 1
