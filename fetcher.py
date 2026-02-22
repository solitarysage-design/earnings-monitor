"""TDnet から決算短信を取得し、株探から財務数値をスクレイピングする"""
import re
import time

import requests
from bs4 import BeautifulSoup

from config import EARNINGS_KEYWORDS, KABUTAN_FINANCE_URL, KABUTAN_STOCK_URL

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EarningsMonitor/1.0; +https://github.com)"}

# やのしん TDnet 非公式 API（JSON形式で適時開示一覧を取得できる）
YANOSHIN_API = "https://webapi.yanoshin.jp/webapi/tdnet/list/{date}-{date}.json"  # date: YYYYMMDD


# ── TDnet (やのしんAPI) ───────────────────────────────────────────────────────

def fetch_tdnet_disclosures(date_str: str) -> list[dict]:
    """date_str: YYYYMMDD 形式。当日の決算短信一覧を返す。"""
    # API は YYYYMMDD 形式
    url = YANOSHIN_API.format(date=date_str)
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, params={"limit": 10000}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        for item in items:
            t = item.get("Tdnet", {})
            title = t.get("title", "")
            if not any(kw in title for kw in EARNINGS_KEYWORDS):
                continue
            raw_code = t.get("company_code", "")
            # 証券コード: 末尾の市場区分文字('0'など)を除いた4桁部分
            code = re.sub(r"[^0-9A-Z]", "", raw_code)[:4]
            pubdate = t.get("pubdate", "")
            time_val = pubdate[11:16] if len(pubdate) >= 16 else ""
            results.append(
                {
                    "time": time_val,
                    "code": code,
                    "name": t.get("company_name", ""),
                    "doc_type": title,
                    "url": t.get("document_url", ""),
                    "date": date_str,
                }
            )
    except Exception as exc:
        print(f"[TDnet] error: {exc}")
    return results


# ── 株探 ─────────────────────────────────────────────────────────────────────

def _parse_num(text: str) -> float | None:
    """'1,234', '▲123', '-', '―' などを float (百万円) に変換する。"""
    text = text.replace(",", "").replace("▲", "-").strip()
    if text in ("", "-", "―", "－", "--"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _yoy(current: float | None, prev: float | None) -> float | None:
    if current is None or prev is None or prev == 0:
        return None
    return round((current - prev) / abs(prev) * 100, 1)


def _parse_market_cap(text: str) -> float | None:
    """時価総額を億円単位に変換: '57兆4,148億円' → 574148.0"""
    text = text.replace(",", "").strip()
    try:
        if "兆" in text:
            parts = text.split("兆")
            cho = float(parts[0])
            oku = float(parts[1].replace("億円", "").replace("億", "") or 0)
            return cho * 10000 + oku
        elif "億" in text:
            return float(text.replace("億円", "").replace("億", ""))
        elif "百万円" in text:
            return round(float(text.replace("百万円", "")) / 100, 1)
    except (ValueError, IndexError):
        pass
    return None


def _parse_rate(text: str) -> float | None:
    """'13.3倍', '2.61％' などを float に変換する。"""
    text = re.sub(r"[倍％%]", "", text).strip()
    try:
        return float(text)
    except ValueError:
        return None


def fetch_kabutan_metrics(code: str) -> dict:
    """株探のメインページから時価総額・PER・PBR・配当利回りを取得する。"""
    url = KABUTAN_STOCK_URL.format(code=code)
    result = {"market_cap": None, "per": None, "pbr": None, "dividend_yield": None}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        LABEL_MAP = {
            "時価総額": ("market_cap", _parse_market_cap),
            "PER":     ("per",         _parse_rate),
            "PBR":     ("pbr",         _parse_rate),
            "利回り":  ("dividend_yield", _parse_rate),
        }
        for el in soup.find_all(["span", "dt", "th", "td"]):
            label = el.get_text(strip=True)
            if label in LABEL_MAP:
                field, parser = LABEL_MAP[label]
                if result[field] is not None:
                    continue  # すでに取得済み
                nxt = el.find_next_sibling(["span", "dd", "td"])
                if nxt:
                    result[field] = parser(nxt.get_text(strip=True))
    except Exception as exc:
        print(f"[株探metrics] code={code} error: {exc}")
    return result


def fetch_kabutan_financials(code: str) -> dict:
    """
    株探の財務ページから直近2期分の売上高・営業利益・経常利益・純利益を取得し、
    前年同期比を計算して返す。
    """
    url = KABUTAN_FINANCE_URL.format(code=code)
    result = {
        "revenue": None, "revenue_yoy": None,
        "operating_profit": None, "operating_profit_yoy": None,
        "ordinary_profit": None, "ordinary_profit_yoy": None,
        "net_profit": None, "net_profit_yoy": None,
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 株探の財務テーブルを探す
        table = soup.find("table", id="finance_table") or soup.find("table", class_="stock_finance_table")
        if table is None:
            for t in soup.find_all("table"):
                if t.find(string=re.compile("売上高|営業収益")):
                    table = t
                    break

        if table is None:
            print(f"[株探] code={code}: テーブルが見つかりません")
            return result

        FIELD_MAP = {
            "売上高": "revenue",
            "営業収益": "revenue",
            "営業利益": "operating_profit",
            "経常利益": "ordinary_profit",
            "純利益": "net_profit",
            "当期純利益": "net_profit",
            "当期利益": "net_profit",
        }

        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if not cells:
                continue
            label = cells[0].get_text(strip=True)
            field = next((v for k, v in FIELD_MAP.items() if k in label), None)
            if field is None:
                continue
            nums = [_parse_num(c.get_text(strip=True)) for c in cells[1:]]
            if len(nums) >= 2:
                result[field] = nums[0]
                result[f"{field}_yoy"] = _yoy(nums[0], nums[1])
            elif len(nums) == 1:
                result[field] = nums[0]
        time.sleep(1)  # 株探へのアクセス間隔
    except Exception as exc:
        print(f"[株探] code={code} error: {exc}")
    return result
