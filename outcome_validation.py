"""V45 forward-only observed signal outcomes. No candle interpolation or fill claims."""
import math
from datetime import datetime, timezone

HORIZONS={"5m":300,"15m":900,"1h":3600,"24h":86400,"72h":259200}
TARGETS=(3,10,50)
MAX_GAP=300  # gaps >5m flagged, never assumed to contain an unobserved hit

def init(con):
    con.execute("""CREATE TABLE IF NOT EXISTS signal_trials(
      id INTEGER PRIMARY KEY AUTOINCREMENT, market TEXT NOT NULL, name TEXT,
      day TEXT NOT NULL, signal TEXT NOT NULL, first_ts INTEGER NOT NULL,
      entry REAL NOT NULL, stop REAL, first_change24 REAL, watch_score INTEGER,
      buy_suitability INTEGER, first_class TEXT, last_ts INTEGER NOT NULL,
      last_price REAL NOT NULL, high_pct REAL NOT NULL DEFAULT 0,
      low_pct REAL NOT NULL DEFAULT 0, observations INTEGER NOT NULL DEFAULT 0,
      max_gap INTEGER NOT NULL DEFAULT 0, first_event TEXT, first_event_ts INTEGER,
      status TEXT NOT NULL DEFAULT 'TRACKING',
      UNIQUE(market,day,signal))""")
    con.execute("""CREATE TABLE IF NOT EXISTS trial_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT, trial_id INTEGER NOT NULL,
      ts INTEGER NOT NULL, kind TEXT NOT NULL, price REAL NOT NULL,
      change_pct REAL NOT NULL, UNIQUE(trial_id,kind))""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_trials_status ON signal_trials(status,first_ts)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_trial_events ON trial_events(trial_id,ts)")

def finite_positive(v):
    try:
        f=float(v)
        return f if math.isfinite(f) and f>0 else None
    except (ValueError,TypeError,OverflowError):return None

def record(con,results,ts):
    day=datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%d')
    for r in results:
        signal=r.get('status')
        if signal not in ('BUY','PRE'):continue
        price=finite_positive(r.get('price'))
        if price is None:continue
        stop=finite_positive(r.get('stop'))
        change=r.get('change24')
        try:change=float(change) if change is not None and math.isfinite(float(change)) else None
        except (ValueError,TypeError,OverflowError):change=None
        classification='기준정보 없음' if change is None else ('후행 +10% 이상' if change>=10 else '후행 +3% 이상' if change>=3 else '초기 관찰 · 사전 적중 미확정')
        con.execute("""INSERT OR IGNORE INTO signal_trials(market,name,day,signal,first_ts,entry,stop,
          first_change24,watch_score,buy_suitability,first_class,last_ts,last_price)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",(r['market'],r.get('name',''),day,signal,ts,price,stop,change,r.get('score'),r.get('buy_suitability'),classification,ts,price))

def observe(con,tickers,ts):
    prices={x.get('market'):finite_positive(x.get('trade_price')) for x in tickers}
    rows=con.execute("SELECT id,market,first_ts,entry,stop,last_ts,high_pct,low_pct,observations,max_gap,first_event FROM signal_trials WHERE status='TRACKING'").fetchall()
    for id_,market,first,entry,stop,last,hi,lo,n,gap,first_event in rows:
        if ts<=last:continue
        age=ts-first
        price=prices.get(market)
        if price is None:
            if age>=HORIZONS['72h']:
                con.execute("UPDATE signal_trials SET status='INCOMPLETE' WHERE id=?",(id_,))
            continue
        pct=(price/entry-1)*100
        elapsed=ts-last
        gap=max(gap,elapsed)
        # Only observed ticker prices count. An unobserved crossing is unknown.
        events=[]
        for target in TARGETS:
            if pct>=target:events.append(('TP'+str(target),price,pct))
        if stop is not None and price<=stop:events.append(('STOP',price,pct))
        for kind,ev_price,ev_pct in events:
            cursor=con.execute('INSERT OR IGNORE INTO trial_events(trial_id,ts,kind,price,change_pct) VALUES(?,?,?,?,?)',(id_,ts,kind,ev_price,ev_pct))
            if cursor.rowcount and first_event is None:
                first_event=kind
                con.execute('UPDATE signal_trials SET first_event=?,first_event_ts=? WHERE id=?',(kind,ts,id_))
        for label,seconds in HORIZONS.items():
            if ts-first>=seconds:
                con.execute('INSERT OR IGNORE INTO trial_events(trial_id,ts,kind,price,change_pct) VALUES(?,?,?,?,?)',(id_,ts,'H_'+label,price,pct))
        status='COMPLETE' if age>=HORIZONS['72h'] else 'TRACKING'
        con.execute('UPDATE signal_trials SET last_ts=?,last_price=?,high_pct=?,low_pct=?,observations=?,max_gap=?,status=? WHERE id=?',
                    (ts,price,max(hi,pct),min(lo,pct),n+1,gap,status,id_))

def report(con,limit=100):
    rows=con.execute("""SELECT id,market,name,signal,first_ts,entry,stop,first_change24,watch_score,
      buy_suitability,first_class,last_ts,last_price,high_pct,low_pct,observations,max_gap,
      first_event,first_event_ts,status FROM signal_trials ORDER BY first_ts DESC,id DESC LIMIT ?""",(limit,)).fetchall()
    keys=('id','market','name','signal','first_ts','entry','stop','first_change24','watch_score','buy_suitability','first_class','last_ts','last_price','high_pct','low_pct','observations','max_gap','first_event','first_event_ts','status')
    trials=[]
    for row in rows:
        d=dict(zip(keys,row))
        evs=con.execute('SELECT kind,ts,price,change_pct FROM trial_events WHERE trial_id=? ORDER BY ts,id',(d['id'],)).fetchall()
        d['events']=[dict(zip(('kind','ts','price','change_pct'),e)) for e in evs]
        d['milestones']={k:next(({'ts':e['ts'],'price':e['price'],'change_pct':round(e['change_pct'],3)} for e in d['events'] if e['kind']=='H_'+k),None) for k in HORIZONS}
        d['hits']={str(t):next((e['ts'] for e in d['events'] if e['kind']=='TP'+str(t)),None) for t in TARGETS}
        d['stop_ts']=next((e['ts'] for e in d['events'] if e['kind']=='STOP'),None)
        d['gap_warning']=d['max_gap']>MAX_GAP
        trials.append(d)
    completed=[x for x in trials if x['status']=='COMPLETE']
    summary={'total_returned':len(trials),'completed_returned':len(completed),'tracking_returned':sum(x['status']=='TRACKING' for x in trials),
       'incomplete_returned':sum(x['status']=='INCOMPLETE' for x in trials),
       'hit_3_completed':sum(x['hits']['3'] is not None for x in completed),
       'hit_10_completed':sum(x['hits']['10'] is not None for x in completed),
       'hit_50_completed':sum(x['hits']['50'] is not None for x in completed),
       'gaps_over_5m':sum(x['gap_warning'] for x in trials)}
    return {'summary':summary,'rows':trials,'method':'신호 이후 관측된 현재가만 사용. 최초 5/15/60분·24/72시간 이후 첫 관측값. 미관측 구간의 최고·최저 및 체결 순서 확인 불가. 동일 시점 목표/손절 순서는 추론하지 않음. 실제 거래 성과 아님.'}
