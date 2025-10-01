"""
Slack通知モジュール
中国事務所到着日の更新時にSlackへ通知を送信
"""
import os
import json
import logging
from urllib import request, error

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Slack通知クラス"""

    def __init__(self):
        """
        環境変数からSlack Webhook URLを取得
        """
        self.webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            logger.warning("SLACK_WEBHOOK_URLが設定されていません。Slack通知は無効です。")

    def send_arrival_notification(self, order_id, arrival_date):
        """
        中国事務所到着日の更新通知を送信

        Args:
            order_id: 注文番号
            arrival_date: 中国事務所到着日
        """
        if not self.webhook_url:
            logger.info(f"Slack通知がスキップされました（注文番号: {order_id}）")
            return

        try:
            message = {
                "text": f"🚚 *中国事務所到着通知*",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🚚 中国事務所到着通知",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*注文番号:*\n{order_id}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*到着日:*\n{arrival_date}"
                            }
                        ]
                    }
                ]
            }

            # Webhook URLにPOSTリクエストを送信
            data = json.dumps(message).encode('utf-8')
            req = request.Request(
                self.webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )

            with request.urlopen(req) as response:
                if response.status == 200:
                    logger.info(f"Slack通知を送信しました（注文番号: {order_id}）")
                else:
                    logger.error(f"Slack通知の送信に失敗しました（ステータス: {response.status}）")

        except error.URLError as e:
            logger.error(f"Slack通知の送信エラー: {e}")
        except Exception as e:
            logger.error(f"Slack通知の送信エラー: {e}")
