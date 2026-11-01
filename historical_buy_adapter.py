"""Historical adapter to the EXISTING server.analyze, not a replacement BUY formula.

Inputs are complete closed 5m/15m/60m bars with keys ts/open/high/low/close/volume.
The 24h change is calculated only when a complete 24h 5m baseline exists.
The live multi-timeframe v49 gate needs additional frames and is NOT replayed here;
therefore output is a *base BUY candidate*, never a verified live BUY.
"""

def to_server_candles(bars, close_ts):
    return [{'t':r['ts'],'o':r['open'],'h':r['high'],'l':r['low'],
             'c':r['close'],'v':r['volume']} for r in bars
            if r['ts']+r['duration_sec']<=close_ts]

def historical_base_signal(server_analyze, bars5, bars15, bars60, close_ts):
    f5=to_server_candles(bars5,close_ts)
    f15=to_server_candles(bars15,close_ts)
    f60=to_server_candles(bars60,close_ts)
    if min(map(len,(f5,f15,f60)))<35 or len(f5)<289:
        return {'status':'INSUFFICIENT_HISTORY','reconstructed':True,
                'reason':'minimum history not reached',
                'available_counts':{'5':len(f5),'15':len(f15),'60':len(f60)}}
    # Exchange candle APIs can omit no-trade periods; do not label 289 sparse
    # observations as a continuous 24-hour window.
    for series, duration, required in ((f5,300,289),(f15,900,35),(f60,3600,35)):
        tail=series[-required:]
        if any(b['t']-a['t']!=duration for a,b in zip(tail,tail[1:])):
            return {'status':'INSUFFICIENT_HISTORY','reconstructed':True,
                    'reason':f'missing {duration//60}m candles in required lookback window'}
    # 288 complete 5m intervals = 24 hours; never current ticker.
    price=f5[-1]['c']
    baseline=f5[-289]['c']
    change24=(price/baseline-1)*100
    result=server_analyze(f5[-120:],f15[-120:],f60[-120:],price,change24)
    return {'status':result['status'],'base_buy_candidate':result['status']=='BUY',
            'reconstructed':True,'full_live_buy_verified':False,
            'reason':'V49 multi-timeframe gate, ticker timing and live selection not replayed',
            'close_ts':close_ts,'change24':change24,
            'entry':result.get('entry'),'stop':result.get('stop'),
            'targets':result.get('targets',[]),'buy_gates':result.get('buy_gates',{})}
