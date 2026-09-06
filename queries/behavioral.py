# ── Behavioral queries ───────────
import streamlit as st
from db import get_engine
from datetime import date, timedelta
from sqlalchemy import text

def get_behavioral_data(uid=None):
    start = date.today() - timedelta(days=30)
    if uid is None:
        uid = st.session_state.get("user_id", 1)
    try:
        with get_engine().connect() as conn:
            events = conn.execute(text("""
                SELECT behavior_type,
                       COUNT(*) as cnt,
                       SUM(financial_cost) as cost
                FROM behavioral_events
                WHERE market='US'
                AND user_id=:uid
                AND event_date >= :start
                GROUP BY behavior_type
                ORDER BY cnt DESC LIMIT 10
            """), {
                "start": str(start),
                "uid": uid
            }).fetchall()

            scores = conn.execute(text("""
                SELECT overall_score,
                       behavioral_state,
                       score_date
                FROM behavioral_scores
                WHERE market='US'
                ORDER BY score_date DESC LIMIT 7
            """)).fetchall()

            today_b = conn.execute(text("""
                SELECT behavior_type, severity,
                       description,
                       COUNT(*) as cnt
                FROM behavioral_events
                WHERE market='US'
                AND user_id=:uid
                AND event_date=:td
                GROUP BY behavior_type,
                         severity, description
                LIMIT 10
            """), {
                "td": str(date.today()),
                "uid": uid
            }).fetchall()

            today_t = conn.execute(text("""
                SELECT COUNT(*),
                       SUM(CASE WHEN pnl>0
                           THEN 1 ELSE 0 END),
                       SUM(pnl),
                       AVG(emotional_state),
                       SUM(CASE WHEN pnl<0
                           THEN 1 ELSE 0 END)
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND trade_date=:td
            """), {
                "td": str(date.today()),
                "uid": uid
            }).fetchone()

        return events, scores, today_b, today_t
    except:
        return [], [], [], None

def calculate_daily_score(target_date=None):
    """
    0-100 composite behavioral score.
    5 components weighted by importance.
    Saves to behavioral_scores table.
    Returns score dict or None if no trades.

    Component breakdown:
    1. System adherence  25 pts — checked system?
    2. Rule adherence    25 pts — followed plan?
    3. Emotion control   20 pts — avg emotion level
    4. Trade discipline  20 pts — trade count + losses
    5. Behavior penalty  10 pts — high severity events
    """
    if target_date is None:
        target_date = date.today()

    try:
        with get_engine().connect() as conn:
            trades = conn.execute(text("""
                SELECT pnl, emotional_state,
                       followed_plan, checked_system,
                       pre_trade_gate, created_at
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND trade_date=:td
                ORDER BY created_at ASC
            """), {
                "td":  str(target_date),
                "uid": st.session_state.get("user_id",1)
            }).fetchall()

            behaviors = conn.execute(text("""
                SELECT behavior_type, severity
                FROM behavioral_events
                WHERE market='US'
                AND user_id=:uid
                AND event_date=:td
            """), {"td": str(target_date), "uid": st.session_state.get("user_id",1)}).fetchall()

        if not trades:
            return None

        total        = len(trades)
        pnls         = [float(t[0]) for t in trades]
        emotions     = [int(t[1]) for t in trades]
        plans        = [bool(t[2]) for t in trades]
        systems      = [bool(t[3]) for t in trades]
        losses       = sum(1 for p in pnls if p < 0)
        hi_behaviors = sum(1 for b in behaviors
                           if b[1] == "High")

        # Component 1 — System adherence (25 pts)
        sys_rate = sum(systems) / total
        if sys_rate == 1.0:    sys_score = 25
        elif sys_rate >= 0.75: sys_score = 18
        elif sys_rate >= 0.5:  sys_score = 10
        else:                  sys_score = 0

        # Component 2 — Rule adherence (25 pts)
        plan_rate = sum(plans) / total
        if plan_rate == 1.0:    plan_score = 25
        elif plan_rate >= 0.75: plan_score = 18
        elif plan_rate >= 0.5:  plan_score = 10
        else:                   plan_score = 0

        # Component 3 — Emotion control (20 pts)
        avg_emotion = sum(emotions) / total
        if avg_emotion <= 4:   emo_score = 20
        elif avg_emotion <= 5: emo_score = 17
        elif avg_emotion <= 6: emo_score = 12
        elif avg_emotion <= 7: emo_score = 6
        else:                  emo_score = 0

        # Component 4 — Trade discipline (20 pts)
        if losses >= 2:  disc_score = 0
        elif total <= 3: disc_score = 20
        elif total == 4: disc_score = 12
        elif total == 5: disc_score = 6
        else:            disc_score = 0

        # Component 5 — Behavior penalty (10 pts)
        if hi_behaviors == 0:   beh_score = 10
        elif hi_behaviors == 1: beh_score = 5
        else:                   beh_score = 0

        total_score = (sys_score + plan_score +
                       emo_score + disc_score +
                       beh_score)

        if total_score >= 80:   state = "Excellent"
        elif total_score >= 65: state = "Good"
        elif total_score >= 50: state = "Fair"
        elif total_score >= 35: state = "Poor"
        else:                   state = "Critical"

        # Save to behavioral_scores
        with get_engine().connect() as conn:
            conn.execute(text("""
                INSERT INTO behavioral_scores(
                    market, score_date,
                    overall_score,
                    behavioral_state,
                    total_trades,
                    system_adherence_score,
                    rule_adherence_score,
                    emotion_control_score,
                    discipline_score)
                VALUES('US',:sd,:os,:bs,
                       :tt,:ss,:rs,:es,:ds)
                ON CONFLICT (market, score_date)
                DO UPDATE SET
                    overall_score=:os,
                    behavioral_state=:bs,
                    total_trades=:tt,
                    system_adherence_score=:ss,
                    rule_adherence_score=:rs,
                    emotion_control_score=:es,
                    discipline_score=:ds
            """), {
                "sd": str(target_date),
                "os": total_score,
                "bs": state,
                "tt": total,
                "ss": sys_score,
                "rs": plan_score,
                "es": emo_score,
                "ds": disc_score
            })
            conn.commit()

        return {
            "score":        total_score,
            "state":        state,
            "total":        total,
            "sys_score":    sys_score,
            "plan_score":   plan_score,
            "emo_score":    emo_score,
            "disc_score":   disc_score,
            "beh_score":    beh_score,
            "avg_emotion":  round(avg_emotion, 1),
            "losses":       losses,
            "hi_behaviors": hi_behaviors
        }

    except Exception as e:
        return None


