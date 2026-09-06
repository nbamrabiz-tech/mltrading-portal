# ── Configuration & Constants ─────────────────
import pytz

EST = pytz.timezone("America/New_York")

# ── Persona strategies ────────────────────────
STRATEGIES = {
    "marcus_rev":  "📈 5-min ORB",
    "james_over":  "📊 EMA 9/21 Crossover",
    "sarah_fomo":  "🚀 Momentum Chasing",
    "alex_bore":   "↔️ Support/Resistance Fade",
    "david_greed": "💰 Intraday Swing",
    "emma_hesit":  "📍 FVG Entries",
    "sam_disc":    "✅ Rules-Based System",
    "sunny":       "🧠 Matrix System",
}

# ── Emotion options ───────────────────────────
EMOTION_OPTIONS = {
    "😌 Calm/Focused":    1,
    "😊 Confident":       2,
    "😤 Eager/Excited":   4,
    "😬 Itchy/Restless":  5,
    "😰 Anxious/Nervous": 7,
    "😠 Angry/Frustrated":8,
    "🤑 Greedy":          7,
    "😱 FOMO":            6,
    "😑 Bored":           4,
}

EXIT_EMOTION_OPTIONS = {
    "😌 Calm":       1,
    "😊 Satisfied":  2,
    "😤 Eager":      4,
    "😬 Restless":   5,
    "😰 Anxious":    7,
    "😠 Frustrated": 8,
    "🤑 Greedy":     7,
    "😱 FOMO":       6,
    "😑 Relieved":   3,
}

# ── Behavioral pattern plain English ──────────
BEHAVIOR_PLAIN = {
    "Revenge Trading":
        ("traded too soon after a loss",
         False,
         "stop → 30 min break after every loss"),
    "Overtrading":
        ("took too many trades",
         False,
         "stop → max 3 trades per day"),
    "Rule Violation":
        ("skipped pre-trade checks",
         False,
         "fix → check system before every trade"),
    "Emotional Exit":
        ("exited on emotion not plan",
         False,
         "fix → set exit level before entering"),
    "FOMO":
        ("chased price without a setup",
         False,
         "stop → wait for price to come to you"),
    "Traded Against Edge":
        ("traded when system said sit out",
         False,
         "fix → trust the No Edge signal"),
    "Wrong Setup for Day":
        ("used wrong strategy for day type",
         False,
         "fix → match setup to today's edge"),
    "Respected No Edge":
        ("sat out correctly on No Edge days",
         True, ""),
    "Greed":
        ("held losers too long hoping for reversal",
         False,
         "fix → honour your stop every time"),
    "Hesitant Trading":
        ("exited winners early before target",
         False,
         "fix → trust your target, "
         "use breakeven stop"),
    "Boredom Trading":
        ("took trades without a clear setup",
         False,
         "stop → no setup, no trade"),
}

# ── Account multipliers ───────────────────────
TICKER_MULTIPLIERS = {
    "MES": 5,
    "ES":  50,
    "MNQ": 2,
    "NQ":  20,
    "MYM": 0.5,
    "YM":  5,
    "M2K": 5,
    "RTY": 50,
    "SPY": 1,
    "QQQ": 1,
}

# ── Colors ────────────────────────────────────
RED    = "#CC3333"
GREEN  = "#2E7D32"
ORANGE = "#E65100"
BLUE   = "#0066CC"
GREY   = "#888888"


