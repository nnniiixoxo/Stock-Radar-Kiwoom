from __future__ import annotations

import math
import re
from typing import Any, Iterable


ALIASES = {
    "code": (
        "stk_cd",
        "stck_cd",
        "종목코드",
        "code",
    ),
    "name": (
        "stk_nm",
        "종목명",
        "name",
    ),
    "price": (
        "exp_cntr_pric",
        "cur_prc",
        "현재가",
        "예상체결가",
        "price",
    ),
    "change": (
        "exp_cntr_flu_rt",
        "pred_pre_flu_rt",
        "flu_rt",
        "등락률",
        "change_pct",
    ),
    "volume": (
        "exp_cntr_qty",
        "trde_qty",
        "예상체결량",
        "거래량",
        "volume",
    ),
    "bid": (
        "buy_req",
        "buy_bid",
        "매수잔량",
        "bid_volume",
    ),
    "ask": (
        "sel_req",
        "sel_bid",
        "매도잔량",
        "ask_volume",
    ),
    "turnover": (
        "trde_prica",
        "거래대금",
        "turnover",
    ),
}


# 아래 문구가 포함된 종목은 제외합니다.
EXCLUDED_NAME_PARTS = (
    "KODEX",
    "TIGER",
    "KOSEF",
    "KBSTAR",
    "RISE",
    "ARIRANG",
    "PLUS",
    "HANARO",
    "ACE ",
    "SOL ",
    "TIMEFOLIO",
    "FOCUS",
    "WOORI",
    "히어로즈",
    "ETN",
    "스팩",
    "SPAC",
    "리츠",
    "인버스",
    "레버리지",
)


def number(value: Any) -> float:
    """API 문자열을 안전하게 숫자로 바꿉니다."""

    if value is None or value == "":
        return 0.0

    text = re.sub(
        r"[^0-9.+-]",
        "",
        str(value).replace(",", ""),
    )

    try:
        result = float(text)

        if math.isfinite(result):
            return result

        return 0.0

    except ValueError:
        return 0.0


def pick(
    row: dict[str, Any],
    key: str,
    default: Any = "",
) -> Any:
    for name in ALIASES[key]:
        if (
            name in row
            and row[name] not in (None, "")
        ):
            return row[name]

    return default