def get_streaks():
    """
    Detects win/loss streaks from trade journal.
    Also detects prediction streaks from learning log.
    Returns streak info and warnings.
    """
    result = {
        "trade_streak":      0,
        "trade_streak_type": None,
        "pred_streak":       0,
        "pred_streak_type":  None,
        "warnings":          []
    }

    try:
        # Trade streaks
        with get_engine().connect() as conn:
            trades = conn.execute(text("""
                SELECT pnl, trade_date
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                ORDER BY trade_date DESC,
                         created_at DESC
                LIMIT 20
            """), {"uid": st.session_state.get("user_id",1)}).fetchall()

        if trades:
            first_pnl    = float(trades[0][0])
            current_type = "Win" if first_pnl > 0 \
                           else "Loss"
            streak = 0

            for t in trades:
                pnl       = float(t[0])
                this_type = "Win" if pnl > 0 else "Loss"
                if this_type == current_type:
                    streak += 1
                else:
                    break

            result["trade_streak"]      = streak
            result["trade_streak_type"] = current_type

            if current_type == "Loss" and streak >= 3:
                result["warnings"].append(
                    f"⛔ {streak} loss streak. "
                    f"STOP TRADING TODAY. "
                    f"Come back tomorrow fresh."
                )
            elif current_type == "Loss" and streak >= 2:
                result["warnings"].append(
                    f"🔴 {streak} consecutive losses. "
                    f"Revenge risk is HIGH. "
                    f"30 min break before next trade."
                )
            elif current_type == "Win" and streak >= 3:
                result["warnings"].append(
                    f"⚠️ {streak} win streak. "
                    f"Overconfidence risk. "
                    f"Do not increase size."
                )

        # Prediction streaks — exclude No Edge days
        with get_engine().connect() as conn:
            preds = conn.execute(text("""
                SELECT was_correct, trade_date
                FROM forward_test_log
                WHERE market='US'
                AND was_correct IS NOT NULL
                AND edge != 'No Edge'
                AND actual_bias IS NOT NULL
                ORDER BY trade_date DESC
                LIMIT 30
            """)).fetchall()

        if preds:
            first_correct = bool(preds[0][0])
            pred_type     = "Correct" \
                            if first_correct \
                            else "Incorrect"
            pred_streak   = 0

            for p in preds:
                if p[0] is None:
                    continue  # Skip No Edge
                this = bool(p[0])
                if (this and pred_type == "Correct") or \
                   (not this and pred_type == "Incorrect"):
                    pred_streak += 1
                else:
                    break

            result["pred_streak"]      = pred_streak
            result["pred_streak_type"] = pred_type

    except:
        pass

    return result


