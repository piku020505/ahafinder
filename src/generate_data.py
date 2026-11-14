"""
Synthetic event-log generator for "Sona", a fictional digital-gold micro-savings app.

The data is SIMULATED. It is built so that realistic product questions can be asked of it
(funnel leaks, KYC failures, activation behaviours, D30 retention), and the generator is
included so anyone can reproduce every number in the README.

Behavioural structure that is planted (and later re-discovered by the analysis):
  * a latent "intent" score per user, shifted by acquisition channel (a confounder)
  * KYC selfie/liveness failures concentrated on low-end Android phones, worse in tier-3 cities
  * D30 retention driven by: setting up AutoSave in week 1, making 3+ manual buys in week 1,
    creating a savings goal; small or no effect for price alerts (a "vanity" feature)

Usage:  python src/generate_data.py --users 60000 --seed 42
Output: data/users.parquet, data/events.parquet
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

SIGNUP_START = pd.Timestamp("2026-07-01")
SIGNUP_DAYS = 92                     # Jul 1 - Sep 30, 2026
HORIZON_DAYS = 35                    # observe each user for 35 days after install


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def generate(n_users: int, seed: int):
    rng = np.random.default_rng(seed)

    # ---------- user attributes ----------
    channel = rng.choice(["organic", "paid_social", "referral", "influencer"], n_users,
                         p=[0.35, 0.30, 0.15, 0.20])
    tier = rng.choice([1, 2, 3], n_users, p=[0.35, 0.35, 0.30])
    p_android = np.where(tier == 3, 0.92, np.where(tier == 2, 0.84, 0.70))
    device = np.where(rng.random(n_users) < p_android, "android", "ios")
    p_low_end = np.where(tier == 3, 0.45, np.where(tier == 2, 0.25, 0.10))
    low_end = (device == "android") & (rng.random(n_users) < p_low_end)
    language = np.where(tier == 1, rng.choice(["en", "hi"], n_users, p=[0.7, 0.3]),
                        rng.choice(["en", "hi", "regional"], n_users, p=[0.3, 0.45, 0.25]))

    ch_shift = pd.Series(channel).map({"organic": 0.2, "paid_social": -0.35,
                                       "referral": 0.55, "influencer": -0.1}).to_numpy()
    intent = rng.normal(0, 1, n_users) + ch_shift

    install_ts = (SIGNUP_START
                  + pd.to_timedelta(rng.integers(0, SIGNUP_DAYS, n_users), unit="D")
                  + pd.to_timedelta(rng.integers(0, 86400, n_users), unit="s"))

    users = pd.DataFrame({
        "user_id": np.arange(1, n_users + 1),
        "install_ts": install_ts,
        "channel": channel, "city_tier": tier, "device": device,
        "low_end_device": low_end, "language": language,
    })

    events = []                       # list of (user_id, ts, name, props_dict)

    def add(uid, ts, name, **props):
        events.append((uid, ts, name, json.dumps(props) if props else "{}"))

    # per-user simulation
    for i in range(n_users):
        uid = i + 1
        t0 = install_ts[i]
        z = intent[i]
        add(uid, t0, "app_install", channel=channel[i])

        # signup
        if rng.random() > sigmoid(1.2 + 0.6 * z):
            continue
        t = t0 + pd.Timedelta(minutes=float(rng.exponential(6)))
        add(uid, t, "signup_completed")

        # kyc start
        if rng.random() > sigmoid(0.9 + 0.5 * z):
            continue
        t += pd.Timedelta(minutes=float(rng.exponential(30)))
        add(uid, t, "kyc_started")

        # kyc attempts (up to 3)
        p_succ = sigmoid(1.9 + 0.4 * z - 1.5 * low_end[i] - 0.35 * (tier[i] == 3)
                         + 0.3 * (device[i] == "ios"))
        kyc_ok = False
        for attempt in range(1, 4):
            t += pd.Timedelta(minutes=float(rng.exponential(4)))
            if rng.random() < p_succ:
                add(uid, t, "kyc_completed", attempt=attempt)
                kyc_ok = True
                break
            if low_end[i]:
                reason = rng.choice(["selfie_liveness_fail", "pan_name_mismatch", "aadhaar_otp_timeout"],
                                    p=[0.72, 0.14, 0.14])
            else:
                reason = rng.choice(["selfie_liveness_fail", "pan_name_mismatch", "aadhaar_otp_timeout"],
                                    p=[0.30, 0.40, 0.30])
            add(uid, t, "kyc_failed", attempt=attempt, reason=str(reason))
            if rng.random() > 0.55:          # gives up
                break
            t += pd.Timedelta(hours=float(rng.exponential(10)))
        if not kyc_ok:
            # a few low-intent opens before churning
            for d in np.where(rng.random(7) < 0.12, np.arange(7), -1):
                if d > 0:
                    add(uid, t0 + pd.Timedelta(days=int(d), hours=float(rng.uniform(8, 22))), "app_open")
            continue

        # UPI link
        if rng.random() > sigmoid(1.6 + 0.4 * z):
            continue
        t += pd.Timedelta(minutes=float(rng.exponential(20)))
        add(uid, t, "upi_linked")

        # first purchase
        if rng.random() > sigmoid(1.0 + 0.5 * z):
            continue
        t_upi = t
        t += pd.Timedelta(hours=float(rng.exponential(8)))
        cap = t0 + pd.Timedelta(days=6, hours=12)          # first buy happens inside week 1
        if t > cap:
            t = max(t_upi + pd.Timedelta(minutes=10), cap - pd.Timedelta(hours=float(rng.uniform(0, 12))))
        add(uid, t, "gold_purchased", amount=round(float(rng.lognormal(4.6, 0.7)), 0), source="manual")

        # ---------- week-1 behaviours ----------
        autosave = rng.random() < sigmoid(-0.9 + 0.7 * z)
        goal = rng.random() < sigmoid(-0.6 + 0.5 * z)
        alert = rng.random() < sigmoid(-0.4 + 0.5 * z)      # popular, but low impact
        referral = rng.random() < sigmoid(-1.9 + 0.4 * z)
        extra_buys = rng.poisson(np.exp(0.15 + 0.45 * z))
        n_buys_w1 = 1 + min(extra_buys, 12)

        t_first = t
        w1_end = t0 + pd.Timedelta(hours=7 * 24 - 1)

        def w1_time():
            # week-1 actions happen after the first purchase and before the end of day 6
            span = max((w1_end - t_first).total_seconds(), 60.0)
            return t_first + pd.Timedelta(seconds=float(rng.uniform(30, span)))

        if autosave:
            t_as = w1_time()
            add(uid, t_as, "autosave_enabled", daily_amount=int(rng.choice([10, 20, 30, 50])))
        if goal:
            add(uid, w1_time(), "goal_created", goal_type=str(rng.choice(["wedding", "emergency", "festival", "gadget"])))
        if alert:
            add(uid, w1_time(), "price_alert_set")
        if referral:
            add(uid, w1_time(), "referral_sent")
        for _ in range(n_buys_w1 - 1):
            add(uid, w1_time(), "gold_purchased", amount=round(float(rng.lognormal(4.3, 0.8)), 0), source="manual")

        # ---------- D30 retention (planted causal structure + confounding via z) ----------
        logit = (-1.75 + 0.55 * z + 1.45 * autosave + 0.85 * (n_buys_w1 >= 3) + 0.08 * min(n_buys_w1, 6)
                 + 0.45 * goal + 0.05 * alert + 0.30 * referral - 0.15 * (tier[i] == 3))
        p_ret = sigmoid(logit)
        retained = rng.random() < p_ret

        # daily app opens across 35 days; engagement decays, retained users keep opening
        days = np.arange(1, HORIZON_DAYS)
        base = sigmoid(-0.6 + 0.5 * z + 0.6 * autosave) * np.exp(-days / (9 if not retained else 60))
        if not retained:
            base[days >= int(rng.integers(12, 27))] = 0.0   # churned users go silent before the D30 window
        else:
            base[(days >= 28) & (days <= 34)] = np.maximum(base[(days >= 28) & (days <= 34)], 0.18)
        open_days = days[rng.random(len(days)) < base]
        if retained and not np.any((open_days >= 28) & (open_days <= 34)):
            open_days = np.append(open_days, rng.integers(28, 35))
        for d in open_days:
            add(uid, t0 + pd.Timedelta(days=int(d), hours=float(rng.uniform(7, 23))), "app_open")
            if d > 7 and rng.random() < 0.18:
                add(uid, t0 + pd.Timedelta(days=int(d), hours=float(rng.uniform(7, 23))),
                    "gold_purchased", amount=round(float(rng.lognormal(4.4, 0.8)), 0), source="manual")

        # autosave daily debits (a fraction of churned users cancel autosave)
        if autosave:
            cancel_day = HORIZON_DAYS if retained else int(rng.integers(8, 30))
            if cancel_day < HORIZON_DAYS:
                add(uid, t0 + pd.Timedelta(days=cancel_day, hours=10), "autosave_cancelled")
            for d in range(int(rng.integers(1, 7)), cancel_day):
                if rng.random() < 0.93:              # some UPI mandate failures
                    add(uid, t0 + pd.Timedelta(days=d, hours=6), "autosave_debit_success")
                else:
                    add(uid, t0 + pd.Timedelta(days=d, hours=6), "autosave_debit_failed")

    ev = pd.DataFrame(events, columns=["user_id", "event_ts", "event_name", "properties"])
    ev = ev.sort_values(["event_ts", "user_id"]).reset_index(drop=True)
    ev.insert(0, "event_id", np.arange(1, len(ev) + 1))
    ev["platform"] = ev["user_id"].map(dict(zip(users.user_id, users.device)))
    return users, ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=60000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    users, ev = generate(a.users, a.seed)
    users.to_parquet(DATA / "users.parquet", index=False)
    ev.to_parquet(DATA / "events.parquet", index=False)
    print(f"users: {len(users):,}  events: {len(ev):,}  "
          f"range: {ev.event_ts.min():%Y-%m-%d} -> {ev.event_ts.max():%Y-%m-%d}")


if __name__ == "__main__":
    main()
