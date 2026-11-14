"""
End-to-end analysis: funnel leaks, KYC deep-dive, opportunity sizing, and aha-moment discovery.
Writes charts to outputs/charts/ and all headline numbers to outputs/results.json.

Run after build_marts.py:   python src/analyze.py
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).parent))
from build_marts import connect, load_named_queries, ROOT  # noqa: E402

OUT = ROOT / "outputs"
CH = OUT / "charts"
CH.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 10, "axes.titleweight": "bold"})
INK, ACCENT, MUTED, BAD = "#1f2937", "#2563eb", "#9ca3af", "#dc2626"

CANDIDATES = {
    "w1_autosave": "Enabled AutoSave",
    "w1_goal": "Created a savings goal",
    "w1_price_alert": "Set a gold price alert",
    "w1_referral": "Sent a referral",
    "buys3": "3+ manual buys",
    "active3": "Opened app on 3+ days",
}


def pct(x, d=1):
    return round(100 * float(x), d)


def main():
    con = connect(read_only=True)
    q = load_named_queries()
    R = {}

    # ------------------------------------------------------------------ 1. funnel
    f = con.execute(q["funnel_overall"]).df()
    f["users"] = f["users"].astype(int)
    f["step_conv"] = f["users"] / f["users"].shift(1)
    f["overall_conv"] = f["users"] / f["users"].iloc[0]
    f["lost"] = (f["users"].shift(1) - f["users"]).fillna(0).astype(int)
    R["funnel"] = f[["step", "users", "step_conv", "overall_conv", "lost"]].round(4).to_dict("records")
    R["install_to_first_buy_pct"] = pct(f["overall_conv"].iloc[-1])

    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.barh(f["step"][::-1], f["users"][::-1], color=ACCENT)
    for y, (u, c) in enumerate(zip(f["users"][::-1], f["step_conv"][::-1])):
        lab = f"{u:,}" + ("" if np.isnan(c) else f"  ({c:.0%} of prev)")
        ax.text(u + 800, y, lab, va="center", fontsize=9, color=INK)
    ax.set_title("Onboarding funnel: 100K installs, Jul-Sep 2026 cohorts")
    ax.set_xlabel("users"); ax.set_xlim(0, 125000)
    fig.tight_layout(); fig.savefig(CH / "01_funnel.png"); plt.close(fig)

    # ------------------------------------------------------------------ 2. KYC deep-dive
    k = con.execute(q["kyc_by_device_tier"]).df()
    piv = k.pivot(index="device_segment", columns="city_tier", values="kyc_completion_rate")
    R["kyc_completion_by_segment"] = piv.round(4).to_dict()
    fig, ax = plt.subplots(figsize=(6, 3))
    im = ax.imshow(piv.values, cmap="RdYlGn", vmin=0.65, vmax=1.0)
    ax.set_xticks(range(3), [f"Tier {c}" for c in piv.columns]); ax.set_yticks(range(len(piv)), piv.index)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            ax.text(j, i, f"{piv.values[i, j]:.0%}", ha="center", va="center", fontsize=10)
    ax.set_title("KYC completion rate (of users who start KYC)")
    fig.colorbar(im, ax=ax, fraction=0.03); fig.tight_layout(); fig.savefig(CH / "02_kyc_heatmap.png"); plt.close(fig)

    r = con.execute(q["kyc_fail_reasons"]).df()
    r["share"] = r["users"] / r.groupby("device_segment")["users"].transform("sum")
    R["kyc_fail_reason_share"] = {seg: g.set_index("reason")["share"].round(4).to_dict()
                                  for seg, g in r.groupby("device_segment")}
    fig, ax = plt.subplots(figsize=(7, 3.2))
    rp = r.pivot(index="device_segment", columns="reason", values="share").fillna(0)
    left = np.zeros(len(rp))
    colors = {"selfie_liveness_fail": BAD, "pan_name_mismatch": ACCENT, "aadhaar_otp_timeout": MUTED}
    for col in rp.columns:
        ax.barh(rp.index, rp[col], left=left, color=colors.get(col, INK), label=col.replace("_", " "))
        for y, (l, v) in enumerate(zip(left, rp[col])):
            if v > 0.08:
                ax.text(l + v / 2, y, f"{v:.0%}", ha="center", va="center", color="white", fontsize=9)
        left += rp[col].values
    ax.set_xlim(0, 1); ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.45), ncol=3, frameon=False, fontsize=8)
    ax.set_title("First KYC failure reason, by device segment")
    fig.tight_layout(); fig.savefig(CH / "03_kyc_fail_reasons.png"); plt.close(fig)

    # ------------------------------------------------------------------ 3. opportunity sizing
    m = con.execute("SELECT * FROM mart_user_activation").df()
    starters = m[m.did_kyc_start == 1]
    low = starters[starters.device_segment == "android_low_end"]
    rest = starters[starters.device_segment != "android_low_end"]
    low_rate, rest_rate = low.did_kyc_done.mean(), rest.did_kyc_done.mean()
    kyc_done = m[m.did_kyc_done == 1]
    p_upi = kyc_done.did_upi.mean()
    p_buy = m[m.did_upi == 1].did_first_buy.mean()
    buyers = m[m.did_first_buy == 1].copy()
    p_d30 = buyers.d30_retained.mean()
    # conservative scenario: close HALF the gap (e.g. fallback to assisted/offline liveness check)
    for name, share in [("close_half_gap", 0.5), ("close_full_gap", 1.0)]:
        extra_kyc = len(low) * (rest_rate - low_rate) * share
        extra_buyers = extra_kyc * p_upi * p_buy
        R[f"opportunity_{name}"] = {
            "extra_kyc_completions": int(round(extra_kyc)),
            "extra_first_buyers": int(round(extra_buyers)),
            "extra_d30_retained": int(round(extra_buyers * p_d30)),
            "lift_in_first_buyers_pct": pct(extra_buyers / len(buyers)),
        }
    R["kyc_low_end_rate"], R["kyc_rest_rate"] = pct(low_rate), pct(rest_rate)
    R["low_end_share_of_kyc_starters"] = pct(len(low) / len(starters))
    R["low_end_share_of_kyc_failures"] = pct(
        (m[(m.kyc_fail_count > 0)].device_segment == "android_low_end").mean())
    sl = r[(r.device_segment == "android_low_end") & (r.reason == "selfie_liveness_fail")]["share"].iloc[0]
    R["low_end_selfie_share_of_fails"] = pct(sl)

    # ------------------------------------------------------------------ 4. aha-moment discovery (first-time buyers)
    buyers["buys3"] = (buyers.w1_manual_buys >= 3).astype(int)
    buyers["active3"] = (buyers.w1_active_days >= 3).astype(int)
    base = buyers.d30_retained.mean()
    R["n_first_buyers"] = int(len(buyers))
    R["d30_retention_buyers_pct"] = pct(base)

    rows = []
    for col, label in CANDIDATES.items():
        did = buyers[buyers[col] == 1]
        nd = buyers[buyers[col] == 0]
        ret_did, ret_nd = did.d30_retained.mean(), nd.d30_retained.mean()
        rows.append({"action": label, "col": col,
                     "adoption": did.shape[0] / len(buyers),
                     "ret_if_did": ret_did, "ret_if_not": ret_nd,
                     "naive_lift_pp": 100 * (ret_did - ret_nd),
                     "precision": ret_did,                                     # P(retained | did)
                     "recall": did.d30_retained.sum() / buyers.d30_retained.sum()})  # P(did | retained)
    cand = pd.DataFrame(rows)

    # adjusted effect: logistic regression with all behaviours + acquisition/segment controls
    formula = ("d30_retained ~ w1_autosave + w1_goal + w1_price_alert + w1_referral + buys3 + active3"
               " + C(channel) + C(city_tier) + C(device_segment) + C(language)")
    mod = smf.logit(formula, data=buyers).fit(disp=0)
    # convert each coefficient to an average marginal effect (pp)
    ame = mod.get_margeff(at="overall").summary_frame()
    for col in CANDIDATES:
        cand.loc[cand.col == col, "adjusted_lift_pp"] = 100 * ame.loc[col, "dy/dx"]
        cand.loc[cand.col == col, "adj_ci_low"] = 100 * ame.loc[col, "Conf. Int. Low"]
        cand.loc[cand.col == col, "adj_ci_high"] = 100 * ame.loc[col, "Cont. Int. Hi."]
        cand.loc[cand.col == col, "odds_ratio"] = float(np.exp(mod.params[col]))
    R["aha_candidates"] = cand.drop(columns="col").round(4).to_dict("records")

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    y = np.arange(len(cand))
    ax.barh(y + 0.2, cand.naive_lift_pp, 0.4, color=MUTED, label="naive lift (did vs didn't)")
    ax.barh(y - 0.2, cand.adjusted_lift_pp, 0.4, color=ACCENT, label="adjusted lift (logit AME, controls)")
    ax.errorbar(cand.adjusted_lift_pp, y - 0.2,
                xerr=[cand.adjusted_lift_pp - cand.adj_ci_low, cand.adj_ci_high - cand.adjusted_lift_pp],
                fmt="none", ecolor=INK, capsize=2, lw=0.8)
    ax.set_yticks(y, cand.action); ax.axvline(0, color=INK, lw=0.6)
    ax.set_xlabel("D30 retention lift (percentage points)")
    ax.set_title("Which week-1 actions predict D30 retention?")
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=2)
    fig.tight_layout(); fig.savefig(CH / "04_aha_candidates.png"); plt.close(fig)

    # threshold sweep for number of manual buys in week 1
    sweep = []
    for kk in range(1, 9):
        did = buyers.w1_manual_buys >= kk
        sweep.append({"k": kk, "coverage": did.mean(),
                      "ret_if_did": buyers.loc[did, "d30_retained"].mean(),
                      "ret_if_not": buyers.loc[~did, "d30_retained"].mean() if (~did).any() else np.nan,
                      "recall": buyers.loc[did, "d30_retained"].sum() / buyers.d30_retained.sum()})
    sw = pd.DataFrame(sweep)
    sw["precision"] = sw["ret_if_did"]
    sw["f1"] = 2 * sw.precision * sw.recall / (sw.precision + sw.recall)
    sw["marginal_gain_pp"] = 100 * sw.ret_if_did.diff()
    R["buy_threshold_sweep"] = sw.round(4).to_dict("records")
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.plot(sw.k, sw.ret_if_did * 100, "-o", color=ACCENT, label="D30 retention if reached k buys")
    ax.plot(sw.k, sw.coverage * 100, "-s", color=MUTED, label="% of buyers reaching k buys")
    ax.axvline(3, color=BAD, ls="--", lw=1); ax.text(3.1, 8, "threshold = 3", color=BAD, fontsize=8)
    ax.set_xlabel("manual gold buys in first 7 days (k)"); ax.set_ylabel("%")
    ax.set_title("Threshold sweep: retention jumps at 3 buys, then flattens")
    ax.legend(frameon=False, fontsize=8); fig.tight_layout(); fig.savefig(CH / "05_threshold_sweep.png"); plt.close(fig)

    # final aha definition
    buyers["aha"] = ((buyers.w1_autosave == 1) | (buyers.buys3 == 1)).astype(int)
    a1, a0 = buyers[buyers.aha == 1], buyers[buyers.aha == 0]
    R["aha_definition"] = "AutoSave enabled OR 3+ manual buys within 7 days of install"
    R["aha_reached_pct"] = pct(buyers.aha.mean())
    R["aha_ret_pct"], R["non_aha_ret_pct"] = pct(a1.d30_retained.mean()), pct(a0.d30_retained.mean())
    R["aha_ret_multiple"] = round(a1.d30_retained.mean() / a0.d30_retained.mean(), 2)
    R["aha_recall_pct"] = pct(a1.d30_retained.sum() / buyers.d30_retained.sum())

    # retention curves aha vs not
    ev = con.execute("""SELECT DISTINCT user_id, day_n FROM stg_events
                        WHERE event_name='app_open' AND day_n BETWEEN 1 AND 34""").df()
    ev = ev.merge(buyers[["user_id", "aha"]], on="user_id")
    curve = ev.groupby(["aha", "day_n"]).user_id.nunique().unstack(0)
    curve = curve / buyers.groupby("aha").size()
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.plot(curve.index, curve[1] * 100, color=ACCENT, lw=2, label=f"reached aha ({R['aha_reached_pct']}% of buyers)")
    ax.plot(curve.index, curve[0] * 100, color=MUTED, lw=2, label="did not reach aha")
    ax.axvspan(28, 34, color="#fde68a", alpha=0.4); ax.text(28.3, 2, "D30 window", fontsize=8)
    ax.set_xlabel("days since install"); ax.set_ylabel("% of first-time buyers opening the app")
    ax.set_title("Daily active % by aha status"); ax.legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(CH / "06_retention_curves.png"); plt.close(fig)

    # ------------------------------------------------------------------ 5. out-of-time validation
    buyers["month"] = pd.to_datetime(buyers.install_ts).dt.month
    train, test = buyers[buyers.month <= 8], buyers[buyers.month == 9]
    mt = smf.logit(formula, data=train).fit(disp=0)
    auc = roc_auc_score(test.d30_retained, mt.predict(test))
    t1 = test[test.aha == 1].d30_retained.mean(); t0 = test[test.aha == 0].d30_retained.mean()
    R["oot_validation"] = {"train": "Jul-Aug cohorts", "test": "Sep cohort", "n_test": int(len(test)),
                           "auc": round(float(auc), 3),
                           "aha_ret_pct_test": pct(t1), "non_aha_ret_pct_test": pct(t0)}

    # ------------------------------------------------------------------ 6. channel + time-to-value
    R["by_channel"] = con.execute(q["activation_by_channel"]).df().round(4).to_dict("records")
    R["time_to_convert"] = {k: round(float(v), 1) for k, v in con.execute(q["time_to_convert"]).df().iloc[0].items()}
    R["n_events"] = int(con.execute("SELECT count(*) FROM stg_events").fetchone()[0])
    R["n_users"] = int(len(m))

    # ------------------------------------------------------------------ 7. metric tree inputs
    R["metric_tree"] = {
        "north_star": "Weekly Active Savers (>=1 successful manual buy or AutoSave debit in the week)",
        "install_to_first_buy_pct": R["install_to_first_buy_pct"],
        "aha_reached_pct_of_buyers": R["aha_reached_pct"],
        "d30_retention_buyers_pct": R["d30_retention_buyers_pct"],
        "autosave_adoption_pct_of_buyers": pct(buyers.w1_autosave.mean()),
        "autosave_debit_failure_rate_pct": pct(m.autosave_failed_debits.sum()
                                               / (m.autosave_failed_debits.sum() + m.autosave_success_debits.sum())),
    }

    # ------------------------------------------------------------------ 8. sizing the follow-up experiment
    # Proposed test: AutoSave set-up screen right after first purchase. Primary metric: D30 retention.
    from scipy.stats import norm
    def n_per_arm(p0, mde_pp, alpha=0.05, power=0.8):
        p1 = p0 + mde_pp / 100
        z_a, z_b = norm.ppf(1 - alpha / 2), norm.ppf(power)
        pbar = (p0 + p1) / 2
        return int(np.ceil(((z_a * np.sqrt(2 * pbar * (1 - pbar)) + z_b * np.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2)
                           / (p1 - p0) ** 2))
    weekly_buyers = len(buyers) / 13
    R["experiment_sizing"] = {
        "hypothesis": "Prompting AutoSave set-up right after the first purchase raises D30 retention",
        "baseline_d30_pct": R["d30_retention_buyers_pct"],
        "mde_pp": 2.0,
        "n_per_arm": n_per_arm(base, 2.0),
        "weeks_needed_at_current_volume": round(2 * n_per_arm(base, 2.0) / weekly_buyers, 1),
    }

    (OUT / "results.json").write_text(json.dumps(R, indent=2, default=float))
    cand.to_csv(OUT / "aha_candidates.csv", index=False)
    sw.to_csv(OUT / "buy_threshold_sweep.csv", index=False)
    print(json.dumps({k: R[k] for k in ["install_to_first_buy_pct", "kyc_low_end_rate", "kyc_rest_rate",
                                         "low_end_share_of_kyc_starters", "low_end_share_of_kyc_failures",
                                         "low_end_selfie_share_of_fails", "opportunity_close_half_gap",
                                         "opportunity_close_full_gap", "n_first_buyers", "d30_retention_buyers_pct",
                                         "aha_reached_pct", "aha_ret_pct", "non_aha_ret_pct", "aha_ret_multiple",
                                         "aha_recall_pct", "oot_validation", "experiment_sizing", "n_events", "metric_tree"]},
                     indent=1, default=float))
    print(cand.round(3).to_string())
    print(sw.round(3).to_string())


if __name__ == "__main__":
    main()
