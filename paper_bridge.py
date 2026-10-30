"""Persistent SQLite, read-only sampled-price paper trading integration. No exchange orders."""
import sqlite3,math,time
import paper_trading as paper
def sync(db_path,results,tickers,now=None):
    now=int(now or time.time())
    with sqlite3.connect(db_path,timeout=20) as db:
        db.execute('PRAGMA busy_timeout=20000')
        db.execute(paper.SCHEMA)
        observed=0
        for t in tickers:
            try:
                market=t['market'];price=float(t['trade_price'])
                if not math.isfinite(price) or price<=0:continue
                paper.observe(db,market,now,price,price);observed+=1
            except (KeyError,ValueError,TypeError,OverflowError):continue
        added=0
        for r in results:
            if r.get('status')!='BUY':continue
            try:
                market=r['market'];entry=float(r['entry']);stop=float(r['stop'])
                levels=r.get('tp_levels') or []
                tp=float(levels[0]['price']) if levels else 0
                if not all(math.isfinite(x) for x in (entry,stop,tp)) or not 0<stop<entry<tp:continue
                if db.execute("SELECT 1 FROM paper_trades WHERE market=? AND status='OPEN' LIMIT 1",(market,)).fetchone():continue
                bucket=now//300*300
                if db.execute('SELECT 1 FROM paper_trades WHERE market=? AND signal_ts>=? AND signal_ts<? LIMIT 1',(market,bucket,bucket+300)).fetchone():continue
                paper.record(db,market,now,entry,stop,tp);added+=1
            except (KeyError,ValueError,TypeError,OverflowError):continue
        return {'recorded':added,'sampled_tickers':observed,**paper.report(db)}
def status(db_path):
    with sqlite3.connect(db_path,timeout=20) as db:
        db.execute(paper.SCHEMA)
        data=paper.report(db)
        rows=db.execute('SELECT market,signal_ts,entry,stop,tp1,status,exit_price,exit_ts,exit_reason FROM paper_trades ORDER BY id DESC LIMIT 100').fetchall()
        data['rows']=[dict(zip(('market','signal_ts','entry','stop','tp1','status','exit_price','exit_ts','exit_reason'),r)) for r in rows]
        data['method']='Observed ticker price snapshots only; gaps and intrabar excursions unknown. Not executable fills.'
        return data