def detect_all_behaviors(trade_id, trade_date,
                          pnl, emotion,
                          followed_plan,
                          checked_system,
                          gate_passed,
                          entry_price, stop_price,
                          exit_price, direction,
                          created_at):
    behaviors = []
    try:
        with get_engine().connect() as conn:
            todays = conn.execute(text("""
                SELECT id, pnl, created_at,
                       emotional_state,
                       checked_system
                FROM trade_journal
                WHERE trade_date=:td
                AND market='US'
                ORDER BY created_at ASC
            """), {"td": str(trade_date)}).fetchall()

        today_pnls    = [float(t[1]) for t in todays]
        losses_before = sum(
            1 for p in today_pnls[:-1] if p < 0)
        total_trades  = len(todays)

        if not checked_system:
            behaviors.append({
                "type":     "FOMO",
                "severity": "High",
                "desc":     "Entered without checking "
                            "system report today.",
                "cost":     min(pnl,0)
            })

        if losses_before >= 1 and pnl < 0:
            behaviors.append({
                "type":     "Revenge Trading",
                "severity": "High"
                            if losses_before >= 2
                            else "Medium",
                "desc":     f"Trade after "
                            f"{losses_before} loss(es)."
                            f" Revenge pattern.",
                "cost":     min(pnl,0)
            })

        if not gate_passed:
            behaviors.append({
                "type":     "Rule Violation",
                "severity": "High",
                "desc":     "Pre-trade gate not met.",
                "cost":     min(pnl,0)
            })

        if not followed_plan:
            behaviors.append({
                "type":     "Rule Violation",
                "severity": "Medium",
                "desc":     "Did not follow plan.",
                "cost":     min(pnl,0)*0.5
            })

        if emotion >= 8:
            behaviors.append({
                "type":     "Tilt",
                "severity": "High",
                "desc":     f"Emotion {emotion}/10. "
                            f"Too high to trade.",
                "cost":     min(pnl,0)
            })
        elif emotion >= 6:
            behaviors.append({
                "type":     "Elevated Emotion",
                "severity": "Medium",
                "desc":     f"Emotion {emotion}/10.",
                "cost":     0
            })

        if total_trades > 3:
            behaviors.append({
                "type":     "Overtrading",
                "severity": "Medium",
                "desc":     f"Trade #{total_trades}."
                            f" Win rate drops after 3.",
                "cost":     min(pnl,0)*0.5
            })

        if len(todays) >= 2:
            current  = todays[-1]
            previous = todays[-2]
            try:
                mins = abs((
                    current[2]-previous[2]
                ).total_seconds())/60
                prev_pnl = float(previous[1])

                if prev_pnl < 0 and mins < 30:
                    behaviors.append({
                        "type":     "Revenge Trading",
                        "severity": "High",
                        "desc":     f"{mins:.0f}min "
                                    f"since last loss. "
                                    f"30min required.",
                        "cost":     min(pnl,0)
                    })
                elif prev_pnl >= 0 and mins < 15:
                    behaviors.append({
                        "type":     "Greed",
                        "severity": "Medium",
                        "desc":     f"{mins:.0f}min "
                                    f"since last win. "
                                    f"15min minimum.",
                        "cost":     0
                    })
            except:
                pass

        if behaviors:
            with get_engine().connect() as conn:
                for b in behaviors:
                    conn.execute(text("""
                        INSERT INTO behavioral_events(
                            market, event_date,
                            trade_id, behavior_type,
                            severity, description,
                            financial_cost)
                        VALUES('US',:td,:tid,
                               :btype,:sev,
                               :desc,:cost)
                    """), {
                        "td":    str(trade_date),
                        "tid":   trade_id,
                        "btype": b["type"],
                        "sev":   b["severity"],
                        "desc":  b["desc"],
                        "cost":  b.get("cost",0)
                    })
                conn.commit()

    except Exception as e:
        st.error(f"Detection error: {e}")

    return behaviors

def check_reentry_timing(trade_date):
    try:
        with get_engine().connect() as conn:
            # Get last LOSING trade time
            last_loss = conn.execute(text("""
                SELECT exit_time,
                       pnl,
                       ticker
                FROM trade_journal
                WHERE market='US'
                AND user_id=:uid
                AND trade_date=:td
                AND pnl < 0
                AND trade_status='closed'
                ORDER BY exit_time DESC
                LIMIT 1
            """), {
                "td":  str(trade_date),
                "uid": st.session_state.get(
                    "user_id", 1)
            }).fetchone()

        if not last_loss:
            return None

        # Calculate minutes since last loss
        now_est = datetime.now(EST)
        loss_time_str = str(last_loss[0])
        try:
            loss_h = int(
                loss_time_str.split(":")[0])
            loss_m = int(
                loss_time_str.split(":")[1])
            loss_mins = loss_h*60 + loss_m
            now_mins  = (now_est.hour*60 +
                         now_est.minute)
            mins_since = now_mins - loss_mins
        except:
            return None

        if 0 < mins_since < 30:
            remaining = 30 - mins_since
            unlock_h  = (loss_h*60 +
                         loss_m + 30) // 60
            unlock_m  = (loss_h*60 +
                         loss_m + 30) % 60
            unlock_time = (f"{unlock_h:02d}:"
                          f"{unlock_m:02d}")
            pnl = float(last_loss[1])
            return {
                "blocked":      True,
                "mandatory":    True,
                "remaining":    remaining,
                "unlock_time":  unlock_time,
                "loss_pnl":     pnl,
                "ticker":       last_loss[2],
                "message":      (
                    f"⏸️ MANDATORY 30-MIN BREAK\n"
                    f"Loss: ${pnl:+.2f} on "
                    f"{last_loss[2]}\n"
                    f"Next trade: {unlock_time} EST\n"
                    f"({remaining:.0f} min remaining)")
            }
    except:
        pass
    return None

