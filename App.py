import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Load 8 Protocol", page_icon="✨", layout="wide")

# ───────────────────────── PALETTE ─────────────────────────
GOLD, BG, CARD = "#D4AF37", "#0B0C10", "#1A1D24"
FOREST = "#1A2318"
NAVY, SILVERBLUE = "#1B263B", "#778DA9"
OBS, TERRA = "#212529", "#A65D37"
COPPER, ROSEWOOD = "#C05A46", "#4A2E2B"
SILVER = "#C0C0C0"

st.markdown(f"""
<style>
.stApp {{ background:{BG}; color:#fff; }}
h1,h2,h3,h4 {{ color:{GOLD} !important; letter-spacing:.5px; }}
p, li, label, span {{ color:#fff; }}
.block-container {{ padding:2.5rem 4rem; max-width:1300px; }}
.card {{ background:{CARD}; border:1px solid {GOLD}; border-radius:14px;
        padding:1.6rem 1.8rem; margin-bottom:1.8rem; }}
.card.wealth {{ background:linear-gradient(160deg,{FOREST},{CARD}); }}
.card.recov  {{ background:linear-gradient(160deg,{NAVY},{CARD}); border-color:{SILVERBLUE}; }}
.card.load   {{ background:linear-gradient(160deg,{OBS},{CARD}); border-color:{TERRA}; }}
.card.alert  {{ background:{ROSEWOOD}; border-color:{COPPER}; }}
.metric-label {{ color:{SILVER}; font-size:.8rem; text-transform:uppercase; letter-spacing:2px; }}
.metric-value {{ font-size:2.4rem; font-weight:600; color:#fff; }}
.badge {{ display:inline-block; padding:.9rem 2rem; border-radius:999px; font-size:1.4rem;
         font-weight:700; letter-spacing:1px; }}
.bar-wrap {{ background:#0f1116; border-radius:8px; height:14px; width:100%; overflow:hidden; }}
.bar {{ height:14px; border-radius:8px; }}
.small {{ color:{SILVER}; font-size:.85rem; }}
.stTabs [data-baseweb="tab"] {{ color:{SILVER}; font-size:1.05rem; padding:.8rem 1.4rem; }}
.stTabs [aria-selected="true"] {{ color:{GOLD} !important; }}
.stButton>button {{ background:{GOLD}; color:#0B0C10; font-weight:700; border:none;
                   border-radius:10px; padding:.7rem 1.6rem; }}
.stButton>button:hover {{ background:#e6c24f; color:#000; }}
[data-testid="stExpander"] {{ background:{CARD}; border:1px solid {GOLD}55; border-radius:12px; }}
</style>
""", unsafe_allow_html=True)

# ───────────────────────── LOGIC ENGINE ─────────────────────────
SURVIVAL_PRESET = dict(work=3, cog=3, emot=2, surv=2, rec=1)

def total_load(w, c, e, s, survival):
    return 10 if survival else w + c + e + s

def adjusted_recovery(rec, micro_count):
    return rec + min(1.0, 0.5 * micro_count)

def net_strain(load, adj):
    return load - adj

def low_recovery_streak(df, today_adj=None):
    """True if adjusted recovery < 2 on the last two consecutive days."""
    vals = list(df.sort_values("date")["adj_rec"])
    if today_adj is not None:
        vals = vals[:-1] + [today_adj] if len(vals) and df.iloc[-1]["date"] == date.today() else vals + [today_adj]
    return len(vals) >= 2 and vals[-1] < 2 and vals[-2] < 2

def ego_mode(load, net, streak):
    if net >= 6 or load >= 8 or streak:
        return "RED"
    if net >= 4:
        return "YELLOW"
    return "GREEN"

MODES = {
    "GREEN":  dict(emoji="🟢", name="Green Mode · Normal Execution", bg=FOREST, fg=GOLD,
                   msg="Full capacity. Build, plan and move your goals forward."),
    "YELLOW": dict(emoji="🟡", name="Yellow Mode · Maintenance Cooldown", bg=NAVY, fg=SILVERBLUE,
                   msg="Essential admin only. Protect your sleep. System Preserved."),
    "RED":    dict(emoji="🔴", name="Red Mode · Overheated Triage", bg=ROSEWOOD, fg=COPPER,
                   msg="Protection Mode Active: discretionary spending frozen, $15 safe "
                       "takeout buffer auto-approved, physical recovery first."),
}

