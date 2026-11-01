"""Run a reproducible, read-only Bithumb historical research sample.

Only publicly available candles; no production DB, secrets, orders or deploys.
Results are observational and must not be called verified live BUY accuracy.
"""
import json
from pathlib import Path
from historical_bithumb_collect import collect
from historical_candidate_audit import evaluate_market
from historical_surge_recall import surge_events, compare_candidates, surge_window_coverage
from historical_trade_outcomes import evaluate_outcomes
from historical_continuity_diagnostics import coverage_report
from historical_snapshot_compare import compare_snapshots
from historical_candle_integrity import validate_candles
from historical_gap_requery import sampled_gap_timestamps, requery_gap
from server import analyze

def classify_recall(comparison, eligible_evaluations, surge_coverage=None):
    """Do not score signal recall when no historical BUY evaluations were possible."""
    if eligible_evaluations == 0 or (surge_coverage is not None and surge_coverage['assessable_windows']==0):
        return {'surge_events':comparison['events'],
                'early_base_buy_candidates':comparison['detected'],
                'recall_pct':None,
                'evaluation_status':'NOT_EVALUABLE_HISTORY'}
    return {'surge_events':comparison['events'],
            'early_base_buy_candidates':comparison['detected'],
            'recall_pct':comparison['recall_pct'],
            'evaluation_status':'PARTIALLY_EVALUABLE' if comparison['events'] else 'NO_SURGE_EVENTS'}

