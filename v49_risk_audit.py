"""Deterministic, fee-aware signal outcome comparison. No probability claims."""
import math

def evaluate_trades(rows,fee_bps=10,slippage_bps=10):
    """rows: market, entry, exit, optional max_drawdown_pct and blocked flag.
    Comparison uses identical recorded exits; it is not a causal backtest.
    """
    if not 0<=fee_bps<=1000 or not 0<=slippage_bps<=1000:
        raise ValueError("invalid costs")
    cost_pct=2*(fee_bps+slippage_bps)/100
    valid=[]
    for row in rows:
        try:
            entry=float(row["entry"]);exit_price=float(row["exit"])
            if not all(math.isfinite(v) and v>0 for v in (entry,exit_price)):
                continue
            pnl=100*(exit_price/entry-1)-cost_pct
            drawdown=row.get("max_drawdown_pct")
            drawdown=float(drawdown) if drawdown is not None else None
            if drawdown is not None and not math.isfinite(drawdown):drawdown=None
            valid.append({"market":row.get("market",""),"net_pct":pnl,
                          "blocked":bool(row.get("blocked",False)),
                          "drawdown_pct":drawdown})
        except (KeyError,TypeError,ValueError):continue
    def stats(group):
        n=len(group)
        if not n:return {"count":0,"win_rate_pct":None,"avg_net_pct":None,"avg_drawdown_pct":None}
        dd=[x["drawdown_pct"] for x in group if x["drawdown_pct"] is not None]
        return {"count":n,"win_rate_pct":round(100*sum(x["net_pct"]>0 for x in group)/n,2),
                "avg_net_pct":round(sum(x["net_pct"] for x in group)/n,3),
                "avg_drawdown_pct":round(sum(dd)/len(dd),3) if dd else None}
    return {"all_signals":stats(valid),"gate_passed":stats([x for x in valid if not x["blocked"]]),
            "gate_blocked":stats([x for x in valid if x["blocked"]]),
            "cost_round_trip_pct":round(cost_pct,3),
            "warning":"동일한 과거 신호의 조건부 비교입니다. 미래 수익률이나 필터 인과효과를 입증하지 않습니다."}
