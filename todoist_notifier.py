from __future__ import annotations

import logging
from typing import Any, Protocol

import requests

logger = logging.getLogger(__name__)

TODOIST_API = "https://api.todoist.com/api/v1"
TIMEOUT_SECONDS = 15
TASK_MARKER = "[到着遅延]"
MAX_NAME_LENGTH = 40
MAX_CONTENT_LENGTH = 150
PRIORITY_HIGH = 3


class TodoistClient(Protocol):
    def list_tasks(self, project_id: str) -> list[dict[str, Any]]: ...
    def create_task(self, payload: dict[str, Any]) -> str: ...
    def update_task(self, task_id: str, payload: dict[str, Any]) -> None: ...


class HttpTodoistClient:
    def __init__(self, api_token: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def list_tasks(self, project_id: str) -> list[dict[str, Any]]:
        response = requests.get(
            f"{TODOIST_API}/tasks",
            headers=self._headers,
            params={"project_id": project_id},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("results", payload) if isinstance(payload, dict) else payload

    def create_task(self, payload: dict[str, Any]) -> str:
        response = requests.post(
            f"{TODOIST_API}/tasks", headers=self._headers, json=payload, timeout=TIMEOUT_SECONDS
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Todoist API error {response.status_code}: {response.text}")
        return str(response.json()["id"])

    def update_task(self, task_id: str, payload: dict[str, Any]) -> None:
        response = requests.post(
            f"{TODOIST_API}/tasks/{task_id}",
            headers=self._headers,
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Todoist API error {response.status_code}: {response.text}")


def _identity(order: dict[str, Any]) -> str:
    """注文番号があればそれ、無ければ商品名で同一性を判断する"""
    order_number = str(order.get("order_number") or "").strip()
    if order_number:
        return order_number
    return str(order.get("product_name") or "").strip()[:MAX_NAME_LENGTH]


def build_task_content(order: dict[str, Any]) -> str:
    name = str(order.get("product_name") or "").strip()[:MAX_NAME_LENGTH]
    order_number = str(order.get("order_number") or "").strip()
    head = f"{TASK_MARKER} {order_number} {name}".replace("  ", " ").strip()
    content = f"{head} {order.get('days_elapsed')}日経過"
    return content[:MAX_CONTENT_LENGTH]


def build_task_description(order: dict[str, Any]) -> str:
    return (
        f"購入日: {order.get('purchase_date')}\n"
        f"経過: {order.get('days_elapsed')}日\n"
        f"商品: {order.get('product_name')}"
    )


def find_existing_task(tasks: list[dict[str, Any]], order: dict[str, Any]) -> dict[str, Any] | None:
    key = _identity(order)
    if not key:
        return None
    for task in tasks:
        content = str(task.get("content") or "")
        if TASK_MARKER in content and key in content:
            return task
    return None


class TodoistNotifier:
    def __init__(self, client: TodoistClient, project_id: str) -> None:
        self._client = client
        self._project_id = project_id

    def notify(self, orders: list[dict[str, Any]]) -> dict[str, int]:
        result = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
        if not orders:
            return result
        try:
            existing = self._client.list_tasks(self._project_id)
        except Exception as e:
            logger.error("Todoist のタスク一覧取得に失敗しました: %s", e)
            return result

        for order in orders:
            try:
                self._notify_one(order, existing, result)
            except Exception as e:
                result["failed"] += 1
                logger.error("Todoist への登録に失敗しました (%s): %s", _identity(order), e)
        logger.info("Todoist: 新規%d件 / 更新%d件 / 変更なし%d件 / 失敗%d件", *result.values())
        return result

    def _notify_one(
        self, order: dict[str, Any], existing: list[dict[str, Any]], result: dict[str, int]
    ) -> None:
        content = build_task_content(order)
        found = find_existing_task(existing, order)
        if found is None:
            self._client.create_task({
                "content": content,
                "description": build_task_description(order),
                "project_id": self._project_id,
                "priority": PRIORITY_HIGH,
            })
            result["created"] += 1
            return
        if str(found.get("content") or "") == content:
            result["skipped"] += 1
            return
        self._client.update_task(str(found["id"]), {
            "content": content,
            "description": build_task_description(order),
        })
        result["updated"] += 1
