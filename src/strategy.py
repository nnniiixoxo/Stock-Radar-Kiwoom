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
        "pred_pric",
        "현재가",
        "예상체결가",
        "price",
    ),
    "change": (
        "exp_cntr_flu_rt",
        "flu_rt",
        "pred_pre_flu_rt",
        "pred_flu_rt",
        "등락률",
        "예상체결등락률",
        "change_pct",
    ),
    "volume": (
        "exp_cntr_qty",
        "trde_qty",
        "pred_trde_qty",
        "예상체결량",
        "거래량",
        "volume",
    ),
    "bid": (
        "buy_req",
        "buy_bid",
        "buy_req_qty",
        "매수잔량",
        "bid_volume",
    ),
    "ask": (
        "sel_req",
        "sel_bid",
        "sel_req_qty",
        "매도잔량",
        "ask_volume",
    ),
    "strength": (
        "cntr_str",
        "체결강도",
        "execution_strength",
    ),
    "turnover": (
        "trde_prica",
        "trde_amt",
        "거래대금",
        "turnover",
    ),
    "foreign": (
        "for_netprps",
        "frgnr_netprps",
        "외인순매수",
        "foreign_net",
    ),
    "institution": (
        "orgn_netprps",
        "기관순매수",
        "institution_net",
    ),
}


def number(value: Any) -> float:
    if value is None or value == "":
        return 0.0

    text = str(value).replace(",", "")
    text = re.sub(r"[^0-9.+-]", "", text)

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
        if name in row and row[name] not in (None, ""):
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
        code = str(
            pick(raw, "code")
        ).strip().lstrip("A")

        if not code:
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


def _scaled(
    value: float,
    low: float,
    high: float,
) -> float:
    if high <= low:
        return 0.0

    return max(
        0.0,
        min(
            1.0,
            (value - low) / (high - low),
        ),
    )


def rank(
    items: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    filters = config["filters"]
    weights = config["weights"]

    ranked: list[dict[str, Any]] = []

    max_turnover = max(
        (
            abs(number(item.get("turnover")))
            for item in items.values()
        ),
        default=1.0,
    ) or 1.0

    max_volume = max(
        (
            abs(number(item.get("volume")))
            for item in items.values()
        ),
        default=1.0,
    ) or 1.0

    for item in items.values():
        price = abs(number(item.get("price")))
        change = number(item.get("change"))
        volume = abs(number(item.get("volume")))

        bid = abs(number(item.get("bid")))
        ask = abs(number(item.get("ask")))

        bid_ask_ratio = bid / max(ask, 1.0)

        strength = number(
            item.get("strength")
        )

        turnover = abs(
            number(item.get("turnover"))
        )

        foreign = number(
            item.get("foreign")
        )

        institution = number(
            item.get("institution")
        )

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

        if volume < filters["min_expected_volume"]:
            continue

        score = (
            weights["expected_change"]
            * max(
                0.0,
                1.0 - abs(change - 2.5) / 2.5,
            )
            + weights["expected_volume"]
            * _scaled(
                volume,
                0,
                max_volume,
            )
            + weights["orderbook"]
            * _scaled(
                bid_ask_ratio,
                0.8,
                2.0,
            )
            + weights["execution_strength"]
            * _scaled(
                strength,
                90,
                150,
            )
            + weights["turnover"]
            * _scaled(
                turnover,
                0,
                max_turnover,
            )
            + weights["foreign_institution"]
            * _scaled(
                foreign + institution,
                0,
                1_000_000,
            )
            + weights["market_regime"] * 0.5
        )

        result = dict(item)

        result.update(
            {
                "price": price,
                "change_pct": round(change, 2),
                "expected_volume": int(volume),
                "bid_ask_ratio": round(
                    bid_ask_ratio,
                    2,
                ),
                "execution_strength": round(
                    strength,
                    1,
                ),
                "score": round(
                    max(0.0, score),
                    1,
                ),
            }
        )

        if result["score"] >= config["min_score"]:
            ranked.append(result)

    ranked.sort(
        key=lambda item: (
            -item["score"],
            -item["expected_volume"],
        )
    )

    return ranked[: config["top_n"]]
