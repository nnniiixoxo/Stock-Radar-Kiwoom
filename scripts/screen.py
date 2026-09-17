from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.kiwoom import KiwoomClient, KiwoomError
from src.strategy import extract_rows, normalize, rank

OUTPUT = ROOT / "dist" / "data" / "results.json"


def main() -> int:
    config = json.loads(
        (ROOT / "config.json").read_text(encoding="utf-8")
    )

    now = datetime.now(ZoneInfo("Asia/Seoul"))
    client = KiwoomClient(mode=config.get("mode"))

    # 키움 REST API 조회 목록
    calls = [
        (
            "ka10029",
            {
                "mrkt_tp": "000",
                "sort_tp": "1",
                "trde_qty_cnd": "0",
                "stk_cnd": "0",
                "crd_cnd": "0",
                "pric_cnd": "0",
                "stex_tp": "3",
            },
        ),
        (
            "ka10023",
            {
                "mrkt_tp": "000",
                "sort_tp": "1",
                "tm_tp": "1",
                "trde_qty_tp": "5",
                "tm": "",
                "stk_cnd": "0",
                "pric_tp": "0",
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

    rows = []
    warnings = []

    try:
        for api_id, body in calls:
            try:
                response = client.call(api_id, body)
                api_rows = extract_rows(response)
                rows.extend(api_rows)

                print(
                    f"{api_id} 조회 성공: "
                    f"{len(api_rows)}개 자료 수집"
                )

            except KiwoomError as exc:
                warning = str(exc)
                warnings.append(warning)
                print(warning, file=sys.stderr)

        items = normalize(rows)
        selected = rank(items, config)

        status = "ok" if rows else "no_data"

        if selected:
            message = (
                f"조건을 통과한 종목 {len(selected)}개를 찾았습니다."
            )
        elif rows:
            message = (
                "자료는 정상적으로 조회했지만 "
                "현재 조건을 통과한 종목이 없습니다."
            )
        else:
            message = "키움 API에서 종목 자료를 가져오지 못했습니다."

        result = {
            "schema_version": 2,
            "generated_at": now.isoformat(),
            "market_date": now.date().isoformat(),
            "status": status,
            "message": message,
            "candidate_count": len(items),
            "stocks": selected,
            "warnings": warnings,
            "disclaimer": (
                "정보 제공용이며 수익을 보장하지 않습니다. "
                "주문 기능은 포함하지 않습니다."
            ),
        }

        OUTPUT.parent.mkdir(parents=True, exist_ok=True)

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

        summary = {
            "status": status,
            "candidates": len(items),
            "selected": len(selected),
            "warnings": warnings,
        }

        print(
            json.dumps(
                summary,
                ensure_ascii=False,
            )
        )

        # 종목 자료를 하나도 가져오지 못하면 실패 처리
        if not rows:
            return 1

        return 0

    except Exception as exc:
        print(
            f"예상하지 못한 오류: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
