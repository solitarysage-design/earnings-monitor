#!/usr/bin/env python3
"""メインエントリポイント: TDnet 取得 → 株探スクレイピング → Slack 通知 → history.json 更新"""
import sys
from datetime import datetime, timezone, timedelta

import fetcher
import history
import notifier

JST = timezone(timedelta(hours=9))


def main(date_str: str | None = None) -> None:
    if date_str is None:
        date_str = datetime.now(JST).strftime("%Y%m%d")
    print(f"[run] 対象日: {date_str}")

    # 1. TDnet から決算短信一覧を取得
    disclosures = fetcher.fetch_tdnet_disclosures(date_str)
    print(f"[run] 決算短信: {len(disclosures)} 件")

    # 2. 株探から財務数値・バリュエーション指標を取得
    financials_map: dict[str, dict] = {}
    metrics_map: dict[str, dict] = {}
    for d in disclosures:
        code = d["code"]
        if code not in financials_map:
            print(f"[run] 株探取得: {code} {d['name']}")
            financials_map[code] = fetcher.fetch_kabutan_financials(code)
            metrics_map[code] = fetcher.fetch_kabutan_metrics(code)

    # 3. Slack 通知
    notifier.send(disclosures, financials_map)

    # 4. history.json に蓄積
    hist = history.load()
    for d in disclosures:
        code = d["code"]
        fin = financials_map.get(code, {})
        met = metrics_map.get(code, {})
        record = {
            "date": date_str,
            "time": d["time"],
            "doc_type": d["doc_type"],
            "url": d["url"],
            **fin,
            **met,
        }
        hist = history.add_record(hist, code, d["name"], record)
    history.save(hist)
    print("[run] history.json 更新完了")


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(date_arg)
