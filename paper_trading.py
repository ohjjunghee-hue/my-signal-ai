"""Read-only paper trade journal. NEVER places exchange orders."""
SCHEMA="""CREATE TABLE IF NOT EXISTS paper_trades (id INTEGER PRIMARY KEY, market TEXT NOT NULL, signal_ts INTEGER NOT NULL, entry REAL NOT NULL CHECK(entry>0), stop REAL NOT NULL CHECK(stop>0), tp1 REAL NOT NULL CHECK(tp1>0), status TEXT NOT NULL DEFAULT 'OPEN', exit_price REAL, exit_ts INTEGER, exit_reason TEXT, UNIQUE(market,signal_ts));"""
def record(db,market,ts,entry,stop,tp1):
    if not (market.startswith('KRW-') and isinstance(ts,int) and ts>0 and 0<stop<entry<tp1):raise ValueError('invalid signal or risk levels')
    db.execute('INSERT OR IGNORE INTO paper_trades(market,signal_ts,entry,stop,tp1) VALUES(?,?,?,?,?)',(market,ts,entry,stop,tp1));db.commit()
def observe(db,market,ts,low,high):
    if not (isinstance(ts,int) and ts>0 and 0<low<=high):raise ValueError('invalid observation')
    rows=db.execute("SELECT id,signal_ts,entry,stop,tp1 FROM paper_trades WHERE market=? AND status='OPEN'",(market,)).fetchall()
    for id,signal_ts,entry,stop,tp1 in rows:
        if ts<=signal_ts:continue
        reason,exit_price=('STOP',stop) if low<=stop else (('TP1',tp1) if high>=tp1 else (None,None))
        if reason:db.execute('UPDATE paper_trades SET status=?,exit_price=?,exit_ts=?,exit_reason=? WHERE id=?',(reason,exit_price,ts,reason,id))
    db.commit()
def report(db,fee_pct=0.2):
    rows=db.execute('SELECT entry,exit_price,status FROM paper_trades').fetchall()
    closed=[100*(ex/en-1)-fee_pct for en,ex,status in rows if ex is not None]
    return {'total':len(rows),'open':sum(x[2]=='OPEN' for x in rows),'closed':len(closed),'net_return_mean_closed_pct':round(sum(closed)/len(closed),4) if closed else None,'assumed_roundtrip_cost_pct':fee_pct,'caution':'Paper only. No exchange orders. Open trades excluded from mean; no slippage or spread modeled.'}