def badge(mode):
    m = MODES[mode]
    return (f"<div class='badge' style='background:{m['bg']};color:{m['fg']};"
            f"border:2px solid {m['fg']}'>{m['emoji']} {m['name']}</div>")

def bar(pct, color):
    pct = max(0, min(pct, 100))
    return f"<div class='bar-wrap'><div class='bar' style='width:{pct}%;background:{color}'></div></div>"

# ───────────────────────── BUDGET CONFIG ─────────────────────────
BASE_CAPS = {"Housing": 1800, "Groceries": 600, "Dining & Takeout": 300, "Transport": 250,
             "Subscriptions": 80, "Shopping": 250, "Wellness": 150, "Fees & Misc": 50}
DISCRETIONARY = {"Dining & Takeout", "Shopping", "Subscriptions"}
GOALS = {
    "🔥 Debt Momentum (Destroy Debt)": {"Dining & Takeout": .6, "Shopping": .4, "Subscriptions": .5, "Wellness": 1.0},
    "🏝️ Vacation / Experience":       {"Dining & Takeout": .8, "Shopping": .6, "Subscriptions": .8, "Transport": .9},
    "🌌 Retirement / Wealth":          {"Dining & Takeout": .7, "Shopping": .5, "Subscriptions": .6},
    "🎓 College Savings":              {"Dining & Takeout": .7, "Shopping": .5, "Subscriptions": .6, "Groceries": .95},
    "🛡️ Emergency Buffer":            {"Dining & Takeout": .7, "Shopping": .4, "Subscriptions": .5},
}
TAGS = ["Standard", "Impulse Buy", "Burnout Tax", "Late/Overdraft Fee"]

def caps_for(goal):
    mult = GOALS[goal]
    return {k: round(v * mult.get(k, 1.0)) for k, v in BASE_CAPS.items()}

# ───────────────────────── MOCK DATA ─────────────────────────
def mock_state():
    t = date.today()
    rows = [  # work, cog, emot, surv, rec, survival, micro
        (1, 1, 1, 0, 3, False, 2), (2, 1, 1, 1, 2, False, 1), (2, 2, 1, 1, 2, False, 0),
        (3, 2, 2, 1, 1, False, 0), (3, 3, 2, 2, 1, True, 0), (2, 2, 1, 1, 2, False, 2),
    ]
    logs = []
    for i, (w, c, e, s, r, sv, mc) in enumerate(rows):
        d = t - timedelta(days=6 - i)
        tl = total_load(w, c, e, s, sv)
        adj = adjusted_recovery(r, mc)
        logs.append(dict(date=d, work=w, cog=c, emot=e, surv=s, rec=r, survival=sv,
                         micro=mc, load=tl, adj_rec=adj, net=net_strain(tl, adj)))
    ex = [(5, "Groceries", 142.5, "Standard"), (5, "Dining & Takeout", 38.0, "Burnout Tax"),
          (4, "Dining & Takeout", 54.0, "Impulse Buy"), (4, "Shopping", 89.0, "Impulse Buy"),
          (3, "Subscriptions", 42.0, "Standard"), (3, "Transport", 61.0, "Standard"),
          (2, "Fees & Misc", 35.0, "Late/Overdraft Fee"), (2, "Housing", 1800.0, "Standard"),
          (1, "Dining & Takeout", 47.0, "Burnout Tax"), (1, "Groceries", 118.0, "Standard"),
          (0, "Shopping", 64.0, "Impulse Buy"), (0, "Wellness", 40.0, "Standard")]
    exp = [dict(date=t - timedelta(days=d), category=c, amount=a, tag=g) for d, c, a, g in ex]
    return pd.DataFrame(logs), pd.DataFrame(exp)

if "logs" not in st.session_state:
    st.session_state.logs, st.session_state.exp = mock_state()
if "goal" not in st.session_state:
    st.session_state.goal = list(GOALS)[0]

logs, exp = st.session_state.logs, st.session_state.exp
goal = st.session_state.goal
caps = caps_for(goal)

