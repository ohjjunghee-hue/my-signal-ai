"""Read-only summaries of historical pre-surge gate diagnostics.

A failed gate count is not evidence that relaxing that gate improves accuracy.
"""
def summarize_missed_surge_gates(diagnostics):
    rows=[]
    totals={}
    for threshold, result in diagnostics.items():
        for event in result.get('records',[]):
            if event.get('status')!='BASE_BUY_MISSED':
                continue
            eligible=int(event.get('eligible_evaluations',0))
            for gate,count in event.get('failed_gate_counts',{}).items():
                count=int(count)
                if eligible<=0 or count<0 or count>eligible:
                    raise ValueError('invalid gate denominator')
                key=(str(threshold),str(gate))
                old=totals.get(key,{'failed':0,'eligible':0,'events':0})
                old['failed']+=count
                old['eligible']+=eligible
                old['events']+=1
                totals[key]=old
    for (threshold,gate),value in sorted(totals.items()):
        rows.append({'threshold_pct':threshold,'gate':gate,
                     'failed_evaluations':value['failed'],
                     'eligible_evaluations':value['eligible'],
                     'failed_pct':round(100*value['failed']/value['eligible'],2),
                     'missed_surge_events_with_gate':value['events']})
    return {'rows':rows,'observational_only':True,
            'warning':'Failure frequency is not causal importance; do not tune BUY thresholds without independent holdout tests.'}
