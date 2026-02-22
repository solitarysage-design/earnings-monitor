import os

# Slack
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# TDnet
TDNET_BASE_URL = "https://www.release.tdnet.info/inbs"

# 株探
KABUTAN_FINANCE_URL = "https://kabutan.jp/stock/finance?code={code}"

# Data
HISTORY_FILE = "data/history.json"

# 取得対象キーワード（決算短信）
EARNINGS_KEYWORDS = [
    "決算短信",
    "四半期決算短信",
]