# ───────────────────────── HEADER ─────────────────────────
st.markdown("# ✨ Load 8 Protocol & Real Budget")
st.markdown("<p class='small'>Celestial Luxury Bundle · Your Life & Load Operating System</p>",
            unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["🚀 Start Here", "📊 Daily Command Center",
                                  "💳 The Real Budget", "📈 7-Day Calibration"])

# ───────────────────────── TAB 1 ─────────────────────────
with tab1:
    st.markdown("<div class='card'><h3>Welcome, Operator</h3>"
                "<p>This system tracks your internal load (Id, Ego, Superego) next to your money, "
                "so you can see burnout coming before it spends for you.</p>"
                "<ol><li>Pick your primary goal below.</li>"
                "<li>Log your load each day (about 30 seconds).</li>"
                "<li>Follow your Ego Mode. It adjusts your budget caps automatically.</li></ol>"
                "<p class='small'>Exhausted? One tap on Survival Mode and you're done.</p></div>",
                unsafe_allow_html=True)

    st.markdown("### 🎯 Choose Your Primary Goal")
    st.session_state.goal = st.radio("Goal", list(GOALS), index=list(GOALS).index(goal),
                                     label_visibility="collapsed")
    goal = st.session_state.goal
    st.markdown(f"<div class='card wealth'><span class='metric-label'>Active Goal</span><br>"
                f"<span style='color:{GOLD};font-size:1.4rem'>{goal}</span>"
                f"<p class='small'>Budget caps in Tab 3 are now tuned to this goal.</p></div>",
                unsafe_allow_html=True)

    st.markdown("### 🧭 Behavioral Anchor Quick Reference")
    anchors = pd.DataFrame({
        "Score": [0, 1, 2, 3],
        "Work": ["Off / no demands", "Light, on schedule", "Heavy, some pressure", "Overloaded, firefighting"],
        "Cognitive": ["Clear mind", "Minor fog", "Hard to focus / decide", "Can't think straight"],
        "Emotional": ["Steady", "Mild irritation", "Reactive / tearful", "Overwhelmed"],
        "Survival": ["Basics handled", "1 basic skipped", "Skipping meals/sleep", "Running on fumes"],
        "Recovery": ["None", "A little (short rest)", "Solid (sleep + a break)", "Fully restored"],
    })
    st.dataframe(anchors, hide_index=True, use_container_width=True)
    st.markdown("<p class='small'>Score the day as it actually was, not as you wish it had been. "
                "These anchors prevent scoring drift.</p>", unsafe_allow_html=True)

