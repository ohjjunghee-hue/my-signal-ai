#!/usr/bin/env python3
"""Point-in-time signal quality and downside audit for saved research examples.
No execution, predictions or guarantees. Standard library only.
"""
import argparse,csv,json,math,pathlib,statistics
from collections import defaultdict

def finite(x):
    try:
        y=float(x);return y if math.isfinite(y) else None
    except (ValueError,TypeError):return None

def audit(rows,fee_bps=20,stop_pct=4):
    """Non-overlapping per-market decision events; conservative intrabar ordering.
    Max/min forward excursions are *not* sufficient to infer exact TP-before-stop;
    ambiguous cases are marked unknown rather than called winners.
    """
    if not 0<=fee_bps<=200 or not 0<stop_pct<=50:raise ValueError('invalid costs or stop')
    valid=[]; invalid=0
    for r in rows:
        try:
            market=str(r['market']);t=int(float(r['t']));h=int(float(r['horizon_bars']))
            gain=finite(r['max_gain_pct']);draw=finite(r['max_drawdown_pct']);sig=int(float(r['signal']))
            if not market or h<1 or gain is None or draw is None or sig not in (0,1):raise ValueError
            valid.append((market,t,h,gain,draw,sig))
        except (KeyError,ValueError,TypeError):invalid+=1
    by_market=defaultdict(list)
    for v in valid:by_market[v[0]].append(v)
    events=[]
    for market,items in by_market.items():
        until=-1
        for _,t,h,gain,draw,sig in sorted(items,key=lambda x:x[1]):
            if not sig or t<until:continue
            until=t+h*900
            event={'market':market,'t':t,'horizon_bars':h,'max_gain_pct':gain,'max_drawdown_pct':draw,'stop_touched':draw<=-stop_pct}
            for target in (3,10,20,50):
                touched=gain>=target
                event[f'target_{target}_touched']=touched
                event[f'target_{target}_before_stop']='unknown' if touched and draw<=-stop_pct else ('possible' if touched else 'no')
            events.append(event)
    total=len(events); cost=2*fee_bps/100
    result={'evaluated_rows':len(valid),'invalid_rows':invalid,'nonoverlapping_signals':total,'assumed_round_trip_cost_pct':round(cost,4),'stop_pct':stop_pct,
            'warning':'Target touches are not executed returns. When stop and target both touched, ordering is unknown.'}
    for target in (3,10,20,50):
        touched=sum(e[f'target_{target}_touched'] for e in events)
        ambiguous=sum(e[f'target_{target}_before_stop']=='unknown' for e in events)
        result[f'target_{target}']={'touches':touched,'touch_rate_pct':round(touched/total*100,2) if total else None,
                                    'ambiguous_stop_order':ambiguous,'unambiguous_possible':touched-ambiguous,
                                    'net_target_after_cost_pct':round(target-cost,4)}
    result['stop_touched']=sum(e['stop_touched'] for e in events)
    result['median_max_gain_pct']=round(statistics.median(e['max_gain_pct'] for e in events),3) if events else None
    result['median_max_drawdown_pct']=round(statistics.median(e['max_drawdown_pct'] for e in events),3) if events else None
    return result,events

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--examples',required=True);p.add_argument('--output',default='audit_results')
    p.add_argument('--fee-bps',type=float,default=20);p.add_argument('--stop-pct',type=float,default=4)
    a=p.parse_args(argv);out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True)
    with open(a.examples,encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    report,events=audit(rows,a.fee_bps,a.stop_pct)
    (out/'risk_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if events:
        with (out/'nonoverlapping_signals.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=events[0].keys());w.writeheader();w.writerows(events)
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
