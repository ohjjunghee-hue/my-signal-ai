#!/usr/bin/env python3
"""Point-in-time Bithumb research and walk-forward audit. No trade execution.

Historical candle data is *not* historical order-book data. This tool cannot infer
hidden manipulation, guarantee targets, or claim real-time prediction performance.
"""
import argparse, csv, json, math, pathlib, statistics, time, urllib.parse, urllib.request
from datetime import datetime, timezone

BASE='https://api.bithumb.com'
HORIZONS={'12h':48,'1d':96,'3d':288}  # 15-minute bars

def api(path):
    req=urllib.request.Request(BASE+path,headers={'User-Agent':'MY-SIGNAL-RESEARCH/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as r: return json.load(r)

def download(market, days=21, unit=15, pause=.15):
    if not market.startswith('KRW-') or not market[4:].replace('-','').isalnum(): raise ValueError('invalid KRW market')
    if unit!=15:raise ValueError('research features require 15-minute candles')
    end=time.time()-days*86400
    until=None; result={}
    for _ in range(math.ceil(days*96/200)+3):
        query={'market':market,'count':200}
        if until:query['to']=datetime.fromtimestamp(until,timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
        rows=api('/v1/candles/minutes/15?'+urllib.parse.urlencode(query))
        if not isinstance(rows,list) or not rows:break
        oldest=None
        for r in rows:
            try:
                ts=datetime.fromisoformat(r['candle_date_time_utc']+'+00:00').timestamp()
                oldest=ts if oldest is None else min(oldest,ts)
                if ts<end or ts+900>time.time()-3:continue
                o,h,l,c,v=(float(r[k]) for k in ('opening_price','high_price','low_price','trade_price','candle_acc_trade_volume'))
                if min(o,h,l,c)<=0 or v<0 or not all(map(math.isfinite,(o,h,l,c,v))):continue
                if h<max(o,c,l) or l>min(o,c,h):continue
                result[ts]={'t':int(ts),'o':o,'h':h,'l':l,'c':c,'v':v}
            except (KeyError,ValueError,TypeError):continue
        if oldest is None or oldest<=end or (until and oldest>=until):break
        until=oldest-1
        time.sleep(pause)
    return sorted(result.values(),key=lambda x:x['t'])

def feature_at(candles,i):
    """All inputs end at i, the already-closed decision candle."""
    if i<96:return None
    a=candles; p=a[i]['c']; prev=a[i-20:i]; recent=a[i-8:i+1]
    if any(a[j+1]['t']-a[j]['t']!=900 for j in range(i-96,i)):return None
    if min(x['c'] for x in a[i-96:i+1])<=0:return None
    vol_base=statistics.mean(x['v'] for x in a[i-20:i])
    vol_ratio=a[i]['v']/max(vol_base,1e-12)
    high20=max(x['h'] for x in prev); low20=min(x['l'] for x in prev)
    compression=(high20-low20)/p*100
    ma5=statistics.mean(x['c'] for x in a[i-4:i+1]); ma20=statistics.mean(x['c'] for x in a[i-19:i+1])
    ma96=statistics.mean(x['c'] for x in a[i-95:i+1])
    change1h=(p/a[i-4]['c']-1)*100; change24=(p/a[i-96]['c']-1)*100
    breakout=p>high20; trend=ma5>ma20 and p>ma96
    candle_strength=(p-a[i]['l'])/max(a[i]['h']-a[i]['l'],1e-12)
    # No future outcomes are used to decide the signal.
    signal=bool(trend and 1.3<=vol_ratio<=8 and compression<=12 and -2<=change1h<=5 and change24<=12 and candle_strength>=.6 and (breakout or p>=high20*.985))
    return {'t':a[i]['t']+900,'entry':p,'vol_ratio':round(vol_ratio,3),'compression_pct':round(compression,3),
            'change1h_pct':round(change1h,3),'change24_pct':round(change24,3),'breakout':int(breakout),
            'trend':int(trend),'signal':int(signal)}

def examples(market,candles,horizon=48,step=4):
    """Decision at candle close, evaluation begins on the *next* candle."""
    out=[]
    for i in range(96,len(candles)-horizon,step):
        f=feature_at(candles,i)
        if f is None:continue
        future=candles[i+1:i+1+horizon]
        if len(future)!=horizon or any(future[j+1]['t']-future[j]['t']!=900 for j in range(len(future)-1)):continue
        high=max(x['h'] for x in future);low=min(x['l'] for x in future)
        row={'market':market,'horizon_bars':horizon,**f,'max_gain_pct':round((high/f['entry']-1)*100,3),
             'max_drawdown_pct':round((low/f['entry']-1)*100,3)}
        for target in (3,10,50):row[f'hit_{target}pct']=int(high>=f['entry']*(1+target/100))
        out.append(row)
    return out

def metrics(rows):
    if not rows:return {'samples':0,'signals':0,'note':'데이터 부족'}
    selected=[x for x in rows if x['signal']]; result={'samples':len(rows),'signals':len(selected),'signal_rate_pct':round(100*len(selected)/len(rows),2)}
    for pct in (3,10,50):
        k=f'hit_{pct}pct';result[f'{pct}pct_signal_hit_rate']=round(100*sum(x[k] for x in selected)/len(selected),2) if selected else None
        result[f'{pct}pct_all_market_base_rate']=round(100*sum(x[k] for x in rows)/len(rows),2)
    if selected:result['signal_median_max_gain_pct']=round(statistics.median(x['max_gain_pct'] for x in selected),2)
    return result

def evaluate(rows,split=.7):
    # Chronological holdout; embargo removes training samples whose outcome
    # extends into the validation window.
    if not rows:return {'train':metrics([]),'test':metrics([])}
    rows=sorted(rows,key=lambda x:x['t']);times=sorted(set(x['t'] for x in rows))
    boundary=times[min(len(times)-1,max(0,int(len(times)*split)))]
    train=[r for r in rows if r['t']+r['horizon_bars']*900<boundary]
    test=[r for r in rows if r['t']>=boundary]
    return {'split_utc':datetime.fromtimestamp(boundary,timezone.utc).isoformat(),'train':metrics(train),'test':metrics(test),
            'note':'기준 규칙은 고정된 연구용 규칙. 같은 시각의 다수 종목 및 겹치는 구간은 독립 표본이 아니므로 통계적 확신을 과대평가하지 말 것.'}

def run(argv=None):
    p=argparse.ArgumentParser(description='Bithumb closed-candle historical research; no trades')
    p.add_argument('--markets',nargs='+',required=True);p.add_argument('--days',type=int,default=21)
    p.add_argument('--horizon',choices=HORIZONS,default='12h');p.add_argument('--output',default='research_results')
    p.add_argument('--input-dir',help='Use pre-downloaded JSON candle arrays; avoids network and supports reproducibility')
    args=p.parse_args(argv)
    if not 4<=args.days<=90: p.error('--days must be between 4 and 90')
    out=pathlib.Path(args.output);out.mkdir(parents=True,exist_ok=True)
    rows=[];coverage=[]
    for market in args.markets:
        try:
            if args.input_dir: candles=json.loads((pathlib.Path(args.input_dir)/(market+'.json')).read_text())
            else:candles=download(market,args.days)
            (out/(market+'.json')).write_text(json.dumps(candles,ensure_ascii=False))
            r=examples(market,candles,HORIZONS[args.horizon]);rows.extend(r)
            coverage.append({'market':market,'candles':len(candles),'evaluated':len(r),'first':candles[0]['t'] if candles else None,'last':candles[-1]['t'] if candles else None})
        except Exception as e:coverage.append({'market':market,'error':str(e)[:200]})
    if rows:
        with (out/'examples.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    report={'method':'closed 15m candles; 1h-spaced decisions; forward high/low labels; chronological embargoed holdout',
            'horizon':args.horizon,'coverage':coverage,'evaluation':evaluate(rows),
            'limitations':['15m candles cannot establish 3m/5m entry timing','historical order-book and individual trades unavailable',
                           'high/low labels are hypothetical and not executable trade returns','historical data gaps excluded',
                           'sample selection and exchange listing history may bias results','do not interpret targets as forecast probabilities']}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2));return report

if __name__=='__main__':run()
