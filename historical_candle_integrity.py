"""Read-only integrity checks for historical exchange candles."""
import math

def validate_candles(rows,unit_minutes):
    if unit_minutes<=0:
        raise ValueError('unit_minutes must be positive')
    invalid=[]
    previous=None
    for row in sorted(rows,key=lambda x:x['ts']):
        ts=row['ts']
        problems=[]
        if previous is not None and ts<=previous:
            problems.append('duplicate_or_out_of_order_timestamp')
        previous=ts
        if ts%(unit_minutes*60):
            problems.append('misaligned_timestamp')
        values={}
        for field in ('open','high','low','close','volume'):
            try:
                values[field]=float(row[field])
                if not math.isfinite(values[field]):
                    problems.append('nonfinite_'+field)
            except (KeyError,ValueError,TypeError,OverflowError):
                problems.append('invalid_'+field)
        if len(values)==5 and all(math.isfinite(x) for x in values.values()):
            o,h,l,c,v=(values[k] for k in ('open','high','low','close','volume'))
            if min(o,h,l,c)<=0:
                problems.append('nonpositive_price')
            if v<0:
                problems.append('negative_volume')
            if h<max(o,c,l) or l>min(o,c,h):
                problems.append('invalid_ohlc_range')
        if problems:
            invalid.append({'ts':ts,'problems':problems})
    return {'checked_count':len(rows),'invalid_count':len(invalid),
            'invalid':invalid,'status':'VALID' if not invalid else 'INVALID'}
