"""Read-only targeted requery of missing 5-minute candle timestamps.

A missing timestamp in the returned API page remains UNRESOLVED; it is not
proof of zero trades. Never fill absent bars or use these as trade signals.
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from historical_bithumb_collect import API

KST=timezone(timedelta(hours=9))

def gap_timestamps(rows, *, unit=5, limit=10):
    if unit not in (5,15,60) or limit<1:
        raise ValueError('invalid unit or limit')
    times=sorted({int(x['ts']) for x in rows})
    gaps=[]
    for a,b in zip(times,times[1:]):
        for ts in range(a+unit*60,b,unit*60):
            gaps.append(ts)
            if len(gaps)>=limit:return gaps
    return gaps

def sampled_gap_timestamps(rows, *, unit=5, limit=3):
    """Choose gaps across the time range, not only the oldest missing bars."""
    if unit not in (5,15,60) or limit<1:
        raise ValueError('invalid unit or limit')
    times=sorted({int(x['ts']) for x in rows})
    spans=[(a,b) for a,b in zip(times,times[1:]) if b-a>unit*60]
    if not spans:return []
    # Choose spread-out missing intervals with bounded memory and requests.
    positions=sorted({(i*(len(spans)-1))//max(1,limit-1) for i in range(limit)})
    return [spans[i][0]+unit*60 for i in positions][:limit]

def requery_gap(market, missing_ts, *, unit=5, opener=None):
    if not market.startswith('KRW-') or unit not in (5,15,60):
        raise ValueError('invalid market or unit')
    if missing_ts%(unit*60):
        raise ValueError('misaligned missing timestamp')
    # Query just after the missing candle's opening time, so that the
    # exchange can return it if it exists. Presence must match exact UTC ts.
    cursor=datetime.fromtimestamp(missing_ts+unit*60,KST).strftime('%Y-%m-%dT%H:%M:%S')
    url=API+str(unit)+'?'+urllib.parse.urlencode({'market':market,'count':2,'to':cursor})
    request=opener or urllib.request.urlopen
    with request(urllib.request.Request(url,headers={'User-Agent':'MY-SIGNAL-gap-audit/1.0'}),timeout=20) as resp:
        payload=json.load(resp)
    if not isinstance(payload,list):raise ValueError('unexpected candle response')
    returned=[int(datetime.fromisoformat(x['candle_date_time_utc']).replace(tzinfo=timezone.utc).timestamp()) for x in payload]
    return {'market':market,'missing_ts':missing_ts,'returned_ts':returned,
            'status':'RECOVERED_BY_REQUERY' if missing_ts in returned else 'UNRESOLVED_AFTER_REQUERY',
            'research_only':True}
