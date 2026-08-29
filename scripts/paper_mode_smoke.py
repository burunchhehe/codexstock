from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.native_core import NativeBroker, NativeJournal, NativeMarket  # noqa: E402


def main() -> int:
    market = NativeMarket()
    broker = NativeBroker(market=market, journal=NativeJournal())
    quote = market.quote("AAPL")
    order = broker.submit_market_order("AAPL", "BUY", 1)
    portfolio = broker.portfolio()
    checks = {
        "synthetic_data_labeled": quote.get("data_mode") == "synthetic",
        "quote_blocks_real_orders": quote.get("real_order_allowed") is False,
        "paper_order_labeled": order.get("real_order_allowed") is False,
        "portfolio_labeled": portfolio.get("real_order_allowed") is False,
        "paper_position_created": len(portfolio.get("positions", [])) == 1,
    }
    payload = {"ok": all(checks.values()), "mode": "synthetic_paper_smoke", "checks": checks, "real_order_allowed": False}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
