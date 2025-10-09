"""Google Sheetsへのデータ書き込みモジュール"""
import os
import logging
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from slack_notifier import SlackNotifier

# ログ設定
logger = logging.getLogger(__name__)

# 定数
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# 列のインデックス定数
COL_ORDER_ID = 1  # B列（注文番号）
COL_ARRIVAL_DATE = 5  # F列（中国事務所到着日）

# デフォルト値
DEFAULT_NUM_COLS = 26  # デフォルトは26列（A-Z）


class GSheet:
    """Google Sheetsへのデータ書き込みクラス"""
    
    def __init__(self, credentials_file=None, spreadsheet_id=None, worksheet_name=None):
        """
        初期化
        
        Args:
            credentials_file: サービスアカウントの認証情報ファイルパス
            spreadsheet_id: スプレッドシートID
            worksheet_name: ワークシート名
        """
        # 環境変数またはデフォルト値から設定を読み込み
        self.credentials_file = credentials_file or os.environ.get(
            "GOOGLE_SHEETS_CREDENTIALS_JSON", "service_account.json"
        )
        self.spreadsheet_id = spreadsheet_id or os.environ.get(
            "GOOGLE_SHEETS_SPREADSHEET_ID", "1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls"
        )
        self.worksheet_name = worksheet_name or os.environ.get(
            "GOOGLE_SHEETS_WORKSHEET", "yiwu"
        )
        
        if not self.spreadsheet_id:
            raise RuntimeError("環境変数 GOOGLE_SHEETS_SPREADSHEET_ID を設定してください")
        
        # 認証情報の設定
        creds = Credentials.from_service_account_file(self.credentials_file, scopes=SCOPES)
        
        # gspreadクライアントの初期化
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(self.spreadsheet_id)
        self.ws = sh.worksheet(self.worksheet_name)
        
        # Google Sheets API v4サービスの初期化（テーブル操作用）
        self.service = build('sheets', 'v4', credentials=creds)
        self.sheet_id = self.ws.id
        
        # Slack通知の初期化
        self.slack_notifier = SlackNotifier()
    
    def get_table_id(self):
        """
        ワークシート内の最初のテーブルのIDを取得
        
        Returns:
            テーブルID（存在しない場合はNone）
        """
        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id,
                includeGridData=False
            ).execute()
            
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['sheetId'] == self.sheet_id:
                    # dataSourceTableオブジェクトを探す
                    for data_source in sheet.get('dataSource', []):
                        if 'dataSourceTableId' in data_source:
                            return data_source['dataSourceTableId']
                    # 通常のテーブルを探す
                    for table in sheet.get('tables', []):
                        return table.get('tableId')
            return None
        except Exception as e:
            logger.error(f"テーブルID取得エラー: {e}")
            return None
    
    def _get_num_cols(self):
        """
        現在のシートの列数を取得
        
        Returns:
            列数（取得できない場合はデフォルト値）
        """
        try:
            all_values = self.ws.get_all_values()
            if all_values:
                return len(all_values[0])
        except Exception as e:
            logger.warning(f"列数取得エラー: {e}")
        return DEFAULT_NUM_COLS
    
    def update_table_range(self, last_row):
        """
        テーブル範囲を指定された最終行まで拡張
        
        Args:
            last_row: 拡張する最終行番号（1から始まる）
        """
        table_id = self.get_table_id()
        if not table_id:
            logger.info("テーブルが見つかりません。テーブル範囲の拡張をスキップします。")
            return
        
        try:
            num_cols = self._get_num_cols()
            
            # updateTableリクエストを作成
            requests = [{
                'updateTable': {
                    'table': {
                        'tableId': table_id,
                        'range': {
                            'sheetId': self.sheet_id,
                            'startRowIndex': 0,
                            'endRowIndex': last_row,
                            'startColumnIndex': 0,
                            'endColumnIndex': num_cols
                        }
                    },
                    'fields': 'range'
                }
            }]
            
            # batchUpdateを実行
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            logger.info(f"テーブル範囲を{last_row}行目まで拡張しました")
        except Exception as e:
            logger.error(f"テーブル範囲拡張エラー: {e}")
    
    def _should_update_row(self, row_index, existing_arrival_dates):
        """
        行を更新すべきかチェック
        
        Args:
            row_index: 行インデックス（1から始まる）
            existing_arrival_dates: 既存の到着日リスト
            
        Returns:
            更新すべき場合True、そうでない場合False
        """
        if row_index > len(existing_arrival_dates):
            return True
        
        arrival_date = existing_arrival_dates[row_index - 1] if existing_arrival_dates[row_index - 1] else ""
        return not arrival_date.strip()
    
    def _update_existing_order(self, row_index, row_data, order_id, new_arrival_date):
        """
        既存の注文を更新
        
        Args:
            row_index: 行インデックス（1から始まる）
            row_data: 更新するデータ
            order_id: 注文番号
            new_arrival_date: 新しい到着日
        """
        end_col = len(row_data)
        range_name = f"A{row_index}:{chr(64 + end_col)}{row_index}"
        self.ws.update(range_name, [row_data])
        logger.info(f"注文番号 {order_id} のF列が空のため更新しました")
        
        # F列が空から値ありに変更された場合、Slack通知を送信
        if new_arrival_date and new_arrival_date.strip():
            self.slack_notifier.send_arrival_notification(order_id, new_arrival_date)
    
    def _add_new_order(self, row_data, order_id, new_arrival_date):
        """
        新しい注文を追加
        
        Args:
            row_data: 追加するデータ
            order_id: 注文番号
            new_arrival_date: 到着日
        """
        self.ws.append_row(row_data)
        logger.info(f"新しい注文番号 {order_id} を追加しました")
        
        # 新規追加時にF列に値がある場合もSlack通知を送信
        if new_arrival_date and new_arrival_date.strip():
            self.slack_notifier.send_arrival_notification(order_id, new_arrival_date)
    
    def write(self, values):
        """
        注文番号がすでに記載されている場合はその行を更新、
        ない場合は追記
        書き込み後、テーブル範囲を自動的に拡張
        
        Args:
            values: 書き込むデータ（ヘッダー行を含む）
        """
        if not values:
            logger.warning("書き込むデータがありません")
            return
        
        # データ行をバッチで処理
        data_rows = values[1:]
        existing_orders = self.ws.col_values(COL_ORDER_ID + 1)  # B列の全データ
        existing_arrival_dates = self.ws.col_values(COL_ARRIVAL_DATE + 1)  # F列の全データ
        
        max_row = len(existing_orders)  # 現在の最大行を記録
        
        for row_data in data_rows:
            order_id = row_data[COL_ORDER_ID]  # 注文番号
            new_arrival_date = row_data[COL_ARRIVAL_DATE] if len(row_data) > COL_ARRIVAL_DATE else ""
            
            if order_id in existing_orders:
                # 既存の注文番号がある場合
                row_index = existing_orders.index(order_id) + 1
                
                # F列（中国事務所到着日）が空の場合のみ更新
                if self._should_update_row(row_index, existing_arrival_dates):
                    self._update_existing_order(row_index, row_data, order_id, new_arrival_date)
                else:
                    logger.info(f"注文番号 {order_id} のF列に既に値があるためスキップしました")
            else:
                # 新しい注文の場合、追記
                self._add_new_order(row_data, order_id, new_arrival_date)
                max_row += 1  # 新規行が追加されたので行数を増やす
        
        # データ書き込み後、テーブル範囲を拡張
        if max_row > 0:
            self.update_table_range(max_row)