# ───────────────────────── TAB 2 ─────────────────────────
with tab2:
    left, right = st.columns([1.2, 1], gap="large")

    with left:
        st.markdown("<div class='card load'><h3>Today's Load</h3>", unsafe_allow_html=True)
        survival = st.checkbox("⚡ Survival Mode (exhausted day: auto-sets max load)", key="survival")
        P = SURVIVAL_PRESET
        w = st.slider("💼 Work", 0, 3, P["work"] if survival else 1, disabled=survival, key="w")
        c = st.slider("🧠 Cognitive", 0, 3, P["cog"] if survival else 1, disabled=survival, key="c")
        e = st.slider("💗 Emotional", 0, 3, P["emot"] if survival else 1, disabled=survival, key="e")
        s = st.slider("🛏️ Survival", 0, 3, P["surv"] if survival else 0, disabled=survival, key="s")
        r = st.slider("🌙 Recovery", 0, 3, P["rec"] if survival else 2, disabled=survival, key="r")
        if survival:
            w, c, e, s, r = P["work"], P["cog"], P["emot"], P["surv"], P["rec"]
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='card recov'><h3>Micro-Recoveries</h3>"
                    "<p class='small'>+0.5 recovery each (max +1.0 per day)</p>", unsafe_allow_html=True)
        m1 = st.checkbox("📴 20-Min Off-Switch")
        m2 = st.checkbox("💧 Hydration / Meal Prep")
        m3 = st.checkbox("🧘 Physical Grounding")
        st.markdown("</div>", unsafe_allow_html=True)
        micro = int(m1) + int(m2) + int(m3)

    load = total_load(w, c, e, s, survival)
    adj = adjusted_recovery(r, micro)
    net = net_strain(load, adj)
    prior = logs[logs["date"] != date.today()]
    streak = low_recovery_streak(prior, today_adj=adj)
    mode = ego_mode(load, net, streak)

    with right:
        st.markdown(f"<div style='margin-bottom:1.8rem'>{badge(mode)}</div>", unsafe_allow_html=True)
        cA, cB = st.columns(2)
        cA.markdown(f"<div class='card load'><div class='metric-label'>Total Load</div>"
                    f"<div class='metric-value'>{load}</div></div>", unsafe_allow_html=True)
        cB.markdown(f"<div class='card recov'><div class='metric-label'>Adj. Recovery</div>"
                    f"<div class='metric-value'>{adj:.1f}</div></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='card load'><div class='metric-label'>Net Strain</div>"
                    f"<div class='metric-value'>{net:.1f}</div>{bar(net / 10 * 100, TERRA)}</div>",
                    unsafe_allow_html=True)
        cls = "alert" if mode == "RED" else ("recov" if mode == "YELLOW" else "wealth")
        st.markdown(f"<div class='card {cls}'><p>{MODES[mode]['msg']}</p></div>", unsafe_allow_html=True)
        if streak:
            st.markdown(f"<div class='card alert'>🧊 <b>Thaw/Cool Protocol:</b> recovery stayed low "
                        f"2 days in a row. System override engaged.</div>", unsafe_allow_html=True)

        if st.button("💾 Save Today's Check-In", use_container_width=True):
            row = dict(date=date.today(), work=w, cog=c, emot=e, surv=s, rec=r, survival=survival,
                       micro=micro, load=load, adj_rec=adj, net=net)
            L = st.session_state.logs
            L = L[L["date"] != date.today()]
            st.session_state.logs = pd.concat([L, pd.DataFrame([row])], ignore_index=True)
            st.success("Check-in saved. System Preserved ✨")
            st.rerun()

    st.session_state["current_mode"] = mode

    st.markdown("### 💸 Expense Log")
    with st.container():
        st.markdown("<div class='card wealth'>", unsafe_allow_html=True)
        x1, x2, x3 = st.columns(3)
        amt = x1.number_input("Amount ($)", min_value=0.0, step=5.0, format="%.2f")
        cat = x2.selectbox("Category", list(BASE_CAPS))
        tag = x3.selectbox("Tag", TAGS)
        frozen = mode == "RED" and cat in DISCRETIONARY
        if frozen:
            st.markdown(f"<div class='card alert'>🛡️ Protection Mode: discretionary spending is paused "
                        f"in Red Mode. A <b>$15 safe takeout/convenience buffer</b> is pre-approved.</div>",
                        unsafe_allow_html=True)
        if st.button("➕ Add Expense"):
            if amt > 0:
                new = dict(date=date.today(), category=cat, amount=amt, tag=tag)
                st.session_state.exp = pd.concat([st.session_state.exp, pd.DataFrame([new])],
                                                 ignore_index=True)
                st.success("Logged. Awareness is the win.")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Recent transactions"):
        st.dataframe(st.session_state.exp.sort_values("date", ascending=False).head(15),
                     hide_index=True, use_container_width=True)

