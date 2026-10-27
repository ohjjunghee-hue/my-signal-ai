#!/usr/bin/env python3
"""Conservative candle-by-candle event validation and missed-surge audit.

Research-only: candles do not reveal trade execution or intra-candle ordering.
"""
import argparse, json, pathlib, statistics
from collections import defaultdict
from research_engine import feature_at

def evaluate_trade(candles, index, horizon=48, stop_pct=4.0, targets=(3,10,20,50), fee_bps=20):
    if not 0 < stop_pct < 50 or not 0 <= fee_bps <= 200: raise ValueError('invalid risk settings')
    if index < 0 or index >= len(candles) or horizon < 1: raise ValueError('invalid index or horizon')
    entry=float(candles[index]['c']); start=candles[index]['t']+900
    result={'entry':entry,'signal_time':start,'horizon_bars':horizon,'stop_pct':stop_pct,'round_trip_cost_pct':fee_bps*2/100,
            'targets':{},'stop_time':None,'max_gain_pct':None,'max_drawdown_pct':None,'complete':False}
    future=candles[index+1:index+1+horizon]
    if len(future)!=horizon or any(x['t']!=start+900*j for j,x in enumerate(future)):return result
    result['complete']=True
    result['max_gain_pct']=round((max(x['h'] for x in future)/entry-1)*100,3)
    result['max_drawdown_pct']=round((min(x['l'] for x in future)/entry-1)*100,3)
    stop=entry*(1-stop_pct/100)
    first_stop=next((x['t'] for x in future if x['l']<=stop),None)
    result['stop_time']=first_stop
    for target in targets:
        hit=entry*(1+target/100)
        first_hit=next((x['t'] for x in future if x['h']>=hit),None)
        if first_hit is None:status='not_reached'
        elif first_stop is None or first_hit<first_stop:status='target_first'
        elif first_hit==first_stop:status='ambiguous_same_candle'
        else:status='stop_first'
        result['targets'][str(target)]={'status':status,'first_hit_time':first_hit,
            'net_target_pct_if_executed':round(target-fee_bps*2/100,3)}
    return result

def study_market(market,candles,horizon=48,stop_pct=4,fee_bps=20,step=4):
    """Report signal events and missed surges, avoiding overlapping evaluation windows.

    Missed events are defined from a *fixed pre-event* decision time; no lookahead
    is used to select features. This is a retrospective audit, not a live hit rate.
    """
    candles=sorted(candles,key=lambda c:c['t']);events=[];missed=[]; last_signal_end=-1
    for i in range(96,len(candles)-horizon,step):
        f=feature_at(candles,i)
        if f is None:continue
        e=evaluate_trade(candles,i,horizon,stop_pct,fee_bps=fee_bps)
        if not e['complete']:continue
        if f['signal'] and f['t']>=last_signal_end:
            events.append({'market':market,'features':f,'outcome':e})
            last_signal_end=f['t']+horizon*900
        # Non-overlapping retrospective 10%+ opportunity audit; not a trade return.
        if i % horizon == 0 and e['max_gain_pct']>=10 and not f['signal']:
            missed.append({'market':market,'decision_time':f['t'],'entry':f['entry'],
                           'future_max_gain_pct':e['max_gain_pct'],
                           'why_not_signaled':{k:f[k] for k in ('vol_ratio','compression_pct','change1h_pct','change24_pct','breakout','trend')}})
    return events,missed

def report(markets,horizon=48):
    all_events=[];all_missed=[];coverage=[]
    for market,candles in markets.items():
        try:
            ev,mi=study_market(market,candles,horizon)
            all_events.extend(ev);all_missed.extend(mi)
            coverage.append({'market':market,'candles':len(candles),'signals':len(ev),'missed_10pct_windows':len(mi)})
        except Exception as ex:coverage.append({'market':market,'error':str(ex)})
    outcome={ 'method':'Closed 15m candles, signal at candle close, future begins next candle',
      'coverage':coverage,'signal_events':len(all_events),'missed_10pct_windows':len(all_missed),
      'limitations':['Missed 10% windows are sampled and overlap across markets; not exhaustive daily misses',
                     'OHLC cannot resolve intrabar order; ambiguous results are not wins',
                     'Future maximum price is not executable profit',
                     '15m data cannot prove 3m early entry or historical order-book behavior']}
    for target in ('3','10','20','50'):
        statuses=[x['outcome']['targets'][target]['status'] for x in all_events]
        outcome['target_'+target]={'target_first':statuses.count('target_first'),
          'stop_first':statuses.count('stop_first'), 'ambiguous':statuses.count('ambiguous_same_candle'),
          'not_reached':statuses.count('not_reached'),
          'target_first_rate_pct':round(100*statuses.count('target_first')/len(statuses),2) if statuses else None}
    return outcome,all_events,all_missed

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--input-dir',required=True);p.add_argument('--output',default='validation_results')
    p.add_argument('--horizon',type=int,choices=[48,96,288],default=48)
    a=p.parse_args(argv);markets={}
    for file in pathlib.Path(a.input_dir).glob('KRW-*.json'):
        markets[file.stem]=json.loads(file.read_text(encoding='utf-8'))
    result,events,missed=report(markets,a.horizon)
    out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True)
    for name,obj in [('validation_report.json',result),('signal_events.json',events),('missed_surges.json',missed)]:
        (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
