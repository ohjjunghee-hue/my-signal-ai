#!/usr/bin/env python3
"""Collect missing Bithumb markets in small resumable shards. Requires all_market_historical_audit.py alongside this file."""
import argparse,csv,json,pathlib,time
from all_market_historical_audit import get,fetch,audit
p=argparse.ArgumentParser();p.add_argument('--shard',type=int,required=True);p.add_argument('--shards',type=int,default=4);p.add_argument('--days',type=int,default=30);a=p.parse_args()
completed=set(json.loads(pathlib.Path('completed_markets.json').read_text()))
all_markets=get('/v1/market/all?isDetails=true')
missing=sorted(x['market'] for x in all_markets if x.get('market','').startswith('KRW-') and str(x.get('market_warning','NONE')).upper() not in ('CAUTION','WARNING') and x['market'] not in completed)
selected=missing[a.shard::a.shards];root=pathlib.Path(f'remaining_shard_{a.shard}');root.mkdir(exist_ok=True)
with (root/'coverage.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['market','unit','candles','events','status','error'])
 for market in selected:
  for unit in (5,15,60):
   try:
    rows=fetch(market,unit,a.days,.2);folder=root/'candles'/str(unit);folder.mkdir(parents=True,exist_ok=True)
    with (folder/(market+'.csv')).open('w',newline='') as out:
     cw=csv.writer(out);cw.writerow(['utc_time','open','high','low','close','volume']);cw.writerows(rows)
    w.writerow([market,unit,len(rows),len(audit(rows,unit)),'OK' if rows else 'EMPTY',''])
   except Exception as e:w.writerow([market,unit,0,0,'ERROR',str(e)[:200]])
  f.flush();print(market,flush=True)
print('Selected markets:',len(selected),'total missing:',len(missing),flush=True)