def run(markets=('KRW-BTC','KRW-ETH','KRW-XRP','KRW-SUI','KRW-APT'),count=1000,out_dir='historical_data'):
    dest=Path(out_dir);dest.mkdir(parents=True,exist_ok=True)
    results={}
    for market in markets:
        for unit in (5,15,60):
            rows=collect(market,unit,count)
            (dest/f'{market}_{unit}m.json').write_text(json.dumps(rows),encoding='utf-8')
        snapshot_check=None
        if market in ('KRW-SUI','KRW-APT'):
            # Compare only overlapping timestamps; do not treat shifted windows as gaps.
            second=collect(market,5,min(count,1000))
            first=json.loads((dest/f'{market}_5m.json').read_text())
            snapshot_check=compare_snapshots(first,second)
            (dest/f'{market}_snapshot_comparison.json').write_text(
                json.dumps(snapshot_check,ensure_ascii=False,indent=2),encoding='utf-8')
        gap_requery=None
        if market in ('KRW-SUI','KRW-APT'):
            first=json.loads((dest/f'{market}_5m.json').read_text())
            targets=sampled_gap_timestamps(first,unit=5,limit=3)
            checked=[]
            for ts in targets:
                try:
                    checked.append(requery_gap(market,ts,unit=5))
                except Exception as exc:
                    # An API failure is inconclusive, never evidence of absence.
                    checked.append({'market':market,'missing_ts':ts,'status':'REQUERY_ERROR',
                                    'error_type':type(exc).__name__,'research_only':True})
            gap_requery={'requested':len(targets),'results':checked,
                         'recovered':sum(x['status']=='RECOVERED_BY_REQUERY' for x in checked),
                         'unresolved':sum(x['status']=='UNRESOLVED_AFTER_REQUERY' for x in checked),
                         'errors':sum(x['status']=='REQUERY_ERROR' for x in checked)}
            (dest/f'{market}_gap_requery.json').write_text(
                json.dumps(gap_requery,ensure_ascii=False,indent=2),encoding='utf-8')
        integrity={str(unit):validate_candles(json.loads((dest/f'{market}_{unit}m.json').read_text()),unit)
                   for unit in (5,15,60)}
        (dest/f'{market}_candle_integrity.json').write_text(json.dumps(integrity,ensure_ascii=False,indent=2),encoding='utf-8')
        invalid_units=[unit for unit,check in integrity.items() if check['status']!='VALID']
        if invalid_units:
            raise ValueError(f'{market}: invalid candle data in {invalid_units}; refusing BUY research evaluation')
        audit=evaluate_market(market,dest,analyze,horizon_minutes=180)
        five=json.loads((dest/f'{market}_5m.json').read_text())
        trade_outcomes=evaluate_outcomes(audit['events'],five)
        (dest/f'{market}_trade_outcomes.json').write_text(json.dumps(trade_outcomes,ensure_ascii=False,indent=2),encoding='utf-8')
        signal_times=[e['signal_close_ts'] for e in audit['events'] if e.get('signal_close_ts')]
        surge_coverage=surge_window_coverage(five,horizon_bars=36)
        recalls={}
        for threshold in (3,10,50):
            events=surge_events(five,threshold_pct=threshold,horizon_bars=36,cooldown_bars=36)
            comparison=compare_candidates(events,signal_times,lead_minutes=5,lookback_minutes=180)
            recalls[str(threshold)]=classify_recall(comparison,audit['eligible_evaluations'],surge_coverage)
        continuity={}
        for unit in (5,15,60):
            frame=json.loads((dest/f'{market}_{unit}m.json').read_text())
            gaps=[b['ts']-a['ts'] for a,b in zip(frame,frame[1:]) if b['ts']-a['ts']!=unit*60]
            continuity[str(unit)]={'first_ts':frame[0]['ts'] if frame else None,
                                   'last_ts':frame[-1]['ts'] if frame else None,
                                   'gap_count':len(gaps),
                                   'max_gap_seconds':max(gaps) if gaps else 0}
        coverage={str(unit):coverage_report(json.loads((dest/f'{market}_{unit}m.json').read_text()),unit,289 if unit==5 else 35)
                  for unit in (5,15,60)}
        results[market]={'gap_requery':gap_requery,
                         'surge_window_coverage':surge_coverage,
                         'candle_integrity':{unit:{k:v for k,v in check.items() if k!='invalid'} for unit,check in integrity.items()},
                         'snapshot_comparison':{k:v for k,v in snapshot_check.items() if k!='changed'} if snapshot_check else None,
                         'candle_continuity':continuity,
                         'continuous_window_coverage':{unit:{k:v for k,v in report.items() if k!='segments'} for unit,report in coverage.items()},
                         'history_evaluation_status':'NOT_EVALUABLE_HISTORY' if audit['eligible_evaluations']==0 else 'PARTIALLY_EVALUABLE',
                         'base_buy_candidates':audit['base_buy_events'],
                         'eligible_evaluations':audit['eligible_evaluations'],
                         'insufficient_evaluations':audit['insufficient_evaluations'],
                         'insufficient_reasons':audit['insufficient_reasons'],
                         'status_counts':audit['status_counts'],
                         'buy_gate_fail_counts':audit['buy_gate_fail_counts'],
                         'resolved_candidates':audit['resolved'],
                         'unique_entry_times':audit['unique_entry_times'],
                         'repeated_entry_signals':audit['repeated_entry_signals'],
                         'candidate_episodes':audit['candidate_episodes'],
                         'trade_outcomes':{k:v for k,v in trade_outcomes.items() if k!='trades'},
                         'signals_within_existing_episode':audit['signals_within_existing_episode'],
                         'max_future_high_pct_summary':audit['max_future_high_pct_summary'],
                         'unresolved_candidates':audit['unresolved'],
                         'hit_counts':audit['hit_counts'],
                         'recall':recalls,
                         'candle_counts':{str(unit):len(json.loads((dest/f'{market}_{unit}m.json').read_text())) for unit in (5,15,60)}}
        (dest/f'{market}_continuity_segments.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2),encoding='utf-8')
        (dest/f'{market}_candidate_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    totals={'eligible_evaluations':sum(x['eligible_evaluations'] for x in results.values()),
            'insufficient_evaluations':sum(x['insufficient_evaluations'] for x in results.values()),
            'base_buy_candidates':sum(x['base_buy_candidates'] for x in results.values()),
            'resolved_candidates':sum(x['resolved_candidates'] for x in results.values())}
    report={'research_only':True,'totals':totals,'markets':results,
            'limitations':['base analyze only; V49 gate not reconstructed',
                           'closed-candle proxy 24h return differs from exchange ticker',
                           'max future high is not executable profit',
                           'trade outcomes are simulated with assumed 0.2% costs; no slippage/spread or real fills',
                           'only sampled markets and historical period; not overall recall',
                           'event windows overlap; cooldown is a research assumption',
                           'missing intervals may reflect no-trade candles or API omissions; cause not verified',
                           'repeat snapshot comparison alone cannot establish why an interval is absent',
                           'recall with no eligible historical evaluations is NOT_EVALUABLE, not 0%']}
    (dest/'research_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return report
if __name__=='__main__':run()
