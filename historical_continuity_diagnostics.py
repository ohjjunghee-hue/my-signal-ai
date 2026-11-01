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
    return {'unit_minutes':unit_minutes,'required_contiguous_bars':required_bars,
            'total_bars':len(rows),'segment_count':len(segments),
            'longest_segment_bars':max((s['bars'] for s in segments),default=0),
            'eligible_rolling_windows':eligible,
            'segments':segments}
