"""Forward-only BUY gate outcome comparison; no invented fills or intrabar extremes."""
import math

def compare(events, prices, horizon_seconds=86400, fee_bps=10, slippage_bps=10, max_sample_delay_seconds=900):
    if horizon_seconds<=0 or max_sample_delay_seconds<0 or min(fee_bps,slippage_bps)<0:raise ValueError("invalid parameters")
    cost=2*(fee_bps+slippage_bps)/100
    by_market={}
    for p in prices:
        try:
            market=str(p["market"]);ts=int(p["time"]);price=float(p["price"])
            if not math.isfinite(price) or price<=0:continue
            by_market.setdefault(market,[]).append((ts,price))
        except (KeyError,ValueError,TypeError):continue
    for samples in by_market.values():samples.sort()
    groups={True:[],False:[]};unresolved=0
    for e in events:
        try:
            ts=int(e["time"]);entry=float(e["price"]);allowed=bool(e["allowed"])
            if not math.isfinite(entry) or entry<=0:continue
            target=ts+horizon_seconds
            # A sample must be observed at or after the full holding horizon.
            future=next((p for t,p in by_market.get(str(e["market"]),[]) if target<=t<=target+max_sample_delay_seconds),None)
            if future is None:unresolved+=1;continue
            groups[allowed].append(100*(future/entry-1)-cost)
        except (KeyError,ValueError,TypeError):continue
    def summarize(values):
        return {"count":len(values),"mean_net_pct":round(sum(values)/len(values),3) if values else None,
                "win_rate_pct":round(100*sum(x>0 for x in values)/len(values),2) if values else None}
    return {"allowed":summarize(groups[True]),"blocked":summarize(groups[False]),
            "unresolved":unresolved,"horizon_seconds":horizon_seconds,
            "note":"기록된 관찰가격 기준 고정 보유기간 비교. 체결 가능 가격·인과효과·실거래 수익률 아님."}
