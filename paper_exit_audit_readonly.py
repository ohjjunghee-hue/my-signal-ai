"""Read-only paper exit sensitivity analysis. No DB writes or exchange orders."""
import math

def compare_exit(entry, stop, tp1, sampled_price, reason, fee_pct=0.2, stress_pct=0.5):
    values=(entry,stop,tp1,sampled_price,fee_pct,stress_pct)
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in values):
        raise ValueError("nonfinite input")
    if not (0 < stop < entry < tp1 and sampled_price > 0 and fee_pct >= 0 and stress_pct >= 0):
        raise ValueError("invalid price or fee")
    if reason not in ("STOP","TP1"):
        raise ValueError("invalid reason")
    threshold=stop if reason=="STOP" else tp1
    ideal=100*(threshold/entry-1)-fee_pct
    sampled=100*(sampled_price/entry-1)-fee_pct
    return {
        "ideal_threshold_net_pct":round(ideal,6),
        "sampled_price_net_pct":round(sampled,6),
        "sampled_stress_net_pct":round(sampled-stress_pct,6),
        "execution_verified":False,
        "note":"Ticker sample is not an executable fill. Intrabar path, spread and slippage unknown."
    }
