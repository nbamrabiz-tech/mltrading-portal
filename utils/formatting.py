
# ── Formatting utilities ─────────

def score_color(score):
    if score >= 80: return "#0066CC"
    if score >= 65: return "#4CAF50"
    if score >= 50: return "#FF8C00"
    if score >= 35: return "#FF5722"
    return "#CC0000"



def card(content, border_color="#0066CC",
         bg="#F8F9FA"):
    return (
        f'<div style="background:{bg};'
        f'padding:14px;border-radius:8px;'
        f'border-left:4px solid {border_color};'
        f'margin-bottom:8px;">'
        f'{content}</div>'
    )

def prob_bar(pct, color, width=150):
    return (
        f'<div style="background:#E8E8E8;'
        f'border-radius:4px;width:{width}px;'
        f'height:8px;margin-top:4px;">'
        f'<div style="background:{color};'
        f'width:{min(pct,100)}%;height:8px;'
        f'border-radius:4px;"></div></div>'
    )

def edge_color(edge):
    if not edge: return "#888888"
    if "Long Bias"  in edge: return "#0066CC"
    if "Short Bias" in edge: return "#CC0000"
    if "Range Bias" in edge: return "#FF8C00"
    return "#888888"

def candle_color(d):
    if "Bullish" in str(d): return "#0066CC"
    if "Bearish" in str(d): return "#CC0000"
    return "#888888"

def score_color(score):
    if score >= 80: return "#0066CC"
    if score >= 65: return "#4CAF50"
    if score >= 50: return "#FF8C00"
    if score >= 35: return "#FF5722"
    return "#CC0000"

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

