"""Read-only cross-timeframe evidence for missing 5-minute Bithumb candles.

A 15-minute aggregate cannot prove whether a particular 5-minute candle
existed, even when aggregate volume is positive. Never synthesize candles.
"""
def cross_timeframe_gap_evidence(missing_timestamps, five_rows, fifteen_rows):
    five={int(x['ts']):x for x in five_rows}
    fifteen={int(x['ts']):x for x in fifteen_rows}
    results=[]
    fifteen_bounds=(min(fifteen),max(fifteen)) if fifteen else None
    for ts in missing_timestamps:
        ts=int(ts)
        if ts%300:raise ValueError('missing timestamp not 5-minute aligned')
        bucket=ts-ts%900
        aggregate=fifteen.get(bucket)
        existing=[t for t in (bucket,bucket+300,bucket+600) if t in five]
        if fifteen_bounds is None or not (fifteen_bounds[0]<=bucket<=fifteen_bounds[1]):
            status='OUTSIDE_15M_HISTORY'
        elif aggregate is None:
            status='NO_15M_AGGREGATE'
        elif len(existing)==3:
            status='ALL_5M_PRESENT'
        else:
            status='15M_PRESENT_5M_INCOMPLETE'
        results.append({'missing_ts':ts,'bucket_15m_ts':bucket,
                        'status':status,'known_5m_count':len(existing),
                        'aggregate_volume':aggregate.get('volume') if aggregate else None,
                        'proof_of_missing_cause':False})
    return {'checked':len(results),'results':results,
            'note':'15m aggregate cannot identify the cause of an absent 5m candle; no synthetic bars.'}
