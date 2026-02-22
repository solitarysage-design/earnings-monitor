"""history.json の読み書きを担当する"""
import json
import os

from config import HISTORY_FILE


def load() -> dict:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save(data: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_record(history: dict, code: str, name: str, record: dict) -> dict:
    """code ごとにレコードを追加（同日重複はスキップ）。"""
    entry = history.setdefault(code, {"name": name, "records": []})
    existing_dates = {r["date"] for r in entry["records"]}
    if record["date"] not in existing_dates:
        entry["records"].append(record)
        entry["records"].sort(key=lambda r: r["date"])
    return history
