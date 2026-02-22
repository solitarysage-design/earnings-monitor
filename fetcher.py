"""TDnet から決算短信を取得し、株探から財務数値をスクレイピングする"""
import re
import time

import requests
from bs4 import BeautifulSoup

from config import EARNINGS_KEYWORDS, KABUTAN_FINANCE_URL, TDNET_BASE_URL

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EarningsMonitor/1.0; +https://github.com)"}


# ── TDnet ───────────────────────────────────────────────────────────────────

def fetch_tdnet_disclosures(date_str: str) -> list[dict]:
    """date_str: YYYYMMDD 形式。当日の決算短信一覧を返す。"""
    results = []
    for page in range(1, 20):
        url = f"{TDNET_BASE_URL}/I_list_{page:03d}_{date_str}.html"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                break
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("table.comn-table tbody tr")
            if not rows:
                # ページが存在しない or データなし
                break
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 5:
                    continue
                time_val = cols[0].get_text(strip=True)
                code = cols[1].get_text(strip=True)
                name = cols[2].get_text(strip=True)
                doc_type = cols[3].get_text(strip=True)
                link_tag = cols[4].find("a") if len(cols) > 4 else None
                doc_url = ""
                if link_tag and link_tag.get("href"):
                    href = link_tag["href"]
                    doc_url = href if href.startswith("http") else f"https://www.release.tdnet.info{href}"

                if any(kw in doc_type for kw in EARNINGS_KEYWORDS):
                    results.append(
                        {
                            "time": time_val,
                            "code": code,
                            "name": name,
                            "doc_type": doc_type,
                            "url": doc_url,
                            "date": date_str,
                        }
                    )
            time.sleep(0.5)
        except Exception as exc:
            print(f"[TDnet] page={page} error: {exc}")
            break
    return results


# ── 株探 ─────────────────────────────────────────────────────────────────────

def _parse_num(text: str) -> float | None:
    """'1,234', '-', '―' などを float (百万円) に変換する。"""
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

        # 株探の財務テーブル: id="finance_table" または class="stock_finance_table"
        table = soup.find("table", id="finance_table") or soup.find("table", class_="stock_finance_table")
        if table is None:
            # フォールバック: テーブルを全探索
            for t in soup.find_all("table"):
                if t.find(string=re.compile("売上高|営業収益")):
                    table = t
                    break

        if table is None:
            print(f"[株探] code={code}: table not found")
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

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["th", "td"])
            if not cells:
                continue
            label = cells[0].get_text(strip=True)
            field = next((v for k, v in FIELD_MAP.items() if k in label), None)
            if field is None:
                continue
            # 数値セルを左から「最新期」「前期」の順で取得
            nums = [_parse_num(c.get_text(strip=True)) for c in cells[1:]]
            nums = [n for n in nums]  # None も保持
            if len(nums) >= 2:
                current, prev = nums[0], nums[1]
                result[field] = current
                result[f"{field}_yoy"] = _yoy(current, prev)
            elif len(nums) == 1:
                result[field] = nums[0]
    except Exception as exc:
        print(f"[株探] code={code} error: {exc}")
    return result
