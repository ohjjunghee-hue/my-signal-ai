#!/usr/bin/env python3
"""Read-only BUY lifecycle audit for MY SIGNAL AI PRO SQLite.

Usage: python audit_buy_lifecycle.py data/signals.db
Does not modify the database or infer executed fills.
"""
import argparse
import json
import sqlite3
from collections import Counter

def audit(db_path):
    uri = "file:" + __import__("pathlib").Path(db_path).resolve().as_posix() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as con:
        con.row_factory = sqlite3.Row
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        needed = {"setup_events", "active_setups"}
        if not needed <= tables:
            raise ValueError("Required tables missing: " + ", ".join(sorted(needed - tables)))
        events = [dict(r) for r in con.execute(
            "SELECT market,ts,previous,new_status,price,reason FROM setup_events ORDER BY ts,id")]
        setups = {r["market"]:dict(r) for r in con.execute(
            "SELECT market,status,last_signal,last_signal_price,first_seen,stop_price,last_price FROM active_setups")}
    buys = [e for e in events if e["new_status"] == "BUY"]
    first_buy = {}
    for e in buys:
        first_buy.setdefault(e["market"], e)
    missing = sorted(set(first_buy) - set(setups))
    discrepancies = []
    for market, event in first_buy.items():
        setup = setups.get(market)
        if setup and setup["last_signal"] is None:
            discrepancies.append({"market":market,"issue":"BUY event exists but last_signal is null"})
        if setup and setup["first_seen"] > event["ts"]:
            discrepancies.append({"market":market,"issue":"first_seen later than BUY event"})
    return {
        "scope":"Available retained SQLite rows only; not full historical accuracy",
        "buy_events":len(buys),
        "unique_buy_markets":len(first_buy),
        "buy_markets_missing_from_active_setups":missing,
        "buy_market_current_statuses":dict(Counter(setups[m]["status"] for m in first_buy if m in setups)),
        "discrepancies":discrepancies,
        "limitations":[
            "Purged setups may be absent by design after retention window.",
            "Current status is not the original BUY event.",
            "No candle path, fill, slippage, spread or profitability validation."
        ],
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("database")
    args=p.parse_args()
    print(json.dumps(audit(args.database),ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
