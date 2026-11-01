"""Research-only next-open trade outcomes. Not fills, live alerts, or advice."""
def evaluate_outcomes(events, candles, *, fee_roundtrip_pct=0.2, horizon_minutes=180):
    if fee_roundtrip_pct<0 or horizon_minutes<5:
        raise ValueError("invalid assumptions")
    bars={b['ts']:b for b in candles}
    results=[]
    occupied_until=-1
    for e in sorted(events,key=lambda x:x['signal_close_ts']):
        if e.get('status')!='RESOLVED' or not e.get('risk_levels_valid'):
            continue
        start=e['entry_ts']
        if start<=occupied_until:
            continue
        entry=float(e['entry_reference'])
        stop=float(e['stop_reference'])
        target=float(e['tp1_reference'])
        if not 0<stop<entry<target:
            continue
        exit_price=None
        reason='TIME'
        last=None
        for ts in range(start,start+horizon_minutes*60,300):
            b=bars.get(ts)
            if b is None:
                reason='UNRESOLVED_GAP'
                break
            last=b
            o=float(b['open']);lo=float(b['low']);hi=float(b['high'])
            if o<=stop:exit_price=o;reason='STOP_GAP';break
            if o>=target:exit_price=o;reason='TP1_GAP';break
            if lo<=stop:exit_price=stop;reason='STOP';break
            if hi>=target:exit_price=target;reason='TP1';break
        if last is None or reason=='UNRESOLVED_GAP':
            results.append({'entry_ts':start,'status':'UNRESOLVED_GAP'})
            continue
        if exit_price is None:exit_price=float(last['close'])
        occupied_until=last['ts']
        results.append({'entry_ts':start,'exit_ts':last['ts'],
                        'exit_reason':reason,
                        'net_pct':round((exit_price/entry-1)*100-fee_roundtrip_pct,6),
                        'execution_verified':False,'status':'RESOLVED'})
    closed=[r for r in results if r['status']=='RESOLVED']
    exit_reason_counts={}
    for trade in closed:
        reason=trade['exit_reason']
        exit_reason_counts[reason]=exit_reason_counts.get(reason,0)+1
    gross_losses=sum(r['net_pct']<0 for r in closed)
    gross_wins=sum(r['net_pct']>0 for r in closed)
    return {'trades':results,'closed_count':len(closed),
            'exit_reason_counts':exit_reason_counts,
            'positive_net_trades':gross_wins,'negative_net_trades':gross_losses,
            'unresolved_count':len(results)-len(closed),
            'mean_net_pct':round(sum(r['net_pct'] for r in closed)/len(closed),6) if closed else None,
            'win_rate_pct':round(100*sum(r['net_pct']>0 for r in closed)/len(closed),2) if closed else None,
            'assumed_roundtrip_cost_pct':fee_roundtrip_pct,
            'execution_verified':False}
