"""Read-only diagnostics of why historical base BUY did not precede a surge.

Gate counts are descriptive, not causal attribution or proof that relaxing a
gate improves returns. Never changes trading thresholds or production signals.
"""
def missed_surge_gate_diagnostics(surge_events, evaluated_signals, *, lead_minutes=5, lookback_minutes=180):
    if lead_minutes<0 or lookback_minutes<=lead_minutes:
        raise ValueError('invalid lead window')
    records=[]
    for event in surge_events:
        hit=int(event['hit_ts'])
        candidates=[s for s in evaluated_signals
                    if hit-lookback_minutes*60<=int(s['close_ts'])<=hit-lead_minutes*60]
        eligible=[s for s in candidates if s.get('status')!='INSUFFICIENT_HISTORY']
        buys=[s for s in eligible if s.get('base_buy_candidate')]
        failures={}
        for row in eligible:
            for gate,passed in row.get('buy_gates',{}).items():
                if passed is False:failures[gate]=failures.get(gate,0)+1
        records.append({'hit_ts':hit,'lookback_evaluations':len(candidates),
                        'eligible_evaluations':len(eligible),'base_buy_signals':len(buys),
                        'failed_gate_counts':failures,
                        'status':'BASE_BUY_PRESENT' if buys else
                                 'NO_ELIGIBLE_LOOKBACK' if not eligible else 'BASE_BUY_MISSED',
                        'causal_claim':False})
    return {'surge_events':len(records),
            'missed_with_eligible_lookback':sum(r['status']=='BASE_BUY_MISSED' for r in records),
            'not_evaluable_lookback':sum(r['status']=='NO_ELIGIBLE_LOOKBACK' for r in records),
            'records':records,'research_only':True}
