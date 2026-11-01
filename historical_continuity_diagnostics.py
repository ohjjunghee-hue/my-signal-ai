"""Read-only continuity diagnostics. Never invents missing exchange candles."""
def continuous_segments(rows, unit_minutes):
    if unit_minutes<=0:
        raise ValueError("unit_minutes must be positive")
    ordered=sorted(rows,key=lambda r:r['ts'])
    step=unit_minutes*60
    segments=[]
    start=prev=None
    count=0
    for row in ordered:
        ts=row['ts']
        if prev is not None and ts<=prev:
            raise ValueError("duplicate or nonincreasing timestamps")
        if prev is None or ts-prev!=step:
            if count:
                segments.append({'start_ts':start,'end_ts':prev,'bars':count,
                                 'duration_minutes':count*unit_minutes})
            start=ts
            count=0
        count+=1
        prev=ts
    if count:
        segments.append({'start_ts':start,'end_ts':prev,'bars':count,
                         'duration_minutes':count*unit_minutes})
    return segments

def coverage_report(rows, unit_minutes, required_bars):
    if required_bars<1:
        raise ValueError("required_bars must be positive")
    segments=continuous_segments(rows,unit_minutes)
    eligible=sum(max(0,s['bars']-required_bars+1) for s in segments)
    segment_lengths=sorted((s['bars'] for s in segments),reverse=True)
    ordered=sorted(rows,key=lambda r:r['ts'])
    missing_intervals=sum(max(0,(b['ts']-a['ts'])//(unit_minutes*60)-1) for a,b in zip(ordered,ordered[1:]))
    observed_span_intervals=((ordered[-1]['ts']-ordered[0]['ts'])//(unit_minutes*60)+1) if ordered else 0
    top_segment_lengths=segment_lengths[:5]
    return {'unit_minutes':unit_minutes,'required_contiguous_bars':required_bars,
            'total_bars':len(rows),'segment_count':len(segments),
            'observed_span_intervals':observed_span_intervals,
            'missing_intervals_in_span':missing_intervals,
            'first_ts':ordered[0]['ts'] if ordered else None,
            'last_ts':ordered[-1]['ts'] if ordered else None,
            'longest_segment_bars':max((s['bars'] for s in segments),default=0),
            'eligible_rolling_windows':eligible,
            'top_5_segment_lengths':top_segment_lengths,
            'insufficient_contiguous_bars':max(0,required_bars-(segment_lengths[0] if segment_lengths else 0)),
            'segments':segments}