def extract_rows(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for value in payload.values():
        if (
            isinstance(value, list)
            and value
            and isinstance(value[0], dict)
        ):
            rows.extend(value)

    return rows


def normalize(
    rows: Iterable[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for raw in rows:
        code = (
            str(pick(raw, "code"))
            .strip()
            .lstrip("A")[:6]
        )

        if not re.fullmatch(r"\d{6}", code):
            continue

        item = merged.setdefault(
            code,
            {"code": code},
        )

        for key in ALIASES:
            value = pick(raw, key, None)

            if value not in (None, ""):
                item[key] = value

    return merged


def is_common_stock(
    item: dict[str, Any],
) -> bool:
    """ETF·ETN·스팩·리츠·우선주 등을 제외합니다."""

    name = str(
        item.get("name", "")
    ).strip()

    upper = name.upper()

    if not name:
        return False

    if any(
        part.upper() in upper
        for part in EXCLUDED_NAME_PARTS
    ):
        return False

    # 이름이 우, 우B, 우C, 숫자우로 끝나는 우선주 제외
    if re.search(
        r"(?:우|우B|우C|\d우)$",
        name,
        re.IGNORECASE,
    ):
        return False

    return True


def preselect(
    items: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    일봉을 조회하기 전에
    유동성 있는 보통주 후보를 좁힙니다.
    """

    filters = config["filters"]
    candidates: list[dict[str, Any]] = []

    for item in items.values():
        price = abs(number(item.get("price")))
        change = number(item.get("change"))
        volume = abs(number(item.get("volume")))
        turnover = abs(number(item.get("turnover")))

        if not is_common_stock(item):
            continue

        if not (
            filters["min_price"]
            <= price
            <= filters["max_price"]
        ):
            continue

        if not (
            filters["min_expected_change_pct"]
            <= change
            <= filters["max_expected_change_pct"]
        ):
            continue

        row = dict(item)

        row.update(
            price=price,
            change_pct=change,
            expected_volume=volume,
            turnover=turnover,
        )

        candidates.append(row)

    # 거래대금과 예상체결량이 많은 종목부터 조회
    candidates.sort(
        key=lambda item: (
            item["turnover"],
            item["expected_volume"],
        ),
        reverse=True,
    )

    limit = int(
        config.get(
            "history_candidate_limit",
            60,
        )
    )

    return candidates[:limit]


def _sma(
    values: list[float],
    period: int,
    offset: int = 0,
) -> float:
    end = len(values) - offset
    start = end - period

    if start < 0:
        return 0.0

    return sum(values[start:end]) / period


def _rsi(
    closes: list[float],
    period: int = 14,
    offset: int = 0,
) -> float:
    end = len(closes) - offset
    start = end - period - 1

    if start < 0:
        return 50.0

    gains = 0.0
    losses = 0.0

    previous_values = closes[start:end - 1]
    current_values = closes[start + 1:end]

    for previous, current in zip(
        previous_values,
        current_values,
    ):
        delta = current - previous
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)

    if losses == 0:
        if gains:
            return 100.0

        return 50.0

    average_gain = gains / period
    average_loss = losses / period
    relative_strength = average_gain / average_loss

    return (
        100.0
        - 100.0 / (1.0 + relative_strength)
    )


def analyze_daily_chart(
    rows: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    """일봉으로 이동평균선, RSI, 거래대금을 계산합니다."""

    candles = []

    for row in rows:
        date = str(row.get("dt", ""))
        close = abs(
            number(row.get("cur_prc"))
        )

        if not date or close <= 0:
            continue

        candles.append(
            {
                "date": date,
                "close": close,
                "volume": abs(
                    number(row.get("trde_qty"))
                ),
                "turnover": abs(
                    number(row.get("trde_prica"))
                ),
            }
        )

    # 오래된 날짜부터 정렬
    candles.sort(
        key=lambda item: item["date"]
    )

    # 120일 이동평균선과 기울기 계산에 필요한 수량
    if len(candles) < 125:
        return None

    closes = [
        item["close"]
        for item in candles
    ]

    turnovers = [
        item["turnover"]
        for item in candles
    ]

    ma5 = _sma(closes, 5)
    ma10 = _sma(closes, 10)
    ma20 = _sma(closes, 20)
    ma50 = _sma(closes, 50)
    ma120 = _sma(closes, 120)

    previous_ma5 = _sma(
        closes,
        5,
        offset=1,
    )

    previous_ma10 = _sma(
        closes,
        10,
        offset=1,
    )

    rsi_now = _rsi(closes)

    rsi_previous = _rsi(
        closes,
        offset=1,
    )

    distance20 = (
        closes[-1] / ma20 - 1.0
    ) * 100.0

    previous_ma20 = _sma(
        closes,
        20,
        offset=1,
    )

    previous_distance20 = (
        closes[-2] / previous_ma20 - 1.0
    ) * 100.0

    average_turnover5 = (
        sum(turnovers[-5:]) / 5.0
    )

    average_turnover20 = (
        sum(turnovers[-20:]) / 20.0
    )

    return {
        "close": closes[-1],
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma50": ma50,
        "ma120": ma120,

        # 현재 20일선이 5거래일 전보다 높은지
        "ma20_up": (
            ma20
            > _sma(closes, 20, offset=5)
        ),

        # 현재 50일선이 5거래일 전보다 높은지
        "ma50_up": (
            ma50
            > _sma(closes, 50, offset=5)
        ),

        # 5일선 상승 또는 5·10일선 골든크로스
        "ma5_turn": (
            ma5 > previous_ma5
            or (
                previous_ma5 <= previous_ma10
                and ma5 > ma10
            )
        ),

        "rsi": rsi_now,
        "rsi_prev": rsi_previous,

        "distance20": distance20,

        "distance20_improving": (
            distance20
            > previous_distance20
        ),

        "avg_turnover20": (
            average_turnover20
        ),

        "turnover_ratio_5_20": (
            average_turnover5
            / max(average_turnover20, 1.0)
        ),

        "trading_days": len(candles),
    }


def _scaled(
    value: float,
    low: float,
    high: float,
) -> float:
    if high <= low:
        return 0.0

    result = (
        value - low
    ) / (
        high - low
    )

    return max(
        0.0,
        min(1.0, result),
    )


def _centered(
    value: float,
    ideal: float,
    radius: float,
) -> float:
    result = (
        1.0
        - abs(value - ideal) / radius
    )

    return max(0.0, result)


def rank_with_history(
    candidates: Iterable[dict[str, Any]],
    history: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    filters = config["filters"]
    weights = config["weights"]

    ranked: list[dict[str, Any]] = []

    for item in candidates:
        code = str(item["code"])
        chart = history.get(code)

        if not chart:
            continue

        change = number(
            item.get(
                "change_pct",
                item.get("change"),
            )
        )

        bid = abs(
            number(item.get("bid"))
        )

        ask = abs(
            number(item.get("ask"))
        )

        if bid or ask:
            bid_ask_ratio = (
                bid / max(ask, 1.0)
            )
        else:
            bid_ask_ratio = 1.0

        # 필수 조건 1:
        # 종가 > 120일선
        # 20일선 > 50일선 > 120일선
        if not (
            chart["close"] > chart["ma120"]
            and chart["ma20"]
            > chart["ma50"]
            > chart["ma120"]
        ):
            continue

        # 필수 조건 2:
        # 20일선과 50일선이 모두 상승 중
        if not (
            chart["ma20_up"]
            and chart["ma50_up"]
        ):
            continue

        # 필수 조건 3:
        # 최근 20일 평균 거래대금
        if (
            chart["avg_turnover20"]
            < filters[
                "min_avg_turnover_20d_million_krw"
            ]
        ):
            continue

        # 과매도와 과열 사이의 RSI
        if not (
            filters["min_rsi"]
            <= chart["rsi"]
            <= filters["max_rsi"]
        ):
            continue

        # 20일선에서 너무 멀리 떨어진 종목 제외
        if not (
            filters["min_distance20_pct"]
            <= chart["distance20"]
            <= filters["max_distance20_pct"]
        ):
            continue

        rsi_turn_bonus = (
            1.0
            if chart["rsi"] > chart["rsi_prev"]
            else 0.45
        )

        distance_turn_bonus = (
            1.0
            if chart["distance20_improving"]
            else 0.45
        )

        ma_turn_bonus = (
            1.0
            if chart["ma5_turn"]
            else 0.0
        )

        score = (
            weights["trend"]

            + weights["rsi_reversal"]
            * _centered(
                chart["rsi"],
                ideal=42.0,
                radius=20.0,
            )
            * rsi_turn_bonus

            + weights["distance_recovery"]
            * _centered(
                chart["distance20"],
                ideal=-0.5,
                radius=6.5,
            )
            * distance_turn_bonus

            + weights["ma5_10_turn"]
            * ma_turn_bonus

            + weights["turnover_trend"]
            * _scaled(
                chart["turnover_ratio_5_20"],
                low=1.0,
                high=1.8,
            )

            + weights["expected_volume"]
            * _scaled(
                abs(
                    number(
                        item.get(
                            "expected_volume"
                        )
                    )
                ),
                low=0,
                high=500_000,
            )

            + weights["orderbook"]
            * _centered(
                bid_ask_ratio,
                ideal=1.6,
                radius=1.5,
            )
        )

        # 장전부터 이미 많이 상승한 종목 감점
        if change > 1.5:
            score -= min(
                12.0,
                (change - 1.5) * 4.0,
            )

        # 매수 잔량이 지나치게 몰린 경우 감점
        if bid_ask_ratio > 5.0:
            score -= 8.0

        result = dict(item)

        result.update(
            {
                "price": abs(
                    number(item.get("price"))
                ),

                "change_pct": round(
                    change,
                    2,
                ),

                "expected_volume": int(
                    abs(
                        number(
                            item.get(
                                "expected_volume"
                            )
                        )
                    )
                ),

                "bid_ask_ratio": round(
                    bid_ask_ratio,
                    2,
                ),

                "rsi14": round(
                    chart["rsi"],
                    1,
                ),

                "distance20_pct": round(
                    chart["distance20"],
                    2,
                ),

                "turnover_ratio_5_20": round(
                    chart[
                        "turnover_ratio_5_20"
                    ],
                    2,
                ),

                "score": round(
                    max(
                        0.0,
                        min(100.0, score),
                    ),
                    1,
                ),
            }
        )

        if (
            result["score"]
            >= config["min_score"]
        ):
            ranked.append(result)

    ranked.sort(
        key=lambda item: (
            -item["score"],
            -item["turnover_ratio_5_20"],
        )
    )

    return ranked[:config["top_n"]]
