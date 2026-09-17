from __future__ import annotations

import json
import sys
import time
from datetime import datetime, time as clock_time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.kiwoom import KiwoomClient, KiwoomError
from src.strategy import extract_rows, normalize, rank

OUTPUT = ROOT / "dist" / "data" / "results.json"


def number(value) -> float:
    if value is None or value == "":
        return 0.0

    try:
        text = str(value)
        text = text.replace(",", "")
        text = text.replace("+", "")
        text = text.replace("%", "")

        return float(text)

    except (TypeError, ValueError):
        return 0.0


def trading_started(now: datetime) -> bool:
    """
    평일 오전 9시 이후인지 확인합니다.
    장 마감 후에도 오늘 누적 거래량은 조회합니다.
    """

    if now.weekday() >= 5:
        return False

    return now.time() >= clock_time(9, 0)


def add_live_data(
    client: KiwoomClient,
    selected: list[dict],
    config: dict,
    warnings: list[str],
    now: datetime,
) -> None:
    """
    최종 선정 종목의 체결강도와 누적 거래량을
    ka10046에서 조회하여 추가합니다.
    """

    if not trading_started(now):
        print(
            "현재는 장 시작 전입니다. "
            "실제 체결강도와 누적 거래량은 "
            "오전 9시 이후 생성됩니다."
        )
        return

    strength_weight = number(
        config.get("weights", {}).get(
            "execution_strength",
            0,
        )
    )

    for stock in selected:
        code = str(
            stock.get("code", "")
        ).strip()

        if not code:
            continue

        try:
            response = client.call(
                "ka10046",
                {
                    "stk_cd": code,
                },
            )

            live_rows = extract_rows(response)

            if not live_rows:
                stock["execution_strength"] = 0

                print(
                    f"{code}: 체결강도 자료 없음"
                )

                time.sleep(0.25)
                continue

            # 첫 번째 자료가 가장 최근 시간 자료
            latest = live_rows[0]

            strength = number(
                latest.get("cntr_str")
            )

            accumulated_volume = number(
                latest.get("acc_trde_qty")
            )

            # 일부 응답에서 누적거래량이 없으면
            # 일반 거래량 항목을 대신 사용
            if accumulated_volume <= 0:
                accumulated_volume = number(
                    latest.get("trde_qty")
                )

            stock["execution_strength"] = round(
                strength,
                1,
            )

            if accumulated_volume > 0:
                stock["expected_volume"] = int(
                    accumulated_volume
                )

            # 기존 점수에는 체결강도가 0으로
            # 계산됐으므로 실제 강도 점수 추가
            strength_ratio = max(
                0.0,
                min(
                    1.0,
                    (strength - 90.0) / 60.0,
                ),
            )

            previous_score = number(
                stock.get("score")
            )

            stock["score"] = round(
                min(
                    100.0,
                    previous_score
                    + strength_weight
                    * strength_ratio,
                ),
                1,
            )

            print(
                f"{code}: "
                f"체결강도={strength:.1f}, "
                f"누적거래량={int(accumulated_volume)}"
            )

        except KiwoomError as exc:
            warning = (
                f"{code} 실시간 자료 조회 실패: "
                f"{exc}"
            )

            warnings.append(warning)

            print(
                warning,
                file=sys.stderr,
            )

        # 키움 API의 초당 조회 제한 보호
        time.sleep(0.25)


def main() -> int:
    config = json.loads(
        (ROOT / "config.json").read_text(
            encoding="utf-8"
        )
    )

    now = datetime.now(
        ZoneInfo("Asia/Seoul")
    )

    client = KiwoomClient(
        mode=config.get("mode")
    )

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
                response = client.call(
                    api_id,
                    body,
                )

                api_rows = extract_rows(response)
                rows.extend(api_rows)

                print(
                    f"{api_id} 조회 성공: "
                    f"{len(api_rows)}개 자료 수집"
                )

            except KiwoomError as exc:
                warning = str(exc)
                warnings.append(warning)

                print(
                    warning,
                    file=sys.stderr,
                )

        items = normalize(rows)
        selected = rank(items, config)

        # 선정된 종목의 실제 체결강도와
        # 누적 거래량 조회
        add_live_data(
            client=client,
            selected=selected,
            config=config,
            warnings=warnings,
            now=now,
        )

        # 체결강도 반영 점수로 다시 정렬
        selected.sort(
            key=lambda stock: (
                -number(stock.get("score")),
                -number(
                    stock.get(
                        "expected_volume"
                    )
                ),
            )
        )

        status = (
            "ok"
            if rows
            else "no_data"
        )

        if selected:
            message = (
                f"조건을 통과한 종목 "
                f"{len(selected)}개를 찾았습니다."
            )

        elif rows:
            message = (
                "자료는 정상적으로 조회했지만 "
                "현재 조건을 통과한 종목이 없습니다."
            )

        else:
            message = (
                "키움 API에서 종목 자료를 "
                "가져오지 못했습니다."
            )

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

        OUTPUT.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = OUTPUT.with_suffix(
            ".tmp"
        )

        temporary.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporary.replace(OUTPUT)

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
