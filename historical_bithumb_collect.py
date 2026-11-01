"""Read-only Bithumb candle collection for offline historical BUY research.

Usage: python historical_bithumb_collect.py --markets KRW-BTC KRW-ETH --count 200 --output-dir historical_data
No orders, no API keys, no production database access. API may omit empty intervals.
"""
import argparse
import json
import pathlib
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

API='https://api.bithumb.com/v1/candles/minutes/'

def collect(market, unit, count=200, *, opener=None, pause=0.15):
    if unit not in (5,15,60):raise ValueError('unsupported unit')
    if not market.startswith('KRW-'):raise ValueError('KRW markets only')
    if not 1<=count<=2000:raise ValueError('count outside 1..2000')
    request=opener or urllib.request.urlopen
    result={}
    before=None
    while len(result)<count:
        params={'market':market,'count':min(200,count-len(result))}
        if before:params['to']=before
        url=API+str(unit)+'?'+urllib.parse.urlencode(params)
        with request(urllib.request.Request(url,headers={'User-Agent':'MY-SIGNAL-historical-research/1.0'}),timeout=20) as resp:
            payload=json.load(resp)
        if not isinstance(payload,list):raise ValueError('unexpected candle response')
        if not payload:break
        oldest=None
        for x in payload:
            stamp=x['candle_date_time_utc']
            dt=datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
            ts=int(dt.timestamp())
            oldest=ts if oldest is None else min(oldest,ts)
            bar={'ts':ts,'duration_sec':unit*60,
                 'open':float(x['opening_price']),'high':float(x['high_price']),
                 'low':float(x['low_price']),'close':float(x['trade_price']),
                 'volume':float(x['candle_acc_trade_volume'])}
            if ts+unit*60<=time.time():result[ts]=bar
        if oldest is None:break
        # Bithumb's `to` parameter is interpreted in KST even though
        # response candle_date_time_utc is UTC. Convert cursor explicitly.
        next_before=datetime.fromtimestamp(oldest,timezone(timedelta(hours=9))).strftime('%Y-%m-%dT%H:%M:%S')
        if before==next_before:break
        before=next_before
        # Short pages can be valid when historical intervals have no trades.
        # Continue pagination until no progress or the API returns no bars.
        time.sleep(pause)
    rows=sorted(result.values(),key=lambda x:x['ts'])[-count:]
    # Keep authentic candles and let downstream research reject only windows
    # that cross gaps. Never synthesize no-trade candles or fabricate prices.
    return rows

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--markets',nargs='+',default=['KRW-BTC','KRW-ETH'])
    p.add_argument('--count',type=int,default=1000)
    p.add_argument('--output-dir',default='historical_data')
    args=p.parse_args()
    out=pathlib.Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    report={'source':'Bithumb public candles','retrieved_utc':datetime.now(timezone.utc).isoformat(),
            'research_only':True,'markets':{}}
    for market in args.markets:
        if not market.startswith('KRW-') or not market[4:].replace('-','').isalnum():
            raise ValueError('invalid market')
        report['markets'][market]={}
        for unit in (5,15,60):
            rows=collect(market,unit,args.count)
            (out/f'{market}_{unit}m.json').write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
            report['markets'][market][str(unit)]={'count':len(rows),
                'first_ts':rows[0]['ts'] if rows else None,
                'last_ts':rows[-1]['ts'] if rows else None}
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
