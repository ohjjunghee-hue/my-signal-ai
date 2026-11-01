"""Read-only comparison of repeated Bithumb candle snapshots.

Compare the overlapping historical timestamps only; absence from a later
snapshot can reflect a shifted collection window, not a deleted candle.
No orders, synthetic bars, production data or network calls here.
"""
def compare_snapshots(first, second):
    def indexed(rows):
        result={}
        for row in rows:
            ts=row['ts']
            if ts in result:
                raise ValueError('duplicate candle timestamp')
            result[ts]=row
        return result
    a=indexed(first)
    b=indexed(second)
    common=sorted(a.keys() & b.keys())
    fields=('open','high','low','close','volume')
    changed=[]
    for ts in common:
        differences=[field for field in fields if a[ts].get(field)!=b[ts].get(field)]
        if differences:
            changed.append({'ts':ts,'fields':differences})
    return {'first_count':len(a),'second_count':len(b),
            'overlap_count':len(common),'changed_count':len(changed),
            'changed':changed,
            'only_first_count':len(a.keys()-b.keys()),
            'only_second_count':len(b.keys()-a.keys()),
            'comparison_status':'NO_OVERLAP' if not common else
                ('CHANGED_OVERLAP' if changed else 'MATCHED_OVERLAP'),
            'note':'Nonoverlapping timestamps are not proof of missing exchange candles.'}
