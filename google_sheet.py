import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from slack_notifier import SlackNotifier

# Google Sheets に書き出し
SHEET_CREDENTIALS =  "service_account.json"
SPREADSHEET_ID = "1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls"
WORKSHEET_NAME = "yiwu"



if not SPREADSHEET_ID:
	raise RuntimeError("環境変数 GOOGLE_SHEETS_SPREADSHEET_ID を設定してください")

scopes = [
"https://www.googleapis.com/auth/spreadsheets",
"https://www.googleapis.com/auth/drive.readonly",
]

class GSheet:
	def __init__(self):
		"""
		"""
		creds = Credentials.from_service_account_file(SHEET_CREDENTIALS, scopes=scopes)
		gc = gspread.authorize(creds)
		sh = gc.open_by_key(SPREADSHEET_ID)
		self.ws = sh.worksheet(WORKSHEET_NAME)

		# Google Sheets API v4サービスの初期化（テーブル操作用）
		self.service = build('sheets', 'v4', credentials=creds)
		self.spreadsheet_id = SPREADSHEET_ID
		self.sheet_id = self.ws.id

		# Slack通知の初期化
		self.slack_notifier = SlackNotifier()
		return

	def get_table_id(self):
		"""
		ワークシート内の最初のテーブルのIDを取得
		テーブルが存在しない場合はNoneを返す
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
			print(f"テーブルID取得エラー: {e}")
			return None

	def update_table_range(self, last_row):
		"""
		テーブル範囲を指定された最終行まで拡張

		Args:
			last_row: 拡張する最終行番号（1から始まる）
		"""
		table_id = self.get_table_id()
		if not table_id:
			print("テーブルが見つかりません。テーブル範囲の拡張をスキップします。")
			return

		try:
			# 現在の列数を取得
			all_values = self.ws.get_all_values()
			if not all_values:
				return

			num_cols = len(all_values[0]) if all_values else 26  # デフォルトは26列（A-Z）

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

			print(f"テーブル範囲を{last_row}行目まで拡張しました")
		except Exception as e:
			print(f"テーブル範囲拡張エラー: {e}")

	def write(self, values):
		"""
		注文番号がすでに記載されている場合はその行を更新、
		ない場合は追記
		書き込み後、テーブル範囲を自動的に拡張
		"""
		if not values:
			return

		# データ行をバッチで処理
		data_rows = values[1:]
		existing_orders = self.ws.col_values(2)  # B列の全データ
		existing_arrival_dates = self.ws.col_values(6)  # F列（中国事務所到着日）の全データ

		max_row = len(existing_orders)  # 現在の最大行を記録

		for row_data in data_rows:
			order_id = row_data[1]  # 注文番号（2列目）
			new_arrival_date = row_data[5] if len(row_data) > 5 else ""  # F列（中国事務所到着日）

			if order_id in existing_orders:
				# 既存の注文番号がある場合
				row_index = existing_orders.index(order_id) + 1

				# F列（中国事務所到着日）が空の場合のみ更新
				if row_index <= len(existing_arrival_dates):
					arrival_date = existing_arrival_dates[row_index - 1] if existing_arrival_dates[row_index - 1] else ""
					if not arrival_date.strip():  # F列が空の場合
						end_col = len(row_data)
						range_name = f"A{row_index}:{chr(64+end_col)}{row_index}"
						self.ws.update(range_name, [row_data])
						print(f"注文番号 {order_id} のF列が空のため更新しました")

						# F列が空から値ありに変更された場合、Slack通知を送信
						if new_arrival_date and new_arrival_date.strip():
							self.slack_notifier.send_arrival_notification(order_id, new_arrival_date)
					else:
						print(f"注文番号 {order_id} のF列に既に値があるためスキップしました")
			else:
				# 新しい注文の場合、追記
				self.ws.append_row(row_data)
				print(f"新しい注文番号 {order_id} を追加しました")
				max_row += 1  # 新規行が追加されたので行数を増やす

				# 新規追加時にF列に値がある場合もSlack通知を送信
				if new_arrival_date and new_arrival_date.strip():
					self.slack_notifier.send_arrival_notification(order_id, new_arrival_date)

		# データ書き込み後、テーブル範囲を拡張
		if max_row > 0:
			self.update_table_range(max_row)

		return