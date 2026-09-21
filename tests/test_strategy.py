import json
from pathlib import Path

from src.strategy import (
    analyze_daily_chart,
    extract_rows,
    is_common_stock,
    normalize,
    number,
    preselect,
    rank_with_history,
)


ROOT = Path(__file__).parents[1]

CONFIG = json.loads(
    (ROOT / "config.json").read_text(
        encoding="utf-8"
    )
)


def test_number_is_safe():
    assert number("+12,345") == 12345
    assert number(None) == 0
    assert number("-") == 0


def test_empty_payload_is_safe():
    assert extract_rows(
        {
            "output": [],
            "return_code": 0,
        }
    ) == []

    assert normalize([]) == {}

    assert preselect(
        {},
        CONFIG,
    ) == []

    assert rank_with_history(
        [],
        {},
        CONFIG,
    ) == []


def test_etf_and_preferred_stock_are_excluded():
    assert not is_common_stock(
        {
            "name": "KODEX 200",
        }
    )

    assert not is_common_stock(
        {
            "name": "삼성전자우",
        }
    )

    assert is_common_stock(
        {
            "name": "삼성전자",
        }
    )


def test_daily_chart_requires_enough_history():
    chart = analyze_daily_chart(
        [
            {
                "dt": "20260101",
                "cur_prc": "1000",
            }
        ]
    )

    assert chart is None


def test_rank_with_history_returns_common_stock():
    rows = [
        {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "exp_cntr_pric": "70000",
            "exp_cntr_flu_rt": "+0.5",
            "exp_cntr_qty": "900000",
        },
        {
            "stk_cd": "005930",
            "buy_req": "160000",
            "sel_req": "100000",
            "trde_prica": "50000",
        },
    ]

    items = normalize(rows)

    candidates = preselect(
        items,
        CONFIG,
    )

    history = {
        "005930": {
            "close": 70000,
            "ma20": 68000,
            "ma50": 65000,
            "ma120": 60000,
            "ma20_up": True,
            "ma50_up": True,
            "ma5_turn": True,
            "rsi": 42,
            "rsi_prev": 39,
            "distance20": -0.5,
            "distance20_improving": True,
            "avg_turnover20": 50000,
            "turnover_ratio_5_20": 1.5,
            "trading_days": 200,
        }
    }

    ranked = rank_with_history(
        candidates,
        history,
        CONFIG,
    )

    assert ranked
    assert ranked[0]["code"] == "005930"
    assert ranked[0]["bid_ask_ratio"] == 1.6

    assert (
        "execution_strength"
        not in ranked[0]
    )