# ───────────────────────── TAB 3 ─────────────────────────
with tab3:
    mode = st.session_state.get("current_mode", "GREEN")
    spend = exp.groupby("category")["amount"].sum().to_dict()
    st.markdown(f"<div class='card wealth'><span class='metric-label'>Adaptive caps for</span><br>"
                f"<span style='color:{GOLD};font-size:1.3rem'>{goal}</span></div>", unsafe_allow_html=True)
    if mode == "RED":
        st.markdown(f"<div class='card alert'>🛡️ <b>Protection Mode Active.</b> Discretionary categories "
                    f"are frozen. Safe takeout buffer: <b>$15</b>.</div>", unsafe_allow_html=True)

    cols = st.columns(2, gap="large")
    for i, (catg, cap) in enumerate(caps.items()):
        spent = spend.get(catg, 0.0)
        pct = spent / cap * 100 if cap else 0
        color = COPPER if pct > 85 else GOLD
        tag_ = " · ⏸ frozen" if (mode == "RED" and catg in DISCRETIONARY) else ""
        cols[i % 2].markdown(
            f"<div class='card wealth'><b>{catg}</b>{tag_}<br>"
            f"<span class='small'>${spent:,.0f} of ${cap:,.0f} · {pct:.0f}%</span>"
            f"{bar(pct, color)}</div>", unsafe_allow_html=True)

    imp = (exp["tag"] == "Impulse Buy").sum()
    burn = exp.loc[exp["tag"] == "Burnout Tax", "amount"].sum()
    fees = exp.loc[exp["tag"] == "Late/Overdraft Fee", "amount"].sum()
    a, b, c_ = st.columns(3)
    a.markdown(f"<div class='card load'><div class='metric-label'>Impulse Buys</div>"
               f"<div class='metric-value'>{imp}</div></div>", unsafe_allow_html=True)
    b.markdown(f"<div class='card load'><div class='metric-label'>Burnout Tax</div>"
               f"<div class='metric-value'>${burn:,.0f}</div></div>", unsafe_allow_html=True)
    c_.markdown(f"<div class='card {'alert' if fees else 'wealth'}'><div class='metric-label'>Fees</div>"
                f"<div class='metric-value'>${fees:,.0f}</div></div>", unsafe_allow_html=True)
    if imp >= 3:
        st.markdown("<div class='card alert'>⚠️ 3+ impulse buys detected. A 24-hour pause rule "
                    "is a good protection.</div>", unsafe_allow_html=True)
    if fees > 0:
        st.markdown("<div class='card alert'>⚠️ Fee detected. Consider an autopay or alert "
                    "to protect your future self.</div>", unsafe_allow_html=True)

# ───────────────────────── TAB 4 ─────────────────────────
with tab4:
    last7 = logs.sort_values("date").tail(7)
    k1, k2, k3 = st.columns(3)
    k1.markdown(f"<div class='card load'><div class='metric-label'>Avg Total Load</div>"
                f"<div class='metric-value'>{last7['load'].mean():.1f}</div></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='card recov'><div class='metric-label'>Avg Adj. Recovery</div>"
                f"<div class='metric-value'>{last7['adj_rec'].mean():.1f}</div></div>", unsafe_allow_html=True)
    k3.markdown(f"<div class='card load'><div class='metric-label'>Avg Net Strain</div>"
                f"<div class='metric-value'>{last7['net'].mean():.1f}</div></div>", unsafe_allow_html=True)

    with st.expander("📉 Trend chart", expanded=True):
        chart = last7.set_index("date")[["load", "adj_rec", "net"]]
        chart.columns = ["Total Load", "Adjusted Recovery", "Net Strain"]
        st.line_chart(chart, color=[TERRA, SILVERBLUE, GOLD])

    st.markdown("### 🔥 Category Burn Rate")
    spend = exp.groupby("category")["amount"].sum().to_dict()
    hot = [(k, spend.get(k, 0) / v * 100) for k, v in caps.items() if spend.get(k, 0) / v > 0.85]
    if hot:
        for k, p in hot:
            st.markdown(f"<div class='card alert'>🛡️ <b>{k}</b> is at {p:.0f}% of its cap. "
                        f"Protect it for the rest of the cycle.</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='card wealth'>✨ All categories under 85%. System Preserved.</div>",
                    unsafe_allow_html=True)

    st.markdown("### 🧊 2-Day Low-Recovery Thaw/Cool Log")
    srt = logs.sort_values("date").reset_index(drop=True)
    events = []
    for i in range(1, len(srt)):
        if srt.loc[i, "adj_rec"] < 2 and srt.loc[i - 1, "adj_rec"] < 2:
            events.append(srt.loc[i, "date"])
    if events:
        for d in events:
            st.markdown(f"<div class='card alert'><b>{d}</b> · Recovery below 2 for 2 consecutive days. "
                        f"Override: Red Mode, discretionary freeze, $15 safe buffer, physical "
                        f"recovery enforced. 🛡️ Protection Mode Active.</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='card recov'>No thaw events. Recovery is holding. 🌙</div>",
                    unsafe_allow_html=True)

    with st.expander("Raw 7-day log"):
        st.dataframe(last7, hide_index=True, use_container_width=True)
