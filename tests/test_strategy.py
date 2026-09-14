import json
from pathlib import Path

from src.strategy import extract_rows, normalize, number, rank


CONFIG = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8"))


def test_number_is_safe():
    assert number("+12,345") == 12345
    assert number(None) == 0
    assert number("-") == 0


def test_empty_payload_never_indexes_empty_list():
    assert extract_rows({"output": [], "return_code": 0}) == []
    assert normalize([]) == {}
    assert rank({}, CONFIG) == []


def test_alias_merge_and_rank():
    payloads = [
        {"종목코드": "A005930", "종목명": "테스트", "예상체결가": "+70000", "등락률": "+2.20", "예상체결량": "900000"},
        {"stk_cd": "005930", "buy_req": "300000", "sel_req": "100000", "cntr_str": "145", "trde_prica": "50000000000", "for_netprps": "500000"},
    ]
    ranked = rank(normalize(payloads), CONFIG)
    assert ranked and ranked[0]["code"] == "005930"
    assert ranked[0]["bid_ask_ratio"] == 3

