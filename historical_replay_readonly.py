"""Offline, forward-only candle replay. Never connects to exchanges or places orders.

Input rows: sorted or unsorted OHLCV dicts with integer UTC Unix seconds in 'ts'.
Indicators use ONLY candles closed at the evaluated timestamp. A signal emitted at
close of candle i is first eligible for execution at candle i+1 OPEN.
This module is a research harness, not a reconstruction of historical live alerts.
"""
import math

def replay(candles, signal_fn, *, max_holding_bars=12, fee_roundtrip_pct=0.2):
    if max_holding_bars < 1: raise ValueError("max_holding_bars must be positive")
    if fee_roundtrip_pct < 0: raise ValueError("fee must be nonnegative")
    rows=sorted(candles,key=lambda x:x["ts"])
    if len({r["ts"] for r in rows})!=len(rows): raise ValueError("duplicate candle timestamps")
    for r in rows:
        vals=[float(r[k]) for k in ("open","high","low","close","volume")]
        if not all(math.isfinite(v) for v in vals): raise ValueError("nonfinite OHLCV")
        o,h,l,c,v=vals
        if min(o,h,l,c)<=0 or v<0 or h<max(o,c,l) or l>min(o,c,h):
            raise ValueError("invalid OHLCV")
    trades=[]
    i=0
    while i<len(rows)-1:
        # Immutable tuple of historical snapshots prevents future-candle access.
        history=tuple(dict(x) for x in rows[:i+1])
        signal=signal_fn(history)
        if not signal:
            i+=1
            continue
        stop=float(signal["stop"])
        target=float(signal["target"])
        entry_idx=i+1
        entry=float(rows[entry_idx]["open"])
        if not (math.isfinite(stop) and math.isfinite(target) and 0<stop<target and entry<target):
            i+=1
            continue
        end=min(entry_idx+max_holding_bars-1,len(rows)-1)
        exit_price=None;reason="TIME";exit_idx=end
        for j in range(entry_idx,end+1):
            bar=rows[j];o=float(bar["open"]);low=float(bar["low"]);high=float(bar["high"])
            # Conservative ordering: gap at open, then stop before target if both hit.
            if o<=stop: exit_price=o;reason="STOP_GAP";exit_idx=j;break
            if o>=target: exit_price=o;reason="TARGET_GAP";exit_idx=j;break
            if low<=stop: exit_price=stop;reason="STOP";exit_idx=j;break
            if high>=target: exit_price=target;reason="TARGET";exit_idx=j;break
        if exit_price is None:exit_price=float(rows[end]["close"])
        trades.append({"signal_ts":rows[i]["ts"],"entry_ts":rows[entry_idx]["ts"],
                       "exit_ts":rows[exit_idx]["ts"],"entry":entry,"exit":exit_price,
                       "exit_reason":reason,"net_pct":round((exit_price/entry-1)*100-fee_roundtrip_pct,6),
                       "execution_verified":False})
        i=exit_idx+1
    return trades

def summarize(trades):
    if not trades:return {"count":0,"mean_net_pct":None,"win_rate_pct":None}
    returns=[t["net_pct"] for t in trades]
    return {"count":len(trades),"mean_net_pct":round(sum(returns)/len(returns),6),
            "win_rate_pct":round(100*sum(x>0 for x in returns)/len(returns),2)}
