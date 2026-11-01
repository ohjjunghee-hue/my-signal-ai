"""V49 higher-timeframe risk gate. Fail closed on unavailable or malformed data."""
import math
import statistics

def evaluate(frames):
    required=("4h","day","week","month")
    missing=[k for k in required if k not in frames or len(frames[k])<20]
    if missing:
        return {"allowed":False,"verdict":"DATA","reasons":["상위 시간대 데이터 부족: "+", ".join(missing)],"frames":{}}
    detail={}
    reasons=[]
    for name in required:
        candles=frames[name]
        closes=[]
        for c in candles:
            try:
                p=float(c["c"])
                if not math.isfinite(p) or p<=0:raise ValueError()
                closes.append(p)
            except (KeyError,TypeError,ValueError):
                return {"allowed":False,"verdict":"DATA","reasons":[name+" 가격 오류"],"frames":detail}
        last=closes[-1]
        ma20=statistics.mean(closes[-20:])
        prior=statistics.mean(closes[-20:-10])
        recent=statistics.mean(closes[-10:])
        declining=recent<prior
        below=last<ma20
        detail[name]={"close":round(last,8),"ma20":round(ma20,8),
                      "below_ma20":below,"declining":declining}
        if name in ("4h","day") and below and declining:
            reasons.append(name+" 20봉 평균 아래·하락 지속")
        if name=="week" and below and declining:
            reasons.append("주봉 하락 추세")
        if name=="month" and below and declining:
            reasons.append("월봉 하락 추세")
    allowed=not reasons
    return {"allowed":allowed,"verdict":"PASS" if allowed else "AVOID",
            "reasons":reasons,"frames":detail}
