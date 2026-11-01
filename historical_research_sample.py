"""Run a reproducible, read-only Bithumb historical research sample.

Only publicly available candles; no production DB, secrets, orders or deploys.
Results are observational and must not be called verified live BUY accuracy.
"""
import json
from pathlib import Path
from historical_bithumb_collect import collect
from historical_candidate_audit import evaluate_market
from historical_surge_recall import surge_events, compare_candidates
from server import analyze

def run(markets=('KRW-BTC','KRW-ETH','KRW-XRP','KRW-SUI','KRW-APT'),count=1000,out_dir='historical_data'):
    dest=Path(out_dir);dest.mkdir(parents=True,exist_ok=True)
    results={}
    for market in markets:
        for unit in (5,15,60):
            rows=collect(market,unit,count)
            (dest/f'{market}_{unit}m.json').write_text(json.dumps(rows),encoding='utf-8')
        audit=evaluate_market(market,dest,analyze,horizon_minutes=180)
        five=json.loads((dest/f'{market}_5m.json').read_text())
        signal_times=[e['signal_close_ts'] for e in audit['events'] if e.get('signal_close_ts')]
        recalls={}
        for threshold in (3,10,50):
            events=surge_events(five,threshold_pct=threshold,horizon_bars=36,cooldown_bars=36)
            comparison=compare_candidates(events,signal_times,lead_minutes=5,lookback_minutes=180)
            recalls[str(threshold)]={'surge_events':comparison['events'],
                                    'early_base_buy_candidates':comparison['detected'],
                                    'recall_pct':comparison['recall_pct']}
        continuity={}
        for unit in (5,15,60):
            frame=json.loads((dest/f'{market}_{unit}m.json').read_text())
            gaps=[b['ts']-a['ts'] for a,b in zip(frame,frame[1:]) if b['ts']-a['ts']!=unit*60]
            continuity[str(unit)]={'first_ts':frame[0]['ts'] if frame else None,
                                   'last_ts':frame[-1]['ts'] if frame else None,
                                   'gap_count':len(gaps),
                                   'max_gap_seconds':max(gaps) if gaps else 0}
        results[market]={'candle_continuity':continuity,
                         'base_buy_candidates':audit['base_buy_events'],
                         'eligible_evaluations':audit['eligible_evaluations'],
                         'insufficient_evaluations':audit['insufficient_evaluations'],
                         'status_counts':audit['status_counts'],
                         'buy_gate_fail_counts':audit['buy_gate_fail_counts'],
                         'resolved_candidates':audit['resolved'],
                         'unresolved_candidates':audit['unresolved'],
                         'hit_counts':audit['hit_counts'],
                         'recall':recalls,
                         'candle_counts':{str(unit):len(json.loads((dest/f'{market}_{unit}m.json').read_text())) for unit in (5,15,60)}}
        (dest/f'{market}_candidate_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'research_only':True,'markets':results,
            'limitations':['base analyze only; V49 gate not reconstructed',
                           'closed-candle proxy 24h return differs from exchange ticker',
                           'max future high is not executable profit',
                           'only sampled markets and historical period; not overall recall',
                           'event windows overlap; cooldown is a research assumption']}
    (dest/'research_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return report
if __name__=='__main__':run()
