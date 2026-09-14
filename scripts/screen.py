from __future__ import annotations

import json
import os
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
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    client = KiwoomClient(mode=config.get("mode"))
    calls = [
        ("ka10029", {"mrkt_tp": "000", "sort_tp": "1"}),
        ("ka10023", {"mrkt_tp": "000", "sort_tp": "1", "tm_tp": "1", "trde_qty_tp": "5", "stk_cnd": "0", "pric_tp": "0"}),
        ("ka10032", {"mrkt_tp": "000", "mang_stk_incls": "0", "stex_tp": "3"}),
        ("ka10020", {"mrkt_tp": "000", "sort_tp": "1", "trde_qty_tp": "0", "stk_cnd": "0", "crd_cnd": "0", "stex_tp": "3"}),
        ("ka90009", {"mrkt_tp": "000", "amt_qty_tp": "1", "qry_dt_tp": "0", "stex_tp": "3"}),
    ]
    rows, warnings = [], []
    try:
        for api_id, body in calls:
            try:
                rows.extend(extract_rows(client.call(api_id, body)))
            except KiwoomError as exc:
                warnings.append(str(exc))
        items = normalize(rows)
        selected = rank(items, config)
        status = "ok" if rows else "no_data"
        result = {
            "schema_version": 2,
            "generated_at": now.isoformat(),
            "market_date": now.date().isoformat(),
            "status": status,
            "message": "프리마켓·예상체결 기반 선별 완료" if selected else "조건을 통과한 종목이 없습니다.",
            "candidate_count": len(items),
            "stocks": selected,
            "warnings": warnings,
            "disclaimer": "정보 제공용이며 수익을 보장하지 않습니다. 주문 기능은 포함하지 않습니다."
        }
        if status == "no_data" and OUTPUT.exists():
            old = json.loads(OUTPUT.read_text(encoding="utf-8"))
            old.update({"last_attempt_at": now.isoformat(), "last_attempt_status": "no_data", "warnings": warnings})
            result = old
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        temp = OUTPUT.with_suffix(".tmp")
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(OUTPUT)
        print(json.dumps({"status": status, "candidates": len(items), "selected": len(selected), "warnings": warnings}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"예상하지 못한 오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

