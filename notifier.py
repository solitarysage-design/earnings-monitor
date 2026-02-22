"""Slack への通知を担当する"""
import json

import requests

from config import SLACK_WEBHOOK_URL


def _fmt(val, suffix="百万円") -> str:
    if val is None:
        return "N/A"
    return f"{val:,.0f}{suffix}"


def _fmt_yoy(yoy) -> str:
    if yoy is None:
        return "N/A"
    sign = "+" if yoy >= 0 else ""
    return f"{sign}{yoy:.1f}%"


def send(disclosures: list[dict], financials_map: dict[str, dict]) -> None:
    """
    disclosures: fetch_tdnet_disclosures() の結果
    financials_map: {code: fetch_kabutan_financials() の結果}
    """
    if not SLACK_WEBHOOK_URL:
        print("[Slack] SLACK_WEBHOOK_URL が設定されていません。スキップします。")
        return
    if not disclosures:
        _post({"text": "本日 (JST) の決算短信は0件でした。"})
        return

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📊 本日の決算短信 ({len(disclosures)} 件)", "emoji": True},
        }
    ]

    for d in disclosures:
        code = d["code"]
        fin = financials_map.get(code, {})
        text_lines = [
            f"*<{d['url']}|{d['name']} ({code})>*  `{d['doc_type']}`",
            f"売上高: {_fmt(fin.get('revenue'))}  前年比: {_fmt_yoy(fin.get('revenue_yoy'))}",
            f"営業利益: {_fmt(fin.get('operating_profit'))}  前年比: {_fmt_yoy(fin.get('operating_profit_yoy'))}",
            f"経常利益: {_fmt(fin.get('ordinary_profit'))}  前年比: {_fmt_yoy(fin.get('ordinary_profit_yoy'))}",
            f"純利益: {_fmt(fin.get('net_profit'))}  前年比: {_fmt_yoy(fin.get('net_profit_yoy'))}",
        ]
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(text_lines)},
            }
        )
        blocks.append({"type": "divider"})

    payload = {"blocks": blocks}
    _post(payload)


def _post(payload: dict) -> None:
    try:
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[Slack] HTTP {resp.status_code}: {resp.text}")
        else:
            print("[Slack] 通知送信完了")
    except Exception as exc:
        print(f"[Slack] 送信エラー: {exc}")
