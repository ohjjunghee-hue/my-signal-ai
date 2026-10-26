#!/usr/bin/env python3
"""MY SIGNAL AI PRO V33: research-only Bithumb scanner, stdlib server."""
import json, os, time, math, sqlite3, threading, urllib.request, urllib.parse, http.server, pathlib, statistics, re, html, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
ROOT=pathlib.Path(__file__).parent
DATA_DIR=pathlib.Path(os.getenv("DATA_DIR",str(ROOT/"data")))
DATA_DIR.mkdir(parents=True,exist_ok=True)
DB=DATA_DIR/"signals.db"
ACCESS_TOKEN=os.getenv("ACCESS_TOKEN", "").strip()
PORT=int(os.getenv('PORT','8765'))
INTERVAL=max(120,int(os.getenv('SCAN_SECONDS','300')))
TOP=max(5,min(60,int(os.getenv('DEEP_MARKETS','25'))))
BASE='https://api.bithumb.com'
NEWS_FEEDS=[('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/'),('Cointelegraph','https://cointelegraph.com/rss')]
lock=threading.Lock()
state={'status':'대기','last_scan':None,'errors':[],'market_count':0,'deep_count':0,'news_updated':None,'news':[],'candidates':[],'scan_seconds':INTERVAL,'engine_version':'V33','buy_enabled':False,'news_ai_enabled':False,'social_enabled':False,'midnight':{'active':False,'status':'대기','last_check':None,'baseline_time':None,'checked':0,'leaders':[],'errors':[],'note':'자정 전후 실제 가격 변화 감시 · 매수 신호 아님'}}

def get_json(path):
    req=urllib.request.Request(BASE+path,headers={'User-Agent':'MY-SIGNAL-V33/0.1','Accept':'application/json'})
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
    # A real BUY requires independently validated forward outcomes; disabled by design.
    if risk:status='WAIT'
    entry=price
    stop=min(x['l'] for x in a[-6:])
    if stop>=entry or (entry-stop)/entry*100>8:stop=entry-max(1.5*atr,entry*.025)
    riskpct=max(0,(entry-stop)/entry*100)
    return {'status':status,'score':score,'entry':entry,'stop':round(stop,8),'stop_pct':round(riskpct,2),'targets':[round(entry*x,8) for x in (1.03,1.10,1.50)],'tp_levels':[{'price':round(entry+max(entry-stop,entry*.005)*mult,8),'pct':round(max(entry-stop,entry*.005)*mult/entry*100,2)} for mult in (1,1.5,2)],'decision':'WAIT' if status=='WAIT' else 'REJECT' if status=='DATA' else 'OBSERVE','decision_reason':('위험 조건 감지: '+', '.join(risk)) if risk else ('확정봉 부족' if status=='DATA' else '실거래 BUY 신호 미검증: 관찰 전용'),'target_note':'관찰 목표 +3/+10/+50%; 실현 가능성 검증 전','risk':risk,'reason':('초기 거래량·추세 조건 관찰' if early else '초기 상승 조건 미충족'),'features':{'vol_ratio':round(vol,2),'rise5_pct':round(rise5,2),'rise8_pct':round(rise8,2),'atr_pct':round(atr_pct,2),'compression_pct':round(compression,2),'resistance':round(resistance,8),'resistance_distance_pct':round(dist,2),'candle_strength':round(candle_strength,2),'trend5_15':trend,'trend60':higher}}

def fetch_news():
    items=[]
    for source,url in NEWS_FEEDS:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 MY-SIGNAL-V33'})
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
    # Select both liquid and pre-breakout candidates; do not equate selection with full-market candle coverage.
    tickers.sort(key=lambda x:float(x.get('acc_trade_price_24h') or 0),reverse=True)
    # Rotate deep analysis across liquid markets to avoid permanently ignoring smaller coins.
    # A baseline liquid tranche is always checked; remaining slots rotate by scan number.
    liquid=max(3,TOP//2)
    baseline=tickers[:liquid]
    remaining=tickers[liquid:]
    cycle=int(time.time()//INTERVAL)
    start=(cycle*max(1,TOP-liquid))%max(1,len(remaining))
    rotation=(remaining[start:]+remaining[:start])[:max(0,TOP-liquid)]
    chosen=baseline+rotation
    results=[]
    with lock:state.update(status=f'심층 분석 중 (0/{len(chosen)})',market_count=len(tickers),deep_count=0)
    for i,x in enumerate(chosen):
        m=x['market'];p=float(x['trade_price'])
        try:
            c5=fetch_candles(m,5);time.sleep(.14)
            c15=fetch_candles(m,15);time.sleep(.14)
            c60=fetch_candles(m,60);time.sleep(.14)
            r=analyze(c5,c15,c60,p,float(x.get('signed_change_rate') or 0)*100)
            r.update(market=m,name=names[m],price=p,change24=round(float(x.get('signed_change_rate') or 0)*100,2),volume24=float(x.get('acc_trade_price_24h') or 0),time=int(time.time()))
            results.append(r)
        except Exception as e:errors.append(m+': '+str(e)[:120])
        with lock:state.update(status=f'심층 분석 중 ({i+1}/{len(chosen)})',deep_count=i+1)
    results.sort(key=lambda x:-x.get('score',0))
    with sqlite3.connect(DB) as con:
        con.executemany('INSERT INTO snapshots(ts,market,status,score,entry,stop,features,reason) VALUES(?,?,?,?,?,?,?,?)',[(r['time'],r['market'],r['status'],r.get('score',0),r.get('entry',0),r.get('stop',0),json.dumps(r.get('features',{})),','.join(r.get('risk',[])) or r.get('reason','')) for r in results])
    news=fetch_news()
    with lock:state.update(status='대기',last_scan=int(time.time()),errors=errors[:30],candidates=results,news=news,news_updated=int(time.time()),scan_duration=round(time.time()-t0,1))


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
                with lock:state['midnight']={'active':True,'status':'자정 집중 감시','last_check':int(time.time()),'baseline_time':session_day+' 23:50 KST (첫 관측 가격)','checked':count,'leaders':leaders,'errors':errs,'note':'첫 관측 가격 대비 실제 변화. 거래대금 증분은 24시간 이동합 기반 추정이며 순매수 아님. BUY 미검증.'}
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
            data=json.dumps({'ok':True,'engine':'V33','last_scan':state['last_scan']}).encode();typ='application/json; charset=utf-8'
        elif path=='/api/status':
            with lock: data=json.dumps(state,ensure_ascii=False).encode()
            typ='application/json; charset=utf-8'
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
    print(f'V33 http://127.0.0.1:{PORT} (모의 관찰 전용; 자동매매 없음)',flush=True)
    http.server.ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
