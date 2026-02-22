"""指定期間の決算データを一括取得する"""
import sys
import time
from datetime import datetime, timedelta

import fetcher
import history


def daterange(start: str, end: str):
    d = datetime.strptime(start, "%Y%m%d")
    end_d = datetime.strptime(end, "%Y%m%d")
    while d <= end_d:
        if d.weekday() < 5:  # 平日のみ
            yield d.strftime("%Y%m%d")
        d += timedelta(days=1)


def main(start: str, end: str) -> None:
    hist = history.load()
    for date_str in daterange(start, end):
        print(f"[backfill] {date_str} 取得開始")
        disclosures = fetcher.fetch_tdnet_disclosures(date_str)
        print(f"[backfill] {date_str}: 決算短信 {len(disclosures)} 件")
        if not disclosures:
            continue

        seen_codes: set[str] = set()
        for d in disclosures:
            code = d["code"]
            fin = {}
            met = {}
            if code not in seen_codes:
                seen_codes.add(code)
                fin = fetcher.fetch_kabutan_financials(code)
                met = fetcher.fetch_kabutan_metrics(code)
                time.sleep(1)  # 株探へのアクセス間隔（metrics 分）
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
        print(f"[backfill] {date_str}: 保存完了")

    print("[backfill] 全期間の取得完了")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python backfill.py YYYYMMDD YYYYMMDD")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
