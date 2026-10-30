#!/usr/bin/env python3
"""MY SIGNAL AI PRO V45: forward-only milestone validation and preserved V44 diagnostics."""
import json, os, time, math, sqlite3, threading, urllib.request, urllib.parse, http.server, pathlib, statistics, re, html, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import outcome_validation as ov
import paper_bridge
from datetime import datetime, timezone, timedelta
ROOT=pathlib.Path(__file__).parent
DATA_DIR=pathlib.Path(os.getenv("DATA_DIR",str(ROOT/"data")))
DATA_DIR.mkdir(parents=True,exist_ok=True)
DB=DATA_DIR/"signals.db"
ACCESS_TOKEN=os.getenv("ACCESS_TOKEN", "").strip()
PORT=int(os.getenv('PORT','8765'))
INTERVAL=max(60,int(os.getenv('SCAN_SECONDS','120')))
TOP=max(5,min(160,int(os.getenv('DEEP_MARKETS','80'))))
WORKERS=max(1,min(8,int(os.getenv('DEEP_WORKERS','4'))))
BASE='https://api.bithumb.com'
NEWS_FEEDS=[('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/'),('Cointelegraph','https://cointelegraph.com/rss')]
lock=threading.Lock()
state={'status':'대기','last_scan':None,'errors':[],'market_count':0,'deep_count':0,'news_updated':None,'news':[],'candidates':[],'scan_seconds':INTERVAL,'engine_version':'V48-INTEGRATED','selection_details':{},'outcome_summary':{},'market_audit':[],'market_leaders':[],'tracked':[],'setup_events':[],'market_updated':None,'momentum':[],'momentum_updated':None,'signal_diagnostics':{},'analysis_workers':WORKERS,'audit_updated':None,'buy_enabled':True,'news_ai_enabled':False,'social_enabled':False,'midnight':{'active':False,'status':'대기','last_check':None,'baseline_time':None,'checked':0,'leaders':[],'errors':[],'note':'자정 전후 실제 가격 변화 감시 · 매수 신호 아님'}}

