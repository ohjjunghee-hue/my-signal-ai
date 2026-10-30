#!/usr/bin/env python3
"""Bithumb KRW universe OHLCV archive and descriptive event audit. No lookahead signal claims."""
import argparse,csv,json,time,urllib.request,urllib.parse,datetime,math,pathlib,collections
BASE='https://api.bithumb.com'
def get(path):
 for attempt in range(6):
  try:
   req=urllib.request.Request(BASE+path,headers={'User-Agent':'MY-SIGNAL-HISTORICAL-AUDIT/1.0'})
   with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
  except Exception:
   if attempt==5:raise
   time.sleep(min(20,2**attempt))
def fetch(market,unit,days,delay):
 end=datetime.datetime.now(datetime.timezone.utc)
 start=end-datetime.timedelta(days=days);seen={};oldest=None
 for page in range(max(1,math.ceil(days*24*60/unit/200)+3)):
  q={'market':market,'count':200}
  if oldest:q['to']=oldest.strftime('%Y-%m-%dT%H:%M:%S')
  raw=get('/v1/candles/minutes/'+str(unit)+'?'+urllib.parse.urlencode(q))
  if not isinstance(raw,list) or not raw:break
  earliest=None
  for x in raw:
   try:
    dt=datetime.datetime.fromisoformat(x['candle_date_time_utc']).replace(tzinfo=datetime.timezone.utc)
    if earliest is None or dt<earliest:earliest=dt
    if dt<start or dt+datetime.timedelta(minutes=unit)>end:continue
    o,h,l,c,v=[float(x[k]) for k in ('opening_price','high_price','low_price','trade_price','candle_acc_trade_volume')]
    if not all(map(math.isfinite,(o,h,l,c,v))) or min(o,h,l,c)<=0 or v<0 or h<max(o,c,l) or l>min(o,c,h):continue
    seen[dt.isoformat()]=(dt.isoformat(),o,h,l,c,v)
   except (ValueError,KeyError,TypeError):continue
  if earliest is None or earliest<=start or (oldest is not None and earliest>=oldest):break
  oldest=earliest;time.sleep(delay)
 return [seen[k] for k in sorted(seen)]
def audit(rows,unit):
 out=[]; windows=[max(1,round(x/unit)) for x in (5,15,60,1440,4320)]
 for i in range(1,len(rows)):
  t,o,h,l,c,v=rows[i];p=rows[i-1][4];ret=(c/p-1)*100
  if abs(ret)>=3:out.append([t,'CANDLE',round(ret,4),round(v,5),'single closed candle'])
  for minutes,n in zip((5,15,60,1440,4320),windows):
   if i>=n:
    r=(c/rows[i-n][4]-1)*100
    if abs(r)>=10 and (i==n or (r>=10 and (rows[i-1][4]/rows[i-1-n][4]-1)*100<10) or (r<=-10 and (rows[i-1][4]/rows[i-1-n][4]-1)*100>-10)):
     out.append([t,str(minutes)+'m',round(r,4),round(v,5),'threshold crossing; overlapping windows possible'])
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--days',type=int,default=30);ap.add_argument('--units',default='5,15,60');ap.add_argument('--delay',type=float,default=.15);ap.add_argument('--output',default='historical_audit');args=ap.parse_args()
 root=pathlib.Path(args.output);root.mkdir(parents=True,exist_ok=True)
 markets=get('/v1/market/all?isDetails=true');eligible=[x for x in markets if x.get('market','').startswith('KRW-') and str(x.get('market_warning','NONE')).upper() not in ('CAUTION','WARNING')]
 (root/'market_universe.json').write_text(json.dumps(eligible,ensure_ascii=False,indent=2),encoding='utf8')
 summary=[]
 with (root/'events.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.writer(f);w.writerow(['market','unit_minutes','utc_time','event_window','change_pct','volume','note'])
  for idx,m in enumerate(eligible,1):
   market=m['market']
   for unit in map(int,args.units.split(',')):
    try:
     rows=fetch(market,unit,args.days,args.delay)
     path=root/'candles'/str(unit);path.mkdir(parents=True,exist_ok=True)
     with (path/(market+'.csv')).open('w',newline='',encoding='utf-8-sig') as out:
      cw=csv.writer(out);cw.writerow(['utc_time','open','high','low','close','volume']);cw.writerows(rows)
     events=audit(rows,unit)
     for e in events:w.writerow([market,unit,*e])
     summary.append({'market':market,'unit':unit,'candles':len(rows),'events':len(events),'status':'OK' if rows else 'EMPTY'})
    except Exception as e:summary.append({'market':market,'unit':unit,'status':'ERROR','error':str(e)[:240]})
   print(f'{idx}/{len(eligible)} {market}',flush=True)
 with (root/'coverage.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=['market','unit','candles','events','status','error']);w.writeheader();w.writerows(summary)
 print('Coverage:',sum(x['status']=='OK' for x in summary),'/',len(summary),'market-timeframe pairs')
if __name__=='__main__':main()
