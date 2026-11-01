"""Independent historical surge-event denominator and candidate recall.

Research only. Surge events are derived from future OHLCV and are NEVER
provided to the signal algorithm. Results do not imply live fills.
"""
def surge_window_coverage(bars, *, horizon_bars=36):
    """Count assessable 5m forward windows separately from unresolved gaps."""
    if horizon_bars<1:
        raise ValueError('positive horizon required')
    rows=sorted(bars,key=lambda x:x['ts'])
    if len({r['ts'] for r in rows})!=len(rows):
        raise ValueError('duplicate timestamps')
    windows=max(0,len(rows)-horizon_bars)
    eligible=0
    for i in range(windows):
        if all(b['ts']-a['ts']==300 for a,b in zip(rows[i:i+horizon_bars],rows[i+1:i+1+horizon_bars])):
            eligible+=1
    return {'possible_windows':windows,'assessable_windows':eligible,
            'unresolved_gap_windows':windows-eligible,
            'status':'NOT_EVALUABLE_HISTORY' if not eligible else 'PARTIALLY_EVALUABLE'}

def surge_events(bars, *, threshold_pct, horizon_bars=36, cooldown_bars=36):
    if threshold_pct<=0 or horizon_bars<1 or cooldown_bars<1:
        raise ValueError('positive parameters required')
    rows=sorted(bars,key=lambda x:x['ts'])
    if len({r['ts'] for r in rows})!=len(rows):
        raise ValueError('duplicate timestamps')
    found=[]
    i=0
    # Only actual contiguous 5-minute observations can establish a 3h event.
    # Sparse exchange candles are not interpreted as confirmed non-events.
    while i+horizon_bars<len(rows):
        base=rows[i]
        future=rows[i+1:i+1+horizon_bars]
        # No trades or sparse bars: unknown, not a confirmed negative.
        if any(b['ts']-a['ts']!=300 for a,b in zip(rows[i:i+horizon_bars],rows[i+1:i+1+horizon_bars])):
            i+=1
            continue
        baseline=float(base['close'])
        if baseline<=0:raise ValueError('invalid baseline')
        hit=next((j for j,x in enumerate(future,1)
                  if (float(x['high'])/baseline-1)*100>=threshold_pct),None)
        if hit is not None:
            found.append({'start_ts':base['ts']+300,'hit_ts':future[hit-1]['ts'],
                          'threshold_pct':threshold_pct,'baseline':baseline,
                          'future_high_pct':round((max(float(x['high']) for x in future[:hit])/baseline-1)*100,6)})
            i+=cooldown_bars
        else:i+=1
    return found

def compare_candidates(events,candidate_signal_close_times,*,lead_minutes=5,lookback_minutes=180):
    if lead_minutes<0 or lookback_minutes<=lead_minutes:raise ValueError('invalid lead window')
    signals=sorted(set(int(t) for t in candidate_signal_close_times))
    rows=[]
    for e in events:
        hit=e['hit_ts']
        # Candidate must predate the first threshold hit, and be within the
        # specified lookback window. Candidate close time is the signal time.
        matched=[t for t in signals if hit-lookback_minutes*60<=t<=hit-lead_minutes*60]
        rows.append({**e,'detected':bool(matched),'first_matching_signal_ts':matched[0] if matched else None})
    detected=sum(x['detected'] for x in rows)
    return {'events':len(rows),'detected':detected,
            'recall_pct':round(100*detected/len(rows),2) if rows else None,
            'details':rows,'research_only':True}
