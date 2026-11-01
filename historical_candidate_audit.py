"""Offline historical candidate audit. Never writes to the production database.

Input directory contains KRW-XXX_{5,15,60}m.json from historical_bithumb_collect.
Output distinguishes base BUY candidates from final live BUY; this is not a
strategy performance estimate or evidence of actual execution.
"""
import argparse
import json
from pathlib import Path
from historical_buy_adapter import historical_base_signal

def evaluate_market(market, data_dir, analyzer, *, horizon_minutes=180):
    if horizon_minutes<5:raise ValueError('horizon_minutes must be >=5')
    base=Path(data_dir)
    candles={unit:json.loads((base/f'{market}_{unit}m.json').read_text(encoding='utf-8'))
             for unit in (5,15,60)}
    five=sorted(candles[5],key=lambda r:r['ts'])
    if len({r['ts'] for r in five})!=len(five):raise ValueError('duplicate 5m candle')
    events=[]
    status_counts={}
    gate_fail_counts={}
    eligible_evaluations=0
    insufficient_evaluations=0
    insufficient_reasons={}
    for i in range(len(five)-1):
        bar=five[i]
        close_ts=bar['ts']+300
        r=historical_base_signal(analyzer,candles[5],candles[15],candles[60],close_ts)
        if r.get('status')=='INSUFFICIENT_HISTORY':
            insufficient_evaluations+=1
            reason=r.get('reason','unknown')
            insufficient_reasons[reason]=insufficient_reasons.get(reason,0)+1
            continue
        eligible_evaluations+=1
        status_counts[r['status']]=status_counts.get(r['status'],0)+1
        for gate,passed in r.get('buy_gates',{}).items():
            if not passed:gate_fail_counts[gate]=gate_fail_counts.get(gate,0)+1
        if not r.get('base_buy_candidate'):continue
        # The reference price is the next bar OPEN, never the signal bar close.
        next_bar=five[i+1]
        if next_bar['ts']!=close_ts:
            events.append({'signal_close_ts':close_ts,'status':'UNRESOLVED_GAP'})
            continue
        entry=float(next_bar['open'])
        if entry<=0:raise ValueError('invalid entry')
        window=[x for x in five[i+1:] if 0<=x['ts']-close_ts<horizon_minutes*60]
        if not window or window[-1]['ts']+300<close_ts+horizon_minutes*60:
            events.append({'signal_close_ts':close_ts,'status':'UNRESOLVED_HORIZON'})
            continue
        if any(b['ts']-a['ts']!=300 for a,b in zip(window,window[1:])):
            events.append({'signal_close_ts':close_ts,'status':'UNRESOLVED_GAP'})
            continue
        max_high=max(float(x['high']) for x in window)
        max_gain_pct=round((max_high/entry-1)*100,6)
        events.append({'signal_close_ts':close_ts,'entry_ts':next_bar['ts'],
                       'entry_reference':entry,'max_future_high_pct':max_gain_pct,
                       'reached_3pct':max_gain_pct>=3,'reached_10pct':max_gain_pct>=10,
                       'reached_50pct':max_gain_pct>=50,'status':'RESOLVED',
                       'reconstructed':True,'final_live_buy_verified':False})
    resolved=[e for e in events if e['status']=='RESOLVED']
    gains=[e['max_future_high_pct'] for e in resolved]
    return {'market':market,'horizon_minutes':horizon_minutes,
            'base_buy_events':len(events),'eligible_evaluations':eligible_evaluations,
            'insufficient_evaluations':insufficient_evaluations,
            'insufficient_reasons':insufficient_reasons,
            'status_counts':status_counts,'buy_gate_fail_counts':gate_fail_counts,
            'resolved':len(resolved),
            'max_future_high_pct_summary':{'min':min(gains) if gains else None,
                                           'mean':round(sum(gains)/len(gains),6) if gains else None,
                                           'max':max(gains) if gains else None},
            'unresolved':len(events)-len(resolved),
            'hit_counts':{str(k):sum(e[f'reached_{k}pct'] for e in resolved) for k in (3,10,50)},
            'events':events,'disclaimer':'Base BUY reconstruction only; not actual BUY logs, not fills, not full live V49 gate.'}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--market',required=True)
    p.add_argument('--data-dir',default='historical_data')
    p.add_argument('--output',default='historical_audit.json')
    p.add_argument('--horizon-minutes',type=int,default=180)
    a=p.parse_args()
    if not a.market.startswith('KRW-'):raise ValueError('KRW markets only')
    from server import analyze
    result=evaluate_market(a.market,a.data_dir,analyze,horizon_minutes=a.horizon_minutes)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='events'},ensure_ascii=False))
if __name__=='__main__':main()