def get_json(path):
    req=urllib.request.Request(BASE+path,headers={'User-Agent':'MY-SIGNAL-V44/0.1','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=12) as res: result=json.load(res)
    if isinstance(result,dict) and result.get('error'):raise ValueError(str(result['error']))
    return result

def fetch_candles(market,unit,count=120):
    path=f'/v1/candles/minutes/{unit}?'+urllib.parse.urlencode({'market':market,'count':count})
    raw=get_json(path)
    if not isinstance(raw,list):raise ValueError('캔들 응답 형식 오류')
    out=[]
    for x in reversed(raw):
        try:
            t=datetime.fromisoformat(x['candle_date_time_utc']+'+00:00').timestamp()
            o,h,l,c,v=[float(x[k]) for k in ('opening_price','high_price','low_price','trade_price','candle_acc_trade_volume')]
            if not all(map(math.isfinite,(o,h,l,c,v))) or min(o,h,l,c)<=0 or v<0 or h<max(o,c,l) or l>min(o,c,h):continue
            if t+unit*60>time.time()-2:continue # strictly closed candle
            out.append({'t':t,'o':o,'h':h,'l':l,'c':c,'v':v})
        except (KeyError,ValueError,TypeError):continue
    return sorted({x['t']:x for x in out}.values(),key=lambda x:x['t'])

def ema(xs,p):
    v=xs[0];k=2/(p+1)
    for x in xs[1:]:v+=(x-v)*k
    return v

def opportunity_targets(entry, stop, atr_pct, resistance, vol_ratio, compression, trend, higher, risk, change24, rise8):
    """Risk-first *scenario* targets; never confuse displayed upside with a forecast.

    Reject tight-RR setups rather than manufacturing attractive targets from ATR.
    The upside bands are explicit scenario thresholds, not probabilities.
    """
    if not all(math.isfinite(x) for x in (entry,stop,atr_pct,resistance,vol_ratio,compression,change24,rise8)) or entry<=0:
        return {'eligible':False,'reason':'가격 데이터 오류','levels':[],'upside_pct':0,'rr':0,'risk_pct':0}
    risk_pct=max(0,(entry-stop)/entry*100)
    if stop>=entry or risk_pct<.5 or risk_pct>8:
        return {'eligible':False,'reason':'손절 거리 비정상','levels':[],'upside_pct':0,'rr':0,'risk_pct':round(risk_pct,2)}
    # Do not use price gain as proof of future upside. Require independently observable setup.
    if risk or not (trend and higher) or vol_ratio<1.3 or compression>12 or change24>15 or rise8>7:
        return {'eligible':False,'reason':'추세·거래량·과열 필터 미충족','levels':[],'upside_pct':0,'rr':0,'risk_pct':round(risk_pct,2)}
    if resistance>entry and (resistance/entry-1)*100<max(1.5,atr_pct):
        return {'eligible':False,'reason':'근접 저항으로 상승 여력 불충분','levels':[],'upside_pct':0,'rr':0,'risk_pct':round(risk_pct,2)}
    # Structural screening only; the target levels remain unvalidated scenarios.
    if compression<=6 and vol_ratio>=2.0 and change24<8:
        pct=[10,20,50];grade='급등 확장 시나리오'
    elif compression<=10 and vol_ratio>=1.5 and change24<12:
        pct=[5,10,20];grade='중기 상승 시나리오'
    else:
        pct=[3,5,10];grade='단기 상승 시나리오'
    rr=pct[0]/risk_pct
    if rr<1.5:
        return {'eligible':False,'reason':'1차 목표 대비 손익비 1.5 미만','levels':[],'upside_pct':pct[-1],'rr':round(rr,2),'risk_pct':round(risk_pct,2)}
    return {'eligible':True,'reason':grade+' · 목표 달성 가능성 미검증','levels':[{'price':round(entry*(1+x/100),8),'pct':x} for x in pct],'upside_pct':pct[-1],'rr':round(rr,2),'risk_pct':round(risk_pct,2)}

def analyze(c5,c15,c60,price,change24=0):
    if min(map(len,(c5,c15,c60)))<35:return {'status':'DATA','reason':'확정봉 부족'}
    a=c5;last=a[-1];prev=a[-2];close=[x['c'] for x in a];vs=[x['v'] for x in a]
    e8=ema(close[-35:],8);e21=ema(close[-35:],21)
    e15=ema([x['c'] for x in c15][-35:],21)
    e60=ema([x['c'] for x in c60][-35:],21)
    vol=last['v']/max(statistics.mean(vs[-21:-1]),1e-12)
    rise5=(last['c']/close[-6]-1)*100
    rise8=(last['c']/close[-9]-1)*100
    resistance=max(x['h'] for x in c15[-21:-1])
    dist=(resistance/price-1)*100
    candle_strength=(last['c']-last['l'])/max(last['h']-last['l'],1e-12)
    atr=statistics.mean(max(x['h']-x['l'],abs(x['h']-p['c']),abs(x['l']-p['c'])) for p,x in zip(a[-15:-1],a[-14:]))
    atr_pct=100*atr/max(price,1e-12)
    compression=(max(x['h'] for x in a[-21:-1])-min(x['l'] for x in a[-21:-1]))/max(price,1e-12)*100
    trend=e8>e21 and c15[-1]['c']>=e15*.992
    higher=c60[-1]['c']>=e60*.97
    risk=[]
    if rise8>7 or rise5>5:risk.append('단기 급등 추격')
    if price>e8*1.045:risk.append('단기 이평 이격 과다')
    if candle_strength<.42 and vol>1.8:risk.append('거래량 증가 후 종가 약세')
    if last['h']>last['c']*1.025:risk.append('긴 윗꼬리')
    if dist>0 and dist<max(1.8,atr_pct*1.1):risk.append('상단 저항 근접')
    if not higher:risk.append('1시간 추세 약세')
    if abs(price/last['c']-1)*100>max(1.5,atr_pct*1.5):risk.append('현재가와 확정봉 가격 괴리')
    if change24>15:risk.append('24시간 급등 후행')
    early=trend and .9<=vol<=4.5 and -1.5<=rise5<=4.5 and compression<=12 and candle_strength>=.55
    score=round(min(95,max(0,25+(20 if trend else 0)+(12 if higher else 0)+min(18,vol*5)+(10 if compression<8 else 0)+(10 if candle_strength>.7 else 0)-len(risk)*9)))
    status='WATCH'
    if early and not risk and dist>=max(2.0,atr_pct*1.5):status='READY'
    if risk:status='WAIT'
    # BUY is a strict, *technical* signal on closed candles, not a validated profit prediction.
    recent_resistance=max(x['h'] for x in a[-21:-1])
    confirmed_breakout=(last['c']>recent_resistance and prev['c']<=max(x['h'] for x in a[-22:-2]))
    buy_setup=(confirmed_breakout and vol>=1.3 and trend and higher and
               0<=rise5<=4.5 and change24<=10 and not risk and
               candle_strength>=.65 and last['c']>prev['c'])
    pre_setup=(early and not risk and change24<8 and vol>=1.3)
    buy_gates={
      '확정봉 20봉 고점 돌파':bool(confirmed_breakout),
      '거래량 1.3배 이상':bool(vol>=1.3),
      '5·15분 추세':bool(trend),
      '1시간 추세':bool(higher),
      '5분 상승폭 0~4.5%':bool(0<=rise5<=4.5),
      '24시간 상승률 10% 이하':bool(change24<=10),
      '위험 경고 없음':bool(not risk),
      '캔들 종가 위치 65% 이상':bool(candle_strength>=.65),
      '직전 봉 대비 상승 마감':bool(last['c']>prev['c'])}
    # Diagnostic suitability is not a probability or a replacement for strict BUY gates.
    # Cap scores for low liquidity momentum, downtrends, and high-risk setups.
    suitability=round(100*sum(buy_gates.values())/len(buy_gates))
    suitability_reasons=[]
    if vol<1.3:
        suitability=min(suitability,39)
        suitability_reasons.append('확정봉 거래량 1.3배 미만')
    if not trend or not higher:
        suitability=min(suitability,45)
        suitability_reasons.append('추세 미확인')
    if risk:
        suitability=min(suitability,35)
        suitability_reasons.extend(risk)
    if change24>10:
        suitability=min(suitability,30)
        suitability_reasons.append('24시간 상승률 10% 초과 · 추격 경계')
    suitability=max(0,min(100,suitability))
    if buy_setup:status='BUY'
    elif pre_setup:status='PRE'
    entry=price
    stop=min(x['l'] for x in a[-6:])
    if stop>=entry or (entry-stop)/entry*100>8:stop=entry-max(1.5*atr,entry*.025)
    riskpct=max(0,(entry-stop)/entry*100)
    opportunity=opportunity_targets(entry,stop,atr_pct,resistance,vol,compression,trend,higher,risk,change24,rise8)
    if opportunity['eligible']:
        tier=opportunity['reason'].split(' · ')[0]
        tier_rank=0 if opportunity['upside_pct']>=50 else 1 if opportunity['upside_pct']>=20 else 2
        medium_targets=opportunity['levels']
    else:
        tier='추천 제외 · 관찰만';tier_rank=3;medium_targets=[]
        # A technical BUY breakout without adequate upside/RR is NOT a buy candidate.
        if status in ('BUY','PRE','READY'):status='WAIT'
    decision='BUY' if status=='BUY' else 'PRE' if status=='PRE' else 'WAIT' if status=='WAIT' else 'OBSERVE'
    return {'status':status,'score':score,'buy_suitability':suitability,'suitability_reasons':suitability_reasons,'score_label':'관찰 점수 (상승 확률 아님)','opportunity_tier':tier,'tier_rank':tier_rank,
      'horizon_note':'상승 시나리오 · 기간 및 도달 미검증',
      'medium_targets':medium_targets,'tier_disclaimer':'목표는 가정된 가격 구간이며 예측이나 수익 보장이 아님',
      'entry':entry,'stop':round(stop,8),'stop_pct':round(riskpct,2),
      'targets':[t['price'] for t in medium_targets],
      'tp_levels':medium_targets,'opportunity':opportunity,'decision':decision,
      'decision_reason':('확정봉 돌파·거래량·추세 확인' if status=='BUY' else '초기 상승 준비 신호' if status=='PRE' else opportunity['reason']),
      'target_note':'시나리오 목표 · 저항/손익비/과열 조건 검토 · 목표 도달 확률 미검증',
      'buy_gates':buy_gates,'buy_gate_passed':sum(buy_gates.values()),'buy_gate_total':len(buy_gates),
      'risk':risk,'reason':('초기 거래량·추세 조건 관찰' if early else '초기 상승 조건 미충족'),
      'features':{'vol_ratio':round(vol,2),'breakout_confirmed':confirmed_breakout,
      'rise5_pct':round(rise5,2),'rise8_pct':round(rise8,2),'atr_pct':round(atr_pct,2),
      'compression_pct':round(compression,2),'resistance':round(resistance,8),
      'resistance_distance_pct':round(dist,2),'candle_strength':round(candle_strength,2),
      'trend5_15':trend,'trend60':higher}}

def fetch_news():
    items=[]
    for source,url in NEWS_FEEDS:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 MY-SIGNAL-V35'})
            with urllib.request.urlopen(req,timeout=8) as r: raw=r.read(750000)
            root=ET.fromstring(raw)
            for item in root.findall('.//item')[:12]:
                title=' '.join((item.findtext('title') or '').split())[:180]
                link=(item.findtext('link') or '').strip()
                if title and link.startswith('https://'):items.append({'source':source,'title':title,'url':link,'published':item.findtext('pubDate') or ''})
        except Exception:continue
    return items[:20]

def db_init():
    with sqlite3.connect(DB) as con:
        ov.init(con)
        con.execute('CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY,ts INTEGER,market TEXT,status TEXT,score INTEGER,entry REAL,stop REAL,features TEXT,reason TEXT)')
        con.execute('CREATE INDEX IF NOT EXISTS ix_market_time ON snapshots(market,ts)')
        con.execute('CREATE TABLE IF NOT EXISTS signal_outcomes(id INTEGER PRIMARY KEY,market TEXT,day TEXT,first_seen INTEGER,last_seen INTEGER,entry REAL,last_price REAL,max_pct REAL,min_pct REAL,status TEXT,signal_type TEXT,UNIQUE(market,day))')
        # Safe additive migration: existing signal records remain untouched.
        cols={row[1] for row in con.execute('PRAGMA table_info(signal_outcomes)')}
        for name,typ in [('first_change24','REAL'),('first_score','INTEGER'),('first_source','TEXT'),('first_class','TEXT'),('observations','INTEGER DEFAULT 0')]:
            if name not in cols:con.execute(f'ALTER TABLE signal_outcomes ADD COLUMN {name} {typ}')
        con.execute('CREATE TABLE IF NOT EXISTS market_audit(id INTEGER PRIMARY KEY, ts INTEGER, market TEXT, price REAL, change24 REAL, turnover24 REAL, analysis_status TEXT, selection_source TEXT)')
        con.execute('CREATE INDEX IF NOT EXISTS ix_audit_market_ts ON market_audit(market,ts)')
        con.execute('''CREATE TABLE IF NOT EXISTS active_setups(
            market TEXT PRIMARY KEY, first_seen INTEGER NOT NULL, last_analyzed INTEGER NOT NULL,
            first_price REAL NOT NULL, first_change24 REAL, first_score INTEGER,
            last_price REAL NOT NULL, peak_price REAL NOT NULL, trough_price REAL NOT NULL,
            stop_price REAL NOT NULL, status TEXT NOT NULL, horizon TEXT NOT NULL,
            expiry INTEGER NOT NULL, confirm_weak INTEGER NOT NULL DEFAULT 0,
            last_score INTEGER, name TEXT, reason TEXT, last_signal INTEGER,
            last_signal_price REAL, exit_reason TEXT DEFAULT '')''')
        con.execute('CREATE INDEX IF NOT EXISTS ix_setups_expiry ON active_setups(expiry)')
        con.execute("""CREATE TABLE IF NOT EXISTS setup_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,market TEXT NOT NULL,ts INTEGER NOT NULL,
            previous TEXT,new_status TEXT NOT NULL,price REAL NOT NULL,
            reason TEXT NOT NULL,UNIQUE(market,ts,new_status))""")
        con.execute('CREATE INDEX IF NOT EXISTS ix_setup_events_market_ts ON setup_events(market,ts DESC)')
        con.execute('''CREATE TABLE IF NOT EXISTS pulse_samples(
            market TEXT NOT NULL, ts INTEGER NOT NULL, price REAL NOT NULL,
            turnover24 REAL NOT NULL, change24 REAL NOT NULL,
            PRIMARY KEY(market,ts))''')
        con.execute('CREATE INDEX IF NOT EXISTS ix_pulse_ts ON pulse_samples(ts)')


def tracked_priority(con, now_ts, limit=32):
    '''Persisted live setups get first claim on expensive candle analysis.'''
    return [r[0] for r in con.execute(
        "SELECT market FROM active_setups WHERE status IN ('PRE','BUY','HOLD','WATCH') AND expiry>? ORDER BY CASE status WHEN 'BUY' THEN 0 WHEN 'HOLD' THEN 1 WHEN 'PRE' THEN 2 ELSE 3 END,first_seen ASC LIMIT ?",
        (now_ts,limit)).fetchall()]


def add_setup_event(con,market,ts,old,new,price,reason):
    if old == new:return
    con.execute('INSERT OR IGNORE INTO setup_events(market,ts,previous,new_status,price,reason) VALUES(?,?,?,?,?,?)',
                (market,ts,old,new,price,reason))

def read_setup_events(con,limit=100,market=None):
    if market:
        rows=con.execute('SELECT market,ts,previous,new_status,price,reason FROM setup_events WHERE market=? ORDER BY ts DESC,id DESC LIMIT ?', (market,limit)).fetchall()
    else:
        rows=con.execute('SELECT market,ts,previous,new_status,price,reason FROM setup_events ORDER BY ts DESC,id DESC LIMIT ?', (limit,)).fetchall()
    return [dict(zip(('market','ts','previous','new_status','price','reason'),r)) for r in rows]

def maintain_setups(con, results, tickers, now_ts):
    '''Sticky recommendations; tickers update marks, only closed-candle analysis changes technical state.

    No price-only promotion to BUY. Hard stop is immediate on observed ticker; ordinary
    demotion requires two consecutive deep analyses. Expiry is fixed on creation.
    '''
    prices={x['market']:float(x.get('trade_price') or 0) for x in tickers}
    changes={x['market']:float(x.get('signed_change_rate') or 0)*100 for x in tickers}
    for r in results:
        m=r['market']; raw=r.get('status','WATCH');price=float(r.get('price') or 0)
        if price<=0 or not math.isfinite(price):continue
        old=con.execute('SELECT first_seen,first_price,stop_price,status,expiry,confirm_weak,last_signal,last_signal_price FROM active_setups WHERE market=?',(m,)).fetchone()
        if old is None:
            if raw not in ('PRE','BUY','READY'):continue
            horizon='2~12시간' if r.get('tier_rank',2)==2 else '1~3일'
            expiry=now_ts+(12*3600 if horizon=='2~12시간' else 72*3600)
            con.execute('''INSERT INTO active_setups(market,first_seen,last_analyzed,first_price,first_change24,first_score,last_price,peak_price,trough_price,stop_price,status,horizon,expiry,confirm_weak,last_score,name,reason,last_signal,last_signal_price)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (m,now_ts,now_ts,price,r.get('change24'),r.get('score'),price,price,price,float(r.get('stop') or price*.97),
                 'BUY' if raw=='BUY' else 'PRE',horizon,expiry,0,r.get('score'),r.get('name',m),r.get('decision_reason',''),now_ts if raw=='BUY' else None,price if raw=='BUY' else None))
            add_setup_event(con,m,now_ts,None,'BUY' if raw=='BUY' else 'PRE',price,'최초 확정봉 신호')
            continue
        first,first_price,stop,prior,expiry,weak,last_signal,last_signal_price=old
        if prior in ('STOP','EXPIRED'):continue
        if price<=stop:
            next_status='STOP';weak=0;reason='관측 가격이 최초 손절선 이탈'
        elif now_ts>=expiry:
            next_status='EXPIRED';weak=0;reason='최초 설정 관찰기간 종료'
        elif raw=='BUY':
            next_status='BUY' if prior!='HOLD' else 'HOLD';weak=0;reason='확정봉 BUY 조건 재충족'
        elif prior in ('BUY','HOLD'):
            next_status='HOLD';weak=0 if raw in ('PRE','READY') else weak+1
            reason='상승 흐름 추적 중' if weak<2 else '기술 조건 약화 · 추적 유지, 신규 매수 아님'
        elif raw in ('PRE','READY'):
            next_status='PRE';weak=0;reason='전조 조건 유지'
        else:
            weak+=1;next_status='PRE' if weak<2 else 'WATCH';reason='연속 조건 약화 · 관찰 유지'
        add_setup_event(con,m,now_ts,prior,next_status,price,reason)
        con.execute('''UPDATE active_setups SET last_analyzed=?,last_price=?,peak_price=MAX(peak_price,?),trough_price=MIN(trough_price,?),status=?,confirm_weak=?,last_score=?,name=?,reason=?,last_signal=CASE WHEN ?='BUY' AND status NOT IN ('BUY','HOLD') THEN ? ELSE last_signal END,last_signal_price=CASE WHEN ?='BUY' AND status NOT IN ('BUY','HOLD') THEN ? ELSE last_signal_price END WHERE market=?''',
            (now_ts,price,price,price,next_status,weak,r.get('score'),r.get('name',m),reason,raw,now_ts,raw,price,m))
    # Log price-triggered exits, including coins not selected for candle analysis.
    existing={row[0]:row[1:] for row in con.execute("SELECT market,status,stop_price,expiry FROM active_setups WHERE status NOT IN ('STOP','EXPIRED')")}
    for m,price in prices.items():
        old=existing.get(m)
        if old and price>0 and math.isfinite(price):
            prior,stop,expiry=old
            if price<=stop:add_setup_event(con,m,now_ts,prior,'STOP',price,'관측 손절선 이탈')
            elif now_ts>=expiry:add_setup_event(con,m,now_ts,prior,'EXPIRED',price,'관찰기간 종료')
    # Every market ticker updates observed price, even if the coin was not deep analyzed.
    # Never claim a BUY from ticker changes alone.
    for m,price in prices.items():
        if price<=0 or not math.isfinite(price):continue
        con.execute('''UPDATE active_setups SET last_price=?,peak_price=MAX(peak_price,?),trough_price=MIN(trough_price,?),status=CASE WHEN status IN ('STOP','EXPIRED') THEN status WHEN ?<=stop_price THEN 'STOP' WHEN ?>=expiry THEN 'EXPIRED' ELSE status END,exit_reason=CASE WHEN status NOT IN ('STOP','EXPIRED') AND ?<=stop_price THEN '관측 손절선 이탈' WHEN status NOT IN ('STOP','EXPIRED') AND ?>=expiry THEN '관찰기간 종료' ELSE exit_reason END WHERE market=?''',
            (price,price,price,price,now_ts,price,now_ts,m))
    con.execute("DELETE FROM active_setups WHERE expiry<? AND status IN ('STOP','EXPIRED')",(now_ts-14*86400,))
    return read_setups(con,now_ts)


def read_setups(con,now_ts,limit=100):
    cols=['market','first_seen','last_analyzed','first_price','first_change24','first_score','last_price','peak_price','trough_price','stop_price','status','horizon','expiry','confirm_weak','last_score','name','reason','last_signal','last_signal_price','exit_reason']
    rows=con.execute('SELECT '+','.join(cols)+''' FROM active_setups ORDER BY CASE status WHEN 'BUY' THEN 0 WHEN 'HOLD' THEN 1 WHEN 'PRE' THEN 2 WHEN 'WATCH' THEN 3 WHEN 'STOP' THEN 4 ELSE 5 END,first_seen ASC LIMIT ?''',(limit,)).fetchall()
    out=[]
    for row in rows:
        d=dict(zip(cols,row));entry=d['first_price'];last=d['last_price'];peak=d['peak_price']
        d['since_pct']=round((last/entry-1)*100,2) if entry else None
        d['peak_since_pct']=round((peak/entry-1)*100,2) if entry else None
        d['age_minutes']=max(0,(now_ts-d['first_seen'])//60)
        d['stale_analysis']=now_ts-d['last_analyzed']>max(INTERVAL*3,600)
        d['is_late']=d['first_change24'] is not None and d['first_change24']>=3
        out.append(d)
    return out


def select_deep_markets(tickers, top, cycle, midnight_leaders=None, pinned=None, accelerators=None):
    """Bounded selection with liquid baseline, midnight leaders and rotation.

    This only improves coverage; it does not predict future returns.
    """
    eligible={x['market']:x for x in tickers if x.get('market')}
    ranked=sorted(eligible.values(),key=lambda x:float(x.get('acc_trade_price_24h') or 0),reverse=True)
    picked=[];sources={}
    def add(x,reason):
        if x and x['market'] not in sources and len(picked)<top:
            picked.append(x);sources[x['market']]=reason
    # Sticky candidates retain deep-analysis priority across cycles.
    for market in (pinned or [])[:max(1,top//2)]:add(eligible.get(market),'기존 후보 지속 추적')
    # Short-interval acceleration is a *priority for investigation*, not BUY.
    for row in (accelerators or [])[:max(1,top//4)]:
        add(eligible.get(row.get('market')),'단기 가격 가속 감시')
    # Reserve space for dynamic and rotating candidates even when top is small.
    liquid_slots=max(1,top//3)
    for x in ranked[:liquid_slots]:add(x,'거래대금 상위')
    leaders=midnight_leaders or []
    for row in leaders[:max(1,top//3)]:
        add(eligible.get(row.get('market')),'자정 급등 감시')
    # A second path uses current 24h movers even outside the midnight window.
    movers=sorted(ranked,key=lambda x:float(x.get('signed_change_rate') or 0),reverse=True)
    mover_quota=max(1,top//5)
    mover_added=0
    for x in movers:
        if mover_added>=mover_quota:break
        if x['market'] not in sources:
            add(x,'24시간 상승 상위 · 이미 상승 주의')
            mover_added+=1
    remaining=[x for x in ranked if x['market'] not in sources]
    slots=top-len(picked)
    if remaining and slots:
        start=(cycle*slots)%len(remaining)
        for x in (remaining[start:]+remaining[:start])[:slots]:add(x,'순환 분석')
    return picked,sources

def update_outcomes(con, tickers, now_ts):
    """Mark-to-market snapshots, no lookahead and no claim of executable fills.

    Track maxima/minima only at subsequent observed tickers, not candle highs.
    """
    prices={x.get('market'):float(x.get('trade_price') or 0) for x in tickers}
    rows=con.execute('SELECT id,market,entry,first_seen,last_seen,max_pct,min_pct FROM signal_outcomes WHERE status=?',('TRACKING',)).fetchall()
    for id_,market,entry,first,last,hi,lo in rows:
        price=prices.get(market,0)
        if price<=0 or not math.isfinite(price) or entry<=0 or now_ts<=first:continue
        pct=(price/entry-1)*100
        age=now_ts-first
        status='COMPLETE' if age>=72*3600 else 'TRACKING'
        con.execute('UPDATE signal_outcomes SET last_seen=?,last_price=?,max_pct=?,min_pct=?,status=?,observations=COALESCE(observations,0)+1 WHERE id=?',(now_ts,price,max(hi,pct),min(lo,pct),status,id_))

def classify_first_signal(change24):
    """Classification uses information available at first observation, not future candles."""
    if change24 is None:return '기준정보 없음'
    if not math.isfinite(change24):return '기준정보 없음'
    if change24>=10:return '이미 +10% 이상 상승 후 발견'
    if change24>=3:return '이미 +3% 이상 상승 후 발견'
    return '초기 관찰 (사전 적중 미확정)'

def record_outcomes(con,results,now_ts):
    # Preserve existing first_seen and first_change24; never overwrite on later scans.
    day=datetime.fromtimestamp(now_ts,timezone.utc).strftime('%Y-%m-%d')
    for r in results:
        if r.get('status') not in ('BUY','PRE','READY','WATCH'):continue
        entry=float(r.get('entry') or 0)
        if entry<=0:continue
        change=r.get('change24')
        try:change=float(change) if change is not None else None
        except (ValueError,TypeError):change=None
        classification=classify_first_signal(change)
        con.execute('INSERT OR IGNORE INTO signal_outcomes(market,day,first_seen,last_seen,entry,last_price,max_pct,min_pct,status,signal_type,first_change24,first_score,first_source,first_class,observations) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (r['market'],day,now_ts,now_ts,entry,entry,0.,0.,'TRACKING',r.get('opportunity_tier','관찰'),change,r.get('score'),r.get('selection_source',''),classification,0))

def audit_market_tickers(con,tickers,results,now_ts):
    """All-market ticker comparison, NOT a claim of full-market candle analysis."""
    by_market={r['market']:r for r in results}
    ranked=sorted(tickers,key=lambda x:float(x.get('signed_change_rate') or 0),reverse=True)
    audit=[]
    for x in ranked[:30]:
        m=x['market'];r=by_market.get(m)
        ch=round(float(x.get('signed_change_rate') or 0)*100,2)
        audit.append({'market':m,'price':float(x.get('trade_price') or 0),'change24':ch,'deep_analyzed':r is not None,'analysis_status':r.get('status') if r else '미분석','selection_source':r.get('selection_source','') if r else '심층 분석 대상 밖','note':'24시간 등락률 기준. 급등 전 발견 여부는 과거 신호 기록으로 별도 판정'})
        con.execute('INSERT INTO market_audit(ts,market,price,change24,turnover24,analysis_status,selection_source) VALUES(?,?,?,?,?,?,?)',(now_ts,m,audit[-1]['price'],ch,float(x.get('acc_trade_price_24h') or 0),audit[-1]['analysis_status'],audit[-1]['selection_source']))
    con.execute('DELETE FROM market_audit WHERE ts < ?', (now_ts-7*86400,))
    return audit

def get_audit_rows(con,limit=100):
    rows=con.execute('SELECT market,first_seen,last_seen,entry,last_price,max_pct,min_pct,status,signal_type,first_change24,first_score,first_source,first_class,observations FROM signal_outcomes ORDER BY first_seen DESC LIMIT ?', (limit,)).fetchall()
    cols=('market','first_seen','last_seen','entry','last_price','max_pct','min_pct','status','signal_type','first_change24','first_score','first_source','first_class','observations')
    out=[]
    for row in rows:
        d=dict(zip(cols,row))
        # Legacy entries lack the contemporaneous change: cannot be retroactively validated.
        d['verdict']='기록 부족' if not d['first_class'] or d['first_class']=='기준정보 없음' else ('후행 발견' if d['first_class'].startswith('이미') else '초기 관찰 · 성과 미확정')
        d['hit_3']=bool(d['max_pct'] is not None and d['max_pct']>=3)
        d['hit_10']=bool(d['max_pct'] is not None and d['max_pct']>=10)
        d['hit_50']=bool(d['max_pct'] is not None and d['max_pct']>=50)
        out.append(d)
    return out

def summarize_outcomes(con):
    rows=con.execute("SELECT max_pct,min_pct FROM signal_outcomes WHERE status='COMPLETE'").fetchall()
    return {'completed':len(rows),'hit_3':sum(x[0]>=3 for x in rows),'hit_10':sum(x[0]>=10 for x in rows),'hit_50':sum(x[0]>=50 for x in rows),'stopped_3':sum(x[1]<=-3 for x in rows),'note':'72시간 관찰가격 기준, 실거래 수익률·예측 정확도 아님. 서버 휴면 중 고저점 누락 가능'}

def momentum_from_samples(previous, current, minutes):
    """Return observable price and 24h rolling turnover differences, not trade flow.

    A difference of 24h cumulative turnover is NOT exact traded value over the
    sample interval because the 24h window also drops older trades.
    """
    if not previous or minutes<=0 or minutes>15:return None
    oldprice,oldturn=previous
    price,turn=current
    if min(oldprice,price)<=0:return None
    pct=100*(price/oldprice-1)
    turnover_delta=turn-oldturn
    return {'change_pct':round(pct,3),'turnover24_delta':round(turnover_delta),
            'minutes':round(minutes,2),'acceleration_pct_per_min':round(pct/minutes,4),
            'turnover_note':'24시간 이동창 거래대금 차이 · 순매수액 아님'}

def pulse_once(now_ts=None, getter=None):
    """Low-cost all-market early movement monitor; independent of deep scan.

    It is NOT a WebSocket or order-book/transaction stream.
    """
    now_ts=int(now_ts or time.time()); getter=getter or get_json
    markets=getter('/v1/market/all?isDetails=true')
    keys=[x['market'] for x in markets if x.get('market','').startswith('KRW-') and
          not re.search('CAUTION|WARNING',str(x.get('market_warning','')),re.I)]
    rows=[]
    for i in range(0,len(keys),80):
        part=getter('/v1/ticker?markets='+urllib.parse.quote(','.join(keys[i:i+80]),safe=','))
        if isinstance(part,list):rows.extend(part)
    rows=[x for x in rows if x.get('market') in keys and float(x.get('trade_price') or 0)>0]
    with sqlite3.connect(DB) as con:
        old={m:(p,t,v) for m,p,t,v in con.execute("""SELECT s.market,s.price,s.turnover24,s.ts
            FROM pulse_samples s JOIN (SELECT market,MAX(ts) AS ts FROM pulse_samples
            WHERE ts<=? GROUP BY market) z ON z.market=s.market AND z.ts=s.ts""",(now_ts-45,))}
        found=[]
        for x in rows:
            m=x['market'];price=float(x['trade_price']);turn=float(x.get('acc_trade_price_24h') or 0)
            previous=old.get(m)
            v=momentum_from_samples(previous[:2],(price,turn),(now_ts-previous[2])/60) if previous else None
            if v:
                v.update(market=m,price=price,change24=round(100*float(x.get('signed_change_rate') or 0),2),sample_time=now_ts)
                # Display all rising movers without labelling them BUY or 'whale accumulation'.
                if v['change_pct']>=.25:found.append(v)
            con.execute('INSERT OR REPLACE INTO pulse_samples VALUES(?,?,?,?,?)',
                        (m,now_ts,price,turn,100*float(x.get('signed_change_rate') or 0)))
        con.execute('DELETE FROM pulse_samples WHERE ts<?',(now_ts-86400,))
    found.sort(key=lambda x:x['acceleration_pct_per_min'],reverse=True)
    with lock:state.update(momentum=found[:40],momentum_updated=now_ts)
    return found

def pulse_loop():
    while True:
        try:pulse_once()
        except Exception as e:
            with lock:state['errors']=(state.get('errors',[])+['빠른 시장 감시: '+str(e)[:120]])[-30:]
        time.sleep(max(45,int(os.getenv('PULSE_SECONDS','60'))))

def analyze_market(ticker, name, source):
    market=ticker['market'];price=float(ticker['trade_price'])
    c5=fetch_candles(market,5)
    c15=fetch_candles(market,15)
    c60=fetch_candles(market,60)
    r=analyze(c5,c15,c60,price,float(ticker.get('signed_change_rate') or 0)*100)
    r.update(selection_source=source,market=market,name=name,price=price,
             change24=round(float(ticker.get('signed_change_rate') or 0)*100,2),
             volume24=float(ticker.get('acc_trade_price_24h') or 0),time=int(time.time()))
    return r

def diagnose_signals(results, errors):
    """Count closed-candle BUY gates, distinguish near misses from actionable BUY."""
    statuses=Counter(r.get('status','UNKNOWN') for r in results)
    rejected=Counter();passed=Counter();failed=Counter();near=[];gated=0
    for r in results:
        gates=r.get('buy_gates') or {}
        if gates:
            gated+=1
            for key,ok in gates.items():
                (passed if ok else failed)[key]+=1
            if r.get('status')!='BUY':
                near.append({'market':r.get('market',''),'name':r.get('name',''),
                  'status':r.get('status',''),'score':r.get('score',0),
                  'passed':sum(bool(x) for x in gates.values()),'total':len(gates),
                  'failed': [k for k,v in gates.items() if not v],
                  'opportunity_rejected':not (r.get('opportunity') or {}).get('eligible',False)})
        if r.get('status') in ('BUY','PRE'):continue
        for reason in r.get('risk',[]):rejected[reason]+=1
        opportunity=r.get('opportunity') or {}
        if not opportunity.get('eligible',False):rejected[opportunity.get('reason','상승 여력 미충족')]+=1
        if r.get('status')=='DATA':rejected['확정봉 부족']+=1
    near.sort(key=lambda x:(-x['passed'],x['opportunity_rejected'],-x['score']))
    return {'analyzed':len(results),'gate_evaluated':gated,'status_counts':dict(statuses),
      'gate_pass_counts':dict(passed),'gate_fail_counts':dict(failed),
      'suitability_summary':{'high_watch_low_buy':sum(1 for r in results if r.get('score',0)>=65 and r.get('buy_suitability',0)<40),
      'low_volume':sum(1 for r in results if r.get('features',{}).get('vol_ratio',0)<1.3),
      'warning':'매수 적합도는 규칙 기반 진단 지표이며 실제 상승 확률이나 수익률이 아닙니다.'},
      'near_misses':near[:8], 'rejection_reasons':dict(rejected.most_common(15)),
      'request_errors':len(errors),
      'note':'각 조건은 확정봉 기술 필터이며 통과율은 상승 확률이 아닙니다. 근접 후보는 BUY가 아닙니다.'}

def scan():
    errors=[];t0=time.time()
    with lock:state['status']='빗썸 시장 조회 중'
    markets=get_json('/v1/market/all?isDetails=true')
    names={x['market']:x.get('korean_name',x['market']) for x in markets if x.get('market','').startswith('KRW-') and not re.search('CAUTION|WARNING',str(x.get('market_warning','')),re.I)}
    tickers=[]; keys=list(names)
    for i in range(0,len(keys),80):
        try:
            rows=get_json('/v1/ticker?markets='+urllib.parse.quote(','.join(keys[i:i+80]),safe=','))
            if isinstance(rows,list):tickers+=rows
        except Exception as e:errors.append('시세 일부 누락: '+str(e)[:120])
        time.sleep(.12)
    tickers=[x for x in tickers if x.get('market') in names and float(x.get('trade_price') or 0)>0]
    if len(tickers)<len(names):
        errors.append(f'전체 시세 일부 누락: {len(tickers)}/{len(names)}종목 수신')
    with lock:
        leaders=list(state.get('midnight',{}).get('leaders',[])) if state.get('midnight',{}).get('active') else []
    with sqlite3.connect(DB) as con:pinned=tracked_priority(con,int(time.time()),max(1,TOP//2))
    with lock: accelerators=list(state.get('momentum',[]))
    chosen,sources=select_deep_markets(tickers,TOP,int(time.time()//INTERVAL),leaders,pinned,accelerators)
    # All-market ticker coverage is distinct from bounded candle analysis.
    market_leaders=sorted(tickers,key=lambda x:float(x.get('signed_change_rate') or 0),reverse=True)[:40]
    market_leaders=[{'market':x['market'],'name':names[x['market']],'price':float(x['trade_price']),'change24':round(float(x.get('signed_change_rate') or 0)*100,2),'turnover24':float(x.get('acc_trade_price_24h') or 0),'deep_selected':x['market'] in sources} for x in market_leaders]
    with lock:state.update(market_leaders=market_leaders,market_updated=int(time.time()))
    results=[]
    with lock:state.update(status=f'심층 분석 중 (0/{len(chosen)})',market_count=len(tickers),deep_count=0,selection_details={k:sum(v==k for v in sources.values()) for k in set(sources.values())})
    # Bounded concurrency reduces serial HTTP latency; no shared SQLite writes in workers.
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures={pool.submit(analyze_market,x,names.get(x['market'],x['market']),sources.get(x['market'],'미확인')):x['market'] for x in chosen}
        for i,f in enumerate(as_completed(futures),1):
            try:results.append(f.result())
            except Exception as e:errors.append(futures[f]+': '+str(e)[:120])
            with lock:state.update(status=f'심층 분석 중 ({i}/{len(chosen)})',deep_count=i)
    if not results:
        errors.append('심층 분석 결과 없음: API 및 캔들 데이터 확인 필요')
    try:
        paper_status=paper_bridge.sync(DB,results,tickers,int(time.time()))
    except Exception as exc:
        paper_status={'error':str(exc)[:160]}
        errors.append('모의거래 기록 실패: '+str(exc)[:120])
    with lock:state['paper_status']=paper_status
    diagnostics=diagnose_signals(results,errors)
    with lock:state['signal_diagnostics']=diagnostics
    results.sort(key=lambda x:({'BUY':0,'PRE':1,'READY':2,'WATCH':3,'WAIT':4,'DATA':5}.get(x.get('status'),6),x.get('tier_rank',3),-x.get('score',0)))
    with sqlite3.connect(DB) as con:
        ov.observe(con,tickers,int(time.time()))
        ov.record(con,results,int(time.time()))
        update_outcomes(con,tickers,int(time.time()))
        record_outcomes(con,results,int(time.time()))
        tracked=maintain_setups(con,results,tickers,int(time.time()))
        setup_events=read_setup_events(con,60)
        summary=summarize_outcomes(con)
        market_audit=audit_market_tickers(con,tickers,results,int(time.time()))
        con.executemany('INSERT INTO snapshots(ts,market,status,score,entry,stop,features,reason) VALUES(?,?,?,?,?,?,?,?)',[(r['time'],r['market'],r['status'],r.get('score',0),r.get('entry',0),r.get('stop',0),json.dumps(r.get('features',{})),','.join(r.get('risk',[])) or r.get('reason','')) for r in results])
    news=fetch_news()
    with lock:state.update(status='대기',last_scan=int(time.time()),errors=errors[:30],candidates=results,news=news,news_updated=int(time.time()),outcome_summary=summary,tracked=tracked,setup_events=setup_events,market_audit=market_audit,audit_updated=int(time.time()),scan_duration=round(time.time()-t0,1))


# KST 23:50–00:30: scan every 30 seconds. No new market session is assumed.
# Baseline snapshots are taken before midnight, not from reset daily percentage fields.
def midnight_active(now=None):
    now=now or datetime.now(timezone(timedelta(hours=9)))
    return now.hour==23 and now.minute>=50 or now.hour==0 and now.minute<30

def midnight_poll_once(baseline, prev_turnover, now=None, getter=None):
    now=now or datetime.now(timezone(timedelta(hours=9)))
    getter=getter or get_json
    markets=getter('/v1/market/all?isDetails=true')
    allowed={x['market']:x.get('korean_name',x['market']) for x in markets if x.get('market','').startswith('KRW-') and not re.search('CAUTION|WARNING',str(x.get('market_warning','')),re.I)}
    ticks=[];errs=[]
    keys=list(allowed)
    for i in range(0,len(keys),80):
        try:
            rows=getter('/v1/ticker?markets='+urllib.parse.quote(','.join(keys[i:i+80]),safe=','))
            if isinstance(rows,list):ticks.extend(rows)
        except Exception as e:errs.append(str(e)[:100])
    results=[]
    for x in ticks:
        m=x.get('market')
        if m not in allowed:continue
        try:
            price=float(x.get('trade_price') or 0);turnover=float(x.get('acc_trade_price_24h') or 0)
            if not (math.isfinite(price) and math.isfinite(turnover) and price>0 and turnover>=0):continue
            if m not in baseline:baseline[m]=price
            old=baseline[m]
            pct=(price/old-1)*100
            # 24h rolling turnover can decline, so this is only a rough flow proxy.
            flow=max(0,turnover-prev_turnover.get(m,turnover))
            prev_turnover[m]=turnover
            results.append({'market':m,'name':allowed[m],'price':price,'baseline':old,'move_pct':round(pct,2),'turnover_delta_est':round(flow),'turnover24':round(turnover),'signal':'OBSERVE','validated':False})
        except (TypeError,ValueError,ZeroDivisionError):continue
    results.sort(key=lambda x:(-x['move_pct'],-x['turnover_delta_est']))
    return results[:20],len(results),errs

def midnight_loop():
    baseline={};turnover={};baseline_day=None
    while True:
        now=datetime.now(timezone(timedelta(hours=9)))
        active=midnight_active(now)
        if active:
            # Keep one baseline for the window spanning 23:50 through 00:29.
            session_day=(now.date() if now.hour==23 else (now-timedelta(days=1)).date()).isoformat()
            if session_day!=baseline_day:
                baseline.clear();turnover.clear();baseline_day=session_day
            try:
                leaders,count,errs=midnight_poll_once(baseline,turnover,now)
                with lock:state['midnight']={'active':True,'status':'자정 집중 감시','last_check':int(time.time()),'baseline_time':session_day+' 관측 시작 (실제 첫 수집 시각은 서버 실행에 따름)','checked':count,'leaders':leaders,'errors':errs,'note':'첫 관측 가격 대비 실제 변화. 거래대금 증분은 24시간 이동합 기반 추정이며 순매수 아님. BUY 미검증.'}
            except Exception as e:
                with lock:state['midnight'].update(active=True,status='수집 오류',errors=[str(e)[:180]])
            time.sleep(30)
        else:
            with lock:state['midnight']['active']=False;state['midnight']['status']='대기 (KST 23:50~00:30)'
            time.sleep(30)

def loop():
    while True:
        try:scan()
        except Exception as e:
            with lock:state.update(status='오류 후 재시도',errors=[str(e)[:250]])
        time.sleep(INTERVAL)


# Chart and rule engine: historical signals are evaluated only with closed candles.
def parse_rule(text):
    text=str(text).strip().replace(' ', '')
    if len(text)>140:raise ValueError('조건이 너무 깁니다')
    m=re.search(r'거래량(?:이|이전보다|평균보다)?([0-9]+(?:\.[0-9]+)?)배',text)
    if m:
        value=float(m.group(1))
        if not 1<=value<=100:raise ValueError('거래량 배수는 1~100 사이여야 합니다')
        return {'kind':'volume','value':value,'label':f'거래량 {value:g}배 이상'}
    m=re.search(r'(?:이격도|5일이격도)(?:가|는)?([0-9]+(?:\.[0-9]+)?)',text)
    if m:
        value=float(m.group(1))
        if not 50<=value<=200:raise ValueError('이격도는 50~200 범위여야 합니다')
        return {'kind':'disparity','value':value,'label':f'5봉 이격도 {value:g} 돌파'}
    m=re.search(r'(\d+)(?:일|봉)선이?(\d+)(?:일|봉)선(?:을|상향)?돌파',text)
    if m:
        fast,slow=map(int,m.groups())
        if not 2<=fast<slow<=120:raise ValueError('이동평균 기간은 2<=단기<장기<=120')
        return {'kind':'cross','fast':fast,'slow':slow,'label':f'{fast}봉선 {slow}봉선 상향돌파'}
    raise ValueError('지원 예시: 거래량 3배, 5일 이격도 103 돌파, 5일선이 20일선 돌파')

def sma(values,period,i):
    if i+1<period:return None
    return sum(values[i+1-period:i+1])/period

def chart_signals(candles,rule=None):
    closes=[c['c'] for c in candles]; volumes=[c['v'] for c in candles];out=[]
    for i in range(1,len(candles)):
        if i<21:continue
        prev_hi=max(x['h'] for x in candles[max(0,i-20):i]); prev_lo=min(x['l'] for x in candles[max(0,i-20):i])
        ma5=sma(closes,5,i);ma20=sma(closes,20,i);old5=sma(closes,5,i-1);old20=sma(closes,20,i-1)
        volbase=sum(volumes[i-20:i])/20
        volratio=volumes[i]/max(volbase,1e-12)
        # Observational technical markers; not trade instructions.
        breakout=closes[i]>prev_hi and closes[i-1]<=max(x['h'] for x in candles[max(0,i-21):i-1]) and volratio>=1.5 and ma5>ma20
        breakdown=closes[i]<prev_lo and volratio>=1.3
        if breakout:out.append({'t':candles[i]['t'],'price':closes[i],'kind':'BUY_WATCH','reason':'20봉 고점 돌파·거래량 증가 (관찰)'})
        if breakdown:out.append({'t':candles[i]['t'],'price':closes[i],'kind':'SELL_WATCH','reason':'20봉 저점 이탈 (위험 관찰)'})
        if rule:
            hit=False
            if rule['kind']=='volume':hit=volratio>=rule['value'] and (volumes[i-1]/max(sum(volumes[i-21:i-1])/20,1e-12))<rule['value']
            if rule['kind']=='disparity':
                a=100*closes[i]/ma5;b=100*closes[i-1]/old5
                hit=a>=rule['value'] and b<rule['value']
            if rule['kind']=='cross':
                f=rule['fast'];g=rule['slow'];af=sma(closes,f,i);ag=sma(closes,g,i);bf=sma(closes,f,i-1);bg=sma(closes,g,i-1)
                hit=all(v is not None for v in (af,ag,bf,bg)) and af>ag and bf<=bg
            if hit:out.append({'t':candles[i]['t'],'price':closes[i],'kind':'CUSTOM','reason':rule['label']})
    return out

def build_chart(market,unit,rule_text=''):
    if not re.fullmatch(r'KRW-[A-Z0-9]{2,20}',market):raise ValueError('잘못된 종목 코드')
    if unit not in (5,15,60,240):raise ValueError('지원하지 않는 봉 주기')
    rule=parse_rule(rule_text) if rule_text.strip() else None
    bars=fetch_candles(market,unit,200)
    if len(bars)<40:raise ValueError('확정 캔들이 부족합니다')
    closes=[x['c'] for x in bars]
    candles=[dict(c,ma5=round(sma(closes,5,i),8) if i>=4 else None,ma20=round(sma(closes,20,i),8) if i>=19 else None,ma60=round(sma(closes,60,i),8) if i>=59 else None) for i,c in enumerate(bars)]
    signals=chart_signals(bars,rule)
    # Outcome is the future CLOSED candle close, strictly after each marker.
    for sig in signals:
        idx=next(i for i,b in enumerate(bars) if b['t']==sig['t'])
        later=bars[idx+1:]
        if later:
            sig['observed_max_pct']=round((max(b['h'] for b in later)/sig['price']-1)*100,2)
            sig['observed_min_pct']=round((min(b['l'] for b in later)/sig['price']-1)*100,2)
            sig['forward_bars']=len(later)
        else:sig['forward_bars']=0
    return {'market':market,'unit':unit,'candles':candles,'signals':signals,'rule':rule,'closed_only':True,'generated_at':int(time.time()),'note':'확정봉만 사용. 화살표는 기술적 관찰 신호이며 검증된 매매 추천이 아님. 후속 최고·최저는 미래 확정봉의 고저점으로 계산하며 체결 수익률이 아님.'}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed=urllib.parse.urlparse(self.path)
        path=parsed.path
        # If configured, protect dashboard and all data APIs with the same token.
        # Browsers can open /?token=... once; JS fetch calls use same-origin cookie.
        if ACCESS_TOKEN and path!="/health":
            import http.cookies, hmac
            cookie=http.cookies.SimpleCookie()
            try:cookie.load(self.headers.get('Cookie',''))
            except Exception:pass
            supplied=urllib.parse.parse_qs(parsed.query).get('token',[''])[0]
            stored=cookie.get('ms_token')
            valid=hmac.compare_digest(supplied,ACCESS_TOKEN) or (stored is not None and hmac.compare_digest(stored.value,ACCESS_TOKEN))
            if not valid:
                self.send_response(401)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write('<meta name="viewport" content="width=device-width,initial-scale=1"><h3>MY SIGNAL AI PRO 접속</h3><form><input type="password" name="token" placeholder="접속 암호" required><button>접속</button></form>'.encode())
                return
            if supplied:
                self.send_response(302)
                self.send_header('Location','/')
                self.send_header('Set-Cookie','ms_token='+ACCESS_TOKEN+'; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000'+('; Secure' if self.headers.get('X-Forwarded-Proto')=='https' else ''))
                self.end_headers()
                return
        if path=='/health':
            data=json.dumps({'ok':True,'engine':'V48-INTEGRATED','last_scan':state['last_scan']}).encode();typ='application/json; charset=utf-8'
        elif path=='/api/status':
            with lock: data=json.dumps(state,ensure_ascii=False,allow_nan=False).encode()
            typ='application/json; charset=utf-8'
        elif path=='/api/chart':
            try:
                q=urllib.parse.parse_qs(parsed.query)
                market=q.get('market',['KRW-BTC'])[0];unit=int(q.get('unit',['15'])[0]);rule=q.get('rule',[''])[0]
                result=build_chart(market,unit,rule)
                data=json.dumps(result,ensure_ascii=False,allow_nan=False).encode();typ='application/json; charset=utf-8'
            except (ValueError,TypeError,OverflowError) as e:
                data=json.dumps({'error':str(e)},ensure_ascii=False).encode();typ='application/json; charset=utf-8'
                self.send_response(400);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            except Exception as e:
                data=json.dumps({'error':'캔들 데이터 조회 실패: '+str(e)[:140]},ensure_ascii=False).encode();typ='application/json; charset=utf-8'
                self.send_response(502);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        elif path=='/api/setup-events':
            with sqlite3.connect(DB) as con:rows=read_setup_events(con,100)
            data=json.dumps(rows,ensure_ascii=False).encode();typ='application/json; charset=utf-8'
        elif path=='/api/tracked':
            with sqlite3.connect(DB) as con:rows=read_setups(con,int(time.time()))
            data=json.dumps({'rows':rows,'note':'최초 관찰가 대비 변화. BUY는 기술 조건 신호이며 수익성 미검증. 오래된 분석은 별도 표시.'},ensure_ascii=False).encode();typ='application/json; charset=utf-8'
        elif path=='/api/diagnostics':
            with lock: d=dict(state.get('signal_diagnostics',{}))
            data=json.dumps(d,ensure_ascii=False).encode();typ='application/json; charset=utf-8'
        elif path=='/api/momentum':
            with lock: rows=list(state['momentum']);ts=state['momentum_updated']
            data=json.dumps({'rows':rows,'updated':ts,'note':'45~900초 간격 시세 비교. BUY 신호가 아니며 호가·실제 체결 흐름 분석 아님'},ensure_ascii=False).encode();typ='application/json; charset=utf-8'
        elif path=='/api/audit':
            with sqlite3.connect(DB) as con:
                rows=get_audit_rows(con)
            data=json.dumps({'rows':rows,'note':'첫 관찰 시점 기준. 과거 데이터가 없는 기존 기록은 검증 불가. 가격 샘플 사이 고저점 누락 가능.'},ensure_ascii=False).encode();typ='application/json; charset=utf-8'
        elif path=='/api/paper':
            try:
                data=json.dumps(paper_bridge.status(DB),ensure_ascii=False,allow_nan=False).encode();typ='application/json; charset=utf-8'
            except Exception as exc:
                data=json.dumps({'error':str(exc)[:160]}).encode();typ='application/json; charset=utf-8'
                self.send_response(503);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        elif path=='/api/validation':
            with sqlite3.connect(DB) as con:result=ov.report(con)
            data=json.dumps(result,ensure_ascii=False,allow_nan=False).encode();typ='application/json; charset=utf-8'
        elif path=='/api/outcomes':
            with sqlite3.connect(DB) as con:
                rows=con.execute('SELECT market,first_seen,last_seen,entry,last_price,max_pct,min_pct,status,signal_type FROM signal_outcomes ORDER BY first_seen DESC LIMIT 100').fetchall()
            data=json.dumps([dict(zip(('market','first_seen','last_seen','entry','last_price','max_pct','min_pct','status','signal_type'),r)) for r in rows],ensure_ascii=False).encode();typ='application/json; charset=utf-8'
        elif path=='/api/history':
            with sqlite3.connect(DB) as con:
                rows=con.execute('SELECT ts,market,status,score,entry,stop,reason FROM snapshots ORDER BY id DESC LIMIT 200').fetchall()
            data=json.dumps([dict(zip(('ts','market','status','score','entry','stop','reason'),r)) for r in rows],ensure_ascii=False).encode();typ='application/json; charset=utf-8'
        elif path=='/':data=(ROOT/'index.html').read_bytes();typ='text/html; charset=utf-8'
        else:self.send_error(404);return
        self.send_response(200);self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'");self.send_header('Content-Type',typ);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass

if __name__=='__main__':
    db_init();threading.Thread(target=loop,daemon=True).start();threading.Thread(target=midnight_loop,daemon=True).start();threading.Thread(target=pulse_loop,daemon=True).start()
    print(f'V45 http://127.0.0.1:{PORT} (모의 관찰 전용; 자동매매 없음)',flush=True)
    http.server.ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
