#!/usr/bin/env python3
"""MY SIGNAL AI PRO V37: research-only Bithumb scanner, stdlib server."""
import json, os, time, math, sqlite3, threading, urllib.request, urllib.parse, http.server, pathlib, statistics, re, html, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
ROOT=pathlib.Path(__file__).parent
DATA_DIR=pathlib.Path(os.getenv("DATA_DIR",str(ROOT/"data")))
DATA_DIR.mkdir(parents=True,exist_ok=True)
DB=DATA_DIR/"signals.db"
ACCESS_TOKEN=os.getenv("ACCESS_TOKEN", "").strip()
PORT=int(os.getenv('PORT','8765'))
INTERVAL=max(60,int(os.getenv('SCAN_SECONDS','120')))
TOP=max(5,min(80,int(os.getenv('DEEP_MARKETS','40'))))
BASE='https://api.bithumb.com'
NEWS_FEEDS=[('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/'),('Cointelegraph','https://cointelegraph.com/rss')]
lock=threading.Lock()
state={'status':'대기','last_scan':None,'errors':[],'market_count':0,'deep_count':0,'news_updated':None,'news':[],'candidates':[],'scan_seconds':INTERVAL,'engine_version':'V37-SIGNAL','selection_details':{},'outcome_summary':{},'market_audit':[],'market_leaders':[],'market_updated':None,'audit_updated':None,'buy_enabled':True,'news_ai_enabled':False,'social_enabled':False,'midnight':{'active':False,'status':'대기','last_check':None,'baseline_time':None,'checked':0,'leaders':[],'errors':[],'note':'자정 전후 실제 가격 변화 감시 · 매수 신호 아님'}}

def get_json(path):
    req=urllib.request.Request(BASE+path,headers={'User-Agent':'MY-SIGNAL-V35/0.1','Accept':'application/json'})
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
    if buy_setup:status='BUY'
    elif pre_setup:status='PRE'
    entry=price
    stop=min(x['l'] for x in a[-6:])
    if stop>=entry or (entry-stop)/entry*100>8:stop=entry-max(1.5*atr,entry*.025)
    riskpct=max(0,(entry-stop)/entry*100)
    # Heuristic opportunity tiers are NOT predicted returns or validated probabilities.
    breakout_setup=(compression<=8 and .9<=vol<=4.5 and trend and higher and rise8<7 and change24<=15)
    if breakout_setup and candle_strength>=.55 and not risk:
        tier='50%+ 급등 전조 관찰';tier_rank=0;horizon='수일 이상 · 기간/도달 미검증'
    elif trend and higher and vol>=1.3 and rise8<9 and change24<=20 and len(risk)<=1:
        tier='10~30% 상승 관찰';tier_rank=1;horizon='2~3일 · 도달 미검증'
    else:
        tier='3~10% 단기 관찰';tier_rank=2;horizon='단기 · 도달 미검증'
    medium_targets=[{'pct':pct,'price':round(entry*(1+pct/100),8)} for pct in ((10,30,50) if tier_rank==0 else (10,20,30) if tier_rank==1 else (3,5,10))]
    return {'status':status,'score':score,'opportunity_tier':tier,'tier_rank':tier_rank,'horizon_note':horizon,'medium_targets':medium_targets,'tier_disclaimer':'기술적 조건 분류일 뿐 목표 도달 예측이나 매수 추천 아님','entry':entry,'stop':round(stop,8),'stop_pct':round(riskpct,2),'targets':[round(entry*x,8) for x in (1.03,1.10,1.50)],'tp_levels':[{'price':round(entry+max(entry-stop,entry*.005)*mult,8),'pct':round(max(entry-stop,entry*.005)*mult/entry*100,2)} for mult in (1,1.5,2)],'decision':'BUY' if status=='BUY' else 'PRE' if status=='PRE' else 'WAIT' if status=='WAIT' else 'OBSERVE','decision_reason':('확정 5분봉 저항 돌파 + 거래량 1.3배 + 다중 추세 일치 (기술 신호, 수익 미검증)' if status=='BUY' else '추세·압축·거래량 조건 충족 (매수 아님)' if status=='PRE' else ('위험 조건 감지: '+', '.join(risk)) if risk else '진입 조건 미충족'),'target_note':'관찰 목표 +3/+10/+50%; 실현 가능성 검증 전','risk':risk,'reason':('초기 거래량·추세 조건 관찰' if early else '초기 상승 조건 미충족'),'features':{'vol_ratio':round(vol,2),'breakout_confirmed':confirmed_breakout,'rise5_pct':round(rise5,2),'rise8_pct':round(rise8,2),'atr_pct':round(atr_pct,2),'compression_pct':round(compression,2),'resistance':round(resistance,8),'resistance_distance_pct':round(dist,2),'candle_strength':round(candle_strength,2),'trend5_15':trend,'trend60':higher}}

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
        con.execute('CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY,ts INTEGER,market TEXT,status TEXT,score INTEGER,entry REAL,stop REAL,features TEXT,reason TEXT)')
        con.execute('CREATE INDEX IF NOT EXISTS ix_market_time ON snapshots(market,ts)')
        con.execute('CREATE TABLE IF NOT EXISTS signal_outcomes(id INTEGER PRIMARY KEY,market TEXT,day TEXT,first_seen INTEGER,last_seen INTEGER,entry REAL,last_price REAL,max_pct REAL,min_pct REAL,status TEXT,signal_type TEXT,UNIQUE(market,day))')
        # Safe additive migration: existing signal records remain untouched.
        cols={row[1] for row in con.execute('PRAGMA table_info(signal_outcomes)')}
        for name,typ in [('first_change24','REAL'),('first_score','INTEGER'),('first_source','TEXT'),('first_class','TEXT'),('observations','INTEGER DEFAULT 0')]:
            if name not in cols:con.execute(f'ALTER TABLE signal_outcomes ADD COLUMN {name} {typ}')
        con.execute('CREATE TABLE IF NOT EXISTS market_audit(id INTEGER PRIMARY KEY, ts INTEGER, market TEXT, price REAL, change24 REAL, turnover24 REAL, analysis_status TEXT, selection_source TEXT)')
        con.execute('CREATE INDEX IF NOT EXISTS ix_audit_market_ts ON market_audit(market,ts)')


