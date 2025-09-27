import time
import gspread
from google.oauth2.service_account import Credentials

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
		return
	
	def write(self, values):
		"""
		注文番号がすでに記載されている場合はその行を更新、
		ない場合は追記
		"""
		if not values:
			return
		
		# ヘッダー行をスキップして処理
		headers = values[0]
		
		# データ行をバッチで処理
		data_rows = values[1:]
		existing_orders = self.ws.col_values(2)  # B列の全データ
		existing_arrival_dates = self.ws.col_values(6)  # F列（中国事務所到着日）の全データ

		for row_data in data_rows:
			order_id = row_data[1]  # 注文番号（2列目）
			
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
					else:
						print(f"注文番号 {order_id} のF列に既に値があるためスキップしました")
			else:
				# 新しい注文の場合、追記
				self.ws.append_row(row_data)
				print(f"新しい注文番号 {order_id} を追加しました")
		
		return