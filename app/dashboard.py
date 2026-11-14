"""
Interactive dashboard for the activation analysis.
Run from the project root:   streamlit run app/dashboard.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from build_marts import DB, build, connect  # noqa: E402

st.set_page_config(page_title="AhaFinder - Sona activation analytics", layout="wide")


@st.cache_data
def load():
    if not DB.exists():
        build()
    con = connect(read_only=True)
    m = con.execute("SELECT * FROM mart_user_activation").df()
    con.close()
    return m


m = load()
st.title("AhaFinder: activation & aha-moment analytics")
st.caption("Simulated data for a fictional digital-gold savings app · 100K installs · Jul-Sep 2026 cohorts")

with st.sidebar:
    st.header("Filters")
    ch = st.multiselect("Acquisition channel", sorted(m.channel.unique()), default=sorted(m.channel.unique()))
    tier = st.multiselect("City tier", [1, 2, 3], default=[1, 2, 3])
    dev = st.multiselect("Device segment", sorted(m.device_segment.unique()), default=sorted(m.device_segment.unique()))
d = m[m.channel.isin(ch) & m.city_tier.isin(tier) & m.device_segment.isin(dev)]
if d.empty:
    st.warning("No users match these filters.")
    st.stop()

buyers = d[d.did_first_buy == 1]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Installs", f"{len(d):,}")
c2.metric("Install to first buy", f"{d.did_first_buy.mean():.1%}")
c3.metric("KYC completion (of starters)", f"{d.loc[d.did_kyc_start == 1, 'did_kyc_done'].mean():.1%}")
c4.metric("D30 retention (buyers)", f"{buyers.d30_retained.mean():.1%}" if len(buyers) else "n/a")

tab1, tab2, tab3 = st.tabs(["Funnel", "KYC deep-dive", "Aha-moment explorer"])

with tab1:
    steps = ["did_signup", "did_kyc_start", "did_kyc_done", "did_upi", "did_first_buy"]
    labels = ["Install", "Signup", "KYC started", "KYC done", "UPI linked", "First buy"]
    vals = [len(d)] + [int(d[s].sum()) for s in steps]
    fig = go.Figure(go.Funnel(y=labels, x=vals, textinfo="value+percent previous"))
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    by = d.groupby("channel").agg(installs=("user_id", "size"), first_buy_rate=("did_first_buy", "mean")).reset_index()
    st.plotly_chart(px.bar(by, x="channel", y="first_buy_rate", text_auto=".1%",
                           title="Install to first buy, by channel"), width="stretch")

with tab2:
    s = d[d.did_kyc_start == 1]
    piv = s.pivot_table(index="device_segment", columns="city_tier", values="did_kyc_done", aggfunc="mean")
    st.plotly_chart(px.imshow(piv, text_auto=".0%", color_continuous_scale="RdYlGn", zmin=0.65, zmax=1,
                              title="KYC completion rate"), width="stretch")
    f = s[s.kyc_fail_count > 0].groupby(["device_segment", "first_kyc_fail_reason"]).size().reset_index(name="users")
    st.plotly_chart(px.bar(f, x="users", y="device_segment", color="first_kyc_fail_reason", orientation="h",
                           title="First KYC failure reason"), width="stretch")

with tab3:
    if buyers.empty:
        st.info("No first-time buyers in this selection.")
    else:
        st.write("Pick a week-1 behaviour and see how D30 retention differs for buyers who did it.")
        opt = st.selectbox("Behaviour", ["Manual buys in week 1 (threshold)", "Enabled AutoSave", "Created goal",
                                         "Set price alert", "Sent referral"])
        if opt.startswith("Manual"):
            k = st.slider("Threshold: at least k manual buys", 1, 8, 3)
            did = buyers.w1_manual_buys >= k
        else:
            col = {"Enabled AutoSave": "w1_autosave", "Created goal": "w1_goal",
                   "Set price alert": "w1_price_alert", "Sent referral": "w1_referral"}[opt]
            did = buyers[col] == 1
        a, b, c = st.columns(3)
        a.metric("Buyers who did it", f"{did.mean():.1%}")
        b.metric("D30 retention if did", f"{buyers.loc[did, 'd30_retained'].mean():.1%}")
        c.metric("D30 retention if not", f"{buyers.loc[~did, 'd30_retained'].mean():.1%}" if (~did).any() else "n/a")
        st.caption("These are correlations. See the README for the confounding-adjusted estimates and "
                   "why a randomised test is still needed before shipping.")