def select_deep_markets(tickers, top, cycle, midnight_leaders=None):
    """Bounded selection with liquid baseline, midnight leaders and rotation.

    This only improves coverage; it does not predict future returns.
    """
    eligible={x['market']:x for x in tickers if x.get('market')}
    ranked=sorted(eligible.values(),key=lambda x:float(x.get('acc_trade_price_24h') or 0),reverse=True)
    picked=[];sources={}
    def add(x,reason):
        if x and x['market'] not in sources and len(picked)<top:
            picked.append(x);sources[x['market']]=reason
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
    with lock:
        leaders=list(state.get('midnight',{}).get('leaders',[])) if state.get('midnight',{}).get('active') else []
    chosen,sources=select_deep_markets(tickers,TOP,int(time.time()//INTERVAL),leaders)
    # All-market ticker coverage is distinct from bounded candle analysis.
    market_leaders=sorted(tickers,key=lambda x:float(x.get('signed_change_rate') or 0),reverse=True)[:40]
    market_leaders=[{'market':x['market'],'name':names[x['market']],'price':float(x['trade_price']),'change24':round(float(x.get('signed_change_rate') or 0)*100,2),'turnover24':float(x.get('acc_trade_price_24h') or 0),'deep_selected':x['market'] in sources} for x in market_leaders]
    with lock:state.update(market_leaders=market_leaders,market_updated=int(time.time()))
    results=[]
    with lock:state.update(status=f'심층 분석 중 (0/{len(chosen)})',market_count=len(tickers),deep_count=0,selection_details={k:sum(v==k for v in sources.values()) for k in set(sources.values())})
    for i,x in enumerate(chosen):
        m=x['market'];p=float(x['trade_price'])
        try:
            c5=fetch_candles(m,5);time.sleep(.14)
            c15=fetch_candles(m,15);time.sleep(.14)
            c60=fetch_candles(m,60);time.sleep(.14)
            r=analyze(c5,c15,c60,p,float(x.get('signed_change_rate') or 0)*100)
            r.update(selection_source=sources.get(m,'미확인'),market=m,name=names[m],price=p,change24=round(float(x.get('signed_change_rate') or 0)*100,2),volume24=float(x.get('acc_trade_price_24h') or 0),time=int(time.time()))
            results.append(r)
        except Exception as e:errors.append(m+': '+str(e)[:120])
        with lock:state.update(status=f'심층 분석 중 ({i+1}/{len(chosen)})',deep_count=i+1)
    results.sort(key=lambda x:({'BUY':0,'PRE':1,'READY':2,'WATCH':3,'WAIT':4,'DATA':5}.get(x.get('status'),6),x.get('tier_rank',3),-x.get('score',0)))
    with sqlite3.connect(DB) as con:
        update_outcomes(con,tickers,int(time.time()))
        record_outcomes(con,results,int(time.time()))
        summary=summarize_outcomes(con)
        market_audit=audit_market_tickers(con,tickers,results,int(time.time()))
        con.executemany('INSERT INTO snapshots(ts,market,status,score,entry,stop,features,reason) VALUES(?,?,?,?,?,?,?,?)',[(r['time'],r['market'],r['status'],r.get('score',0),r.get('entry',0),r.get('stop',0),json.dumps(r.get('features',{})),','.join(r.get('risk',[])) or r.get('reason','')) for r in results])
    news=fetch_news()
    with lock:state.update(status='대기',last_scan=int(time.time()),errors=errors[:30],candidates=results,news=news,news_updated=int(time.time()),outcome_summary=summary,market_audit=market_audit,audit_updated=int(time.time()),scan_duration=round(time.time()-t0,1))


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
            data=json.dumps({'ok':True,'engine':'V37-SIGNAL','last_scan':state['last_scan']}).encode();typ='application/json; charset=utf-8'
        elif path=='/api/status':
            with lock: data=json.dumps(state,ensure_ascii=False).encode()
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
        elif path=='/api/audit':
            with sqlite3.connect(DB) as con:
                rows=get_audit_rows(con)
            data=json.dumps({'rows':rows,'note':'첫 관찰 시점 기준. 과거 데이터가 없는 기존 기록은 검증 불가. 가격 샘플 사이 고저점 누락 가능.'},ensure_ascii=False).encode();typ='application/json; charset=utf-8'
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
    db_init();threading.Thread(target=loop,daemon=True).start();threading.Thread(target=midnight_loop,daemon=True).start()
    print(f'V35 http://127.0.0.1:{PORT} (모의 관찰 전용; 자동매매 없음)',flush=True)
    http.server.ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
