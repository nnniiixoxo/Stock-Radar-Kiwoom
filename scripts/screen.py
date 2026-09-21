from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.kiwoom import KiwoomClient, KiwoomError
from src.strategy import (
    analyze_daily_chart,
    extract_rows,
    normalize,
    preselect,
    rank_with_history,
)


OUTPUT = (
    ROOT
    / "dist"
    / "data"
    / "results.json"
)


def main() -> int:
    config_path = ROOT / "config.json"

    config = json.loads(
        config_path.read_text(
            encoding="utf-8"
        )
    )

    now = datetime.now(
        ZoneInfo("Asia/Seoul")
    )

    client = KiwoomClient(
        mode=config.get("mode")
    )

    # 장전 예상체결, 거래량, 거래대금,
    # 호가 관련 후보를 모읍니다.
    calls = [
        (
            "ka10029",
            {
                "mrkt_tp": "000",
                "sort_tp": "1",
            },
        ),
        (
            "ka10023",
            {
                "mrkt_tp": "000",
                "sort_tp": "1",
                "tm_tp": "1",
                "trde_qty_tp": "5",
                "stk_cnd": "0",
                "pric_tp": "0",
                "trde_qty_cnd": "0",
                "stex_tp": "3",
            },
        ),
        (
            "ka10032",
            {
                "mrkt_tp": "000",
                "mang_stk_incls": "0",
                "stex_tp": "3",
            },
        ),
        (
            "ka10020",
            {
                "mrkt_tp": "000",
                "sort_tp": "1",
                "trde_qty_tp": "0",
                "stk_cnd": "0",
                "crd_cnd": "0",
                "stex_tp": "3",
            },
        ),
        (
            "ka90009",
            {
                "mrkt_tp": "000",
                "amt_qty_tp": "1",
                "qry_dt_tp": "0",
                "stex_tp": "3",
            },
        ),
    ]

    rows: list[dict] = []
    warnings: list[str] = []

    try:
        # 1단계:
        # 여러 순위 API에서 후보 종목을 수집합니다.
        for api_id, body in calls:
            try:
                payload = client.call(
                    api_id,
                    body,
                )

                rows.extend(
                    extract_rows(payload)
                )

            except KiwoomError as exc:
                warnings.append(str(exc))

        items = normalize(rows)

        # ETF·ETN·우선주 등을 제외하고
        # 일봉을 조회할 후보를 최대 60개로 좁힙니다.
        candidates = preselect(
            items,
            config,
        )

        # 2단계:
        # 후보별 일봉을 조회합니다.
        history: dict[str, dict] = {}

        base_date = now.strftime("%Y%m%d")

        for index, item in enumerate(
            candidates
        ):
            code = item["code"]

            try:
                payload = client.call(
                    "ka10081",
                    {
                        "stk_cd": code,
                        "base_dt": base_date,
                        "upd_stkpc_tp": "1",
                    },
                )

                chart_rows = payload.get(
                    "stk_dt_pole_chart_qry",
                    [],
                )

                chart = analyze_daily_chart(
                    chart_rows
                )

                if chart:
                    history[code] = chart

            except KiwoomError as exc:
                warnings.append(
                    f"{code} 일봉 조회 실패: {exc}"
                )

            # 국내주식 조회 한도인
            # 초당 5회를 넘지 않게 기다립니다.
            if index + 1 < len(candidates):
                time.sleep(0.23)

        # 정배열, RSI, 이격도, 거래대금,
        # 예상체결량과 호가를 합산합니다.
        selected = rank_with_history(
            candidates,
            history,
            config,
        )

        status = (
            "ok"
            if rows
            else "no_data"
        )

        if selected:
            message = (
                "전일 차트와 장전 수급을 결합한 "
                "상승 가능성 점수"
            )
        else:
            message = (
                "새 기준을 통과한 종목이 없습니다."
            )

        result = {
            "schema_version": 3,
            "generated_at": now.isoformat(),
            "market_date": (
                now.date().isoformat()
            ),
            "status": status,
            "message": message,
            "candidate_count": len(items),
            "history_checked": len(history),
            "stocks": selected,
            "warnings": warnings[:20],
            "disclaimer": (
                "상승 가능성 점수는 확률이나 "
                "수익 보장이 아닙니다. "
                "정보 제공용이며 주문 기능은 없습니다."
            ),
        }

        # API 전체가 실패한 경우에는
        # 기존 정상 결과를 지우지 않습니다.
        if (
            status == "no_data"
            and OUTPUT.exists()
        ):
            old = json.loads(
                OUTPUT.read_text(
                    encoding="utf-8"
                )
            )

            old.update(
                {
                    "last_attempt_at":
                        now.isoformat(),

                    "last_attempt_status":
                        "no_data",

                    "warnings":
                        warnings[:20],
                }
            )

            result = old

        OUTPUT.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp = OUTPUT.with_suffix(".tmp")

        temp.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temp.replace(OUTPUT)

        print(
            json.dumps(
                {
                    "status": status,
                    "candidates": len(items),
                    "history_checked":
                        len(history),
                    "selected":
                        len(selected),
                    "warnings":
                        warnings[:5],
                },
                ensure_ascii=False,
            )
        )

        return 0

    except Exception as exc:
        print(
            f"예상하지 못한 오류: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
