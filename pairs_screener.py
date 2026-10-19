#!/usr/bin/env python3
"""
Pairs-Trading-Screener (US / Europa / Deutschland)

Testet alle Paare innerhalb eines Sektors (Aktien, Rohstoff-Futures, Index-Futures/
Indizes) auf Korrelation, Kointegration
(Engle-Granger), Mean-Reversion-Geschwindigkeit (Half-Life), Hurst-Exponent und
den aktuellen Spread-Z-Score. Erzeugt `pairs_data.json` und das Dashboard
`pairs.html`.

Aufruf:
    python pairs_screener.py                 # Daten via Yahoo Finance laden
    python pairs_screener.py --offline       # nur lokaler Cache (prices_cache.csv)
    python pairs_screener.py --cache-dir X   # Cache-Verzeichnis (default: ./cache)
"""

import argparse
import json
import math
import os
import sys
import time
import warnings
from datetime import datetime
from itertools import combinations

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from pairs_universe import UNIVERSE, FX_TICKERS, all_tickers, currency_of, region_of, asset_of, multiplier_of  # noqa: E402

# --------------------------------------------------------------------------- #
# Konfiguration
# --------------------------------------------------------------------------- #
CFG = {
    "download_years": 3.5,     # Historie, die geladen wird
    "coint_window": 504,       # Handelstage für Kointegrations-/Regressionsfenster (~2 Jahre)
    "corr_window": 252,        # Handelstage für die Korrelation der Tagesrenditen (~1 Jahr)
    "prefilter_corr": 0.25,    # Paare mit geringerer Renditekorrelation werden gar nicht erst getestet
    "min_overlap": 400,        # Mindestanzahl gemeinsamer Handelstage
    "max_stale_days": 10,      # Ticker verwerfen, deren letzter Kurs älter ist (Kalendertage)
    "series_days": 252,        # Länge der Chart-Serien im JSON
    "series_max_pairs": 250,   # Für wie viele Paare Chart-Serien ausgegeben werden
    "report_max_pvalue": 0.20, # Paare mit höherem p-Wert kommen nicht ins JSON
    "beta_range": (0.2, 5.0),  # Hedge Ratios außerhalb sind keine sinnvollen Paare (β≈0: Spread = Einzelaktie)
    "z_setup": 2.0,            # |z| ab dem ein Paar als SETUP gilt
    "z_watch": 1.5,            # |z| ab dem ein Paar auf WATCH steht
    "quality_min": 55,         # Mindest-Qualitätsscore für SETUP/WATCH
    "z_extreme": 4.0,          # ab hier Verdacht auf Strukturbruch
}

SCRATCH_DEFAULT_CACHE = "cache"


def log(msg):
    print(msg, flush=True)


# --------------------------------------------------------------------------- #
# Daten
# --------------------------------------------------------------------------- #
def read_cache(path):
    """Liest einen Long-CSV (date,ticker,close) in ein Wide-DataFrame."""
    if not path or not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    wide = df.pivot_table(index="date", columns="ticker", values="close", aggfunc="last")
    return wide.sort_index()


def download_yahoo(tickers, start):
    import yfinance as yf
    frames = []
    chunk = 60
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i + chunk]
        for attempt in range(3):
            try:
                d = yf.download(part, start=start, progress=False, auto_adjust=True,
                                group_by="column", threads=True)
                break
            except Exception as e:  # pragma: no cover
                log(f"  Download-Fehler ({e}), Versuch {attempt + 1}/3")
                time.sleep(5 * (attempt + 1))
                d = None
        if d is None or d.empty:
            continue
        if isinstance(d.columns, pd.MultiIndex):
            close = d["Close"] if "Close" in d.columns.get_level_values(0) else d.xs("Close", axis=1, level=0)
        else:
            close = d[["Close"]].rename(columns={"Close": part[0]})
        frames.append(close)
        log(f"  {min(i + chunk, len(tickers))}/{len(tickers)} Ticker geladen")
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, axis=1)
    out = out.loc[:, ~out.columns.duplicated()]
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out.sort_index()


def load_prices(tickers, offline, cache_dir):
    start = (datetime.now() - pd.Timedelta(days=int(CFG["download_years"] * 365))).strftime("%Y-%m-%d")
    cache_px = read_cache(os.path.join(cache_dir, "prices_cache.csv"))
    cache_fx = read_cache(os.path.join(cache_dir, "fx_cache.csv"))

    px, fx = pd.DataFrame(), pd.DataFrame()
    if not offline:
        log("Lade Kurse von Yahoo Finance ...")
        px = download_yahoo(tickers, start)
        fx = download_yahoo(sorted(set(FX_TICKERS.values())), start)

    if not cache_px.empty:
        px = cache_px if px.empty else px.combine_first(cache_px)
    if not cache_fx.empty:
        fx = cache_fx if fx.empty else fx.combine_first(cache_fx)

    if px.empty:
        sys.exit("Keine Kursdaten verfügbar (weder Download noch Cache).")

    # Bereinigen: nur Ticker aus dem Universum, numerisch, keine Nullpreise
    px = px.reindex(columns=[t for t in tickers if t in px.columns]).astype(float)
    px = px.where(px > 0)
    # Verwaiste / delistete Ticker entfernen
    last_ok = px.apply(lambda s: s.last_valid_index())
    cutoff = px.index.max() - pd.Timedelta(days=CFG["max_stale_days"])
    stale = [t for t, d in last_ok.items() if d is None or d < cutoff]
    too_short = [t for t in px.columns if px[t].notna().sum() < CFG["min_overlap"]]
    drop = sorted(set(stale) | set(too_short))
    if drop:
        log(f"  Verworfen ({len(drop)}): {', '.join(drop)}")
    px = px.drop(columns=drop)
    return px, fx


def to_eur(px, fx):
    """Rechnet alle Kurse in EUR um. Gibt (px_eur, ok) zurück; ok=False, wenn FX fehlt."""
    if fx.empty:
        return px.copy(), False
    out = px.copy()
    fxa = fx.reindex(px.index).ffill().bfill()
    for t in px.columns:
        cur = currency_of(t)
        if cur == "EUR":
            continue
        fxt = FX_TICKERS[cur]
        if fxt not in fxa.columns:
            return px.copy(), False
        scale = 0.01 if cur == "GBp" else 1.0
        out[t] = px[t] * scale / fxa[fxt]
    return out, True


# --------------------------------------------------------------------------- #
# Statistik
# --------------------------------------------------------------------------- #
def half_life(resid):
    r = resid.values
    dr = np.diff(r)
    lag = r[:-1]
    if len(lag) < 20 or np.std(lag) == 0:
        return float("inf")
    b = np.polyfit(lag, dr, 1)[0]
    if b >= 0 or b <= -1:
        return float("inf")
    return float(-math.log(2) / math.log(1 + b))


def hurst(resid, max_lag=20):
    """Hurst-Exponent über die Varianz der Lag-Differenzen (0.5 = Random Walk, <0.5 = mean-reverting)."""
    r = resid.values
    lags = range(2, max_lag + 1)
    tau = []
    for lag in lags:
        d = r[lag:] - r[:-lag]
        s = np.std(d)
        tau.append(s if s > 0 else np.nan)
    tau = np.array(tau)
    ok = ~np.isnan(tau)
    if ok.sum() < 5:
        return float("nan")
    slope = np.polyfit(np.log(np.array(list(lags))[ok]), np.log(tau[ok]), 1)[0]
    return float(slope)


def zero_crossings(resid):
    s = np.sign(resid.values)
    s = s[s != 0]
    return int((s[1:] * s[:-1] < 0).sum())


def days_since_cross(resid):
    s = np.sign(resid.values)
    last = s[-1]
    n = 0
    for v in s[::-1]:
        if v == last or v == 0:
            n += 1
        else:
            break
    return n


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def quality_score(p, corr, hl, drift, h):
    s_coint = 35 * clamp(1 - p / 0.10)
    s_corr = 20 * clamp((corr - 0.30) / 0.60)
    if hl <= 5:
        s_hl = 20 * clamp(hl / 5)
    elif hl <= 40:
        s_hl = 20.0
    else:
        s_hl = 20 * clamp(1 - (hl - 40) / 80)
    s_drift = 10 * clamp(1 - drift / 0.5)
    s_hurst = 15 * clamp((0.5 - h) / 0.3) if not math.isnan(h) else 0.0
    return s_coint + s_corr + s_hl + s_drift + s_hurst


def track_pair(a, b, pa, pb):
    """Minimalstatistik für die Watchlist: Regression b ~ a, aktueller z, Spread-σ, Half-Life."""
    df = pd.concat([pa, pb], axis=1, keys=["a", "b"]).ffill(limit=3).dropna().tail(CFG["coint_window"])
    if len(df) < CFG["min_overlap"]:
        return None
    la, lb = np.log(df["a"]), np.log(df["b"])
    beta, alpha = np.polyfit(la.values, lb.values, 1)
    resid = lb - (alpha + beta * la)
    sd = resid.std(ddof=1)
    if not (sd > 0):
        return None
    return {"dep": b, "z": float(resid.iloc[-1] / sd), "sd": float(sd * 100), "beta": float(beta),
            "hl": half_life(resid)}


def analyze_pair(a, b, pa, pb):
    """pa, pb: Preis-Serien (bereits in gemeinsamer Währung, falls nötig)."""
    from statsmodels.tsa.stattools import coint

    df = pd.concat([pa, pb], axis=1, keys=["a", "b"]).ffill(limit=3).dropna()
    df = df.tail(CFG["coint_window"])
    if len(df) < CFG["min_overlap"]:
        return None

    la, lb = np.log(df["a"]), np.log(df["b"])

    # Vorfilter: Paare ohne nennenswerte Renditekorrelation sind nie gute Kandidaten
    # (spart den teuren Kointegrationstest)
    pre_corr = la.diff().tail(CFG["corr_window"]).corr(lb.diff().tail(CFG["corr_window"]))
    if np.isnan(pre_corr) or pre_corr < CFG["prefilter_corr"]:
        return None

    # Richtung wählen: die Regressionsrichtung mit dem niedrigeren p-Wert
    p_ab = coint(lb.values, la.values, trend="c", autolag="aic")[1]   # b ~ a
    p_ba = coint(la.values, lb.values, trend="c", autolag="aic")[1]   # a ~ b
    if p_ba < p_ab:
        a, b, la, lb, p = b, a, lb, la, p_ba
        pa_, pb_ = df["b"], df["a"]
    else:
        p = p_ab
        pa_, pb_ = df["a"], df["b"]
    if p > CFG["report_max_pvalue"]:
        return None

    beta, alpha = np.polyfit(la.values, lb.values, 1)
    if not (CFG["beta_range"][0] <= beta <= CFG["beta_range"][1]):
        return None
    resid = lb - (alpha + beta * la)
    sd = resid.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return None
    z = resid / sd

    # Korrelation der Tagesrenditen
    ra, rb = la.diff(), lb.diff()
    corr = float(ra.tail(CFG["corr_window"]).corr(rb.tail(CFG["corr_window"])))
    corr_full = float(ra.corr(rb))
    if np.isnan(corr) or corr <= 0:
        return None

    # Beta-Stabilität: erste vs. zweite Hälfte
    half = len(la) // 2
    b1 = np.polyfit(la.values[:half], lb.values[:half], 1)[0]
    b2 = np.polyfit(la.values[half:], lb.values[half:], 1)[0]
    drift = float(abs(b1 - b2) / abs(beta))

    hl = half_life(resid)
    h = hurst(resid)
    zc = zero_crossings(resid)
    dsc = days_since_cross(resid)
    spread_vol = float(resid.diff().std() * math.sqrt(252) * 100)

    z_now = float(z.iloc[-1])
    z_5 = float(z.iloc[-6]) if len(z) > 6 else float("nan")
    z_20 = float(z.iloc[-21]) if len(z) > 21 else float("nan")

    q = quality_score(p, corr, hl, drift, h)
    sig = clamp(abs(z_now) / CFG["z_setup"])
    total = q * sig
    if abs(z_now) >= CFG["z_extreme"]:
        total *= 0.7

    if q >= CFG["quality_min"] and abs(z_now) >= CFG["z_setup"]:
        status = "SETUP"
    elif q >= CFG["quality_min"] and abs(z_now) >= CFG["z_watch"]:
        status = "WATCH"
    else:
        status = "-"
    if abs(z_now) >= CFG["z_extreme"]:
        status = "EXTREM"

    # Spread = log(b) - beta*log(a) - alpha. z>0: b zu teuer relativ zu a -> Short b / Long a.
    if z_now > 0:
        long_leg, short_leg = a, b
    else:
        long_leg, short_leg = b, a

    return {
        "a": a, "b": b, "p": float(p), "beta": float(beta), "alpha": float(alpha),
        "corr": corr, "corr_full": corr_full, "half_life": hl, "hurst": h,
        "zero_cross": zc, "days_since_cross": dsc, "spread_vol": spread_vol,
        "beta_drift": drift, "z": z_now, "z5": z_5, "z20": z_20,
        "exp_move_pct": float(abs(z_now) * sd * 100),
        "spread_sd_pct": float(sd * 100),
        "quality": float(q), "score": float(total), "status": status,
        "long": long_leg, "short": short_leg, "n": int(len(df)),
        "last_date": df.index[-1].strftime("%Y-%m-%d"),
        "_z_series": z.tail(CFG["series_days"]),
        "_pa": pa_.tail(CFG["series_days"]), "_pb": pb_.tail(CFG["series_days"]),
    }


# --------------------------------------------------------------------------- #
# Hauptprogramm
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="nur lokalen Cache verwenden")
    ap.add_argument("--cache-dir", default=SCRATCH_DEFAULT_CACHE)
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--sectors", default="", help="Komma-Liste, nur diese Sektoren rechnen (Test)")
    args = ap.parse_args()

    t0 = time.time()
    tickers = all_tickers()
    names = {t: n for members in UNIVERSE.values() for t, n in members}
    px, fx = load_prices(tickers, args.offline, args.cache_dir)
    px_eur, fx_ok = to_eur(px, fx)
    log(f"Kursdaten: {px.shape[1]} Ticker, {px.index.min().date()} bis {px.index.max().date()}"
        f"{'' if fx_ok else '  [FX fehlt: Cross-Currency-Paare in Lokalwährung]'}")

    sectors = UNIVERSE
    if args.sectors:
        wanted = [s.strip() for s in args.sectors.split(",")]
        sectors = {k: v for k, v in UNIVERSE.items() if k in wanted}

    results, n_tested = [], 0
    track = {}   # "A|B" (alphabetisch) -> Tracking-Daten für die Watchlist, für alle testbaren Paare
    for sector, members in sectors.items():
        avail = [t for t, _ in members if t in px.columns]
        n_pairs = len(avail) * (len(avail) - 1) // 2
        for a, b in combinations(avail, 2):
            n_tested += 1
            same_cur = currency_of(a) == currency_of(b)
            src = px if same_cur else px_eur
            try:
                r = analyze_pair(a, b, src[a], src[b])
            except Exception as e:  # einzelne Ausreißer nicht die ganze Berechnung kosten lassen
                log(f"  Fehler {a}/{b}: {e}")
                continue
            key = "|".join(sorted([a, b]))
            if r is None:
                try:
                    t = track_pair(a, b, src[a], src[b])
                except Exception:
                    t = None
                if t:
                    track[key] = t
                continue
            track[key] = {"dep": r["b"], "z": r["z"], "sd": r["spread_sd_pct"], "beta": r["beta"], "hl": r["half_life"]}
            r["sector"] = sector
            r["fx"] = (not same_cur)
            r["fx_converted"] = (not same_cur) and fx_ok
            ra, rb = region_of(r["a"]), region_of(r["b"])
            r["region"] = ra if ra == rb else "Cross"
            r["region_a"], r["region_b"] = ra, rb
            r["cur_a"], r["cur_b"] = currency_of(r["a"]), currency_of(r["b"])
            r["name_a"], r["name_b"] = names.get(r["a"], r["a"]), names.get(r["b"], r["b"])
            r["asset"] = asset_of(r["a"])
            r["mult_a"], r["mult_b"] = multiplier_of(r["a"]), multiplier_of(r["b"])
            r["last_a"], r["last_b"] = float(px[r["a"]].dropna().iloc[-1]), float(px[r["b"]].dropna().iloc[-1])
            results.append(r)
        log(f"  {sector}: {len(avail)} Aktien, {n_pairs} Paare getestet")

    results.sort(key=lambda r: (-r["score"], r["p"]))
    log(f"{n_tested} Paare getestet, {len(results)} mit p <= {CFG['report_max_pvalue']}, "
        f"{sum(r['p'] < 0.05 for r in results)} mit p < 0.05, "
        f"{sum(r['status'] == 'SETUP' for r in results)} Setups, "
        f"{sum(r['status'] == 'WATCH' for r in results)} Watch  ({time.time() - t0:.0f}s)")

    # Chart-Serien nur für die relevantesten Paare
    by_quality = sorted(results, key=lambda r: -r["quality"])
    with_series = set(id(r) for r in results[:CFG["series_max_pairs"]])
    with_series |= set(id(r) for r in by_quality[:CFG["series_max_pairs"] // 2])
    with_series |= set(id(r) for r in results if r["status"] in ("SETUP", "WATCH", "EXTREM"))

    def fnum(x, nd=3):
        if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
            return None
        return round(float(x), nd)

    pairs_json = []
    for i, r in enumerate(results):
        d = {
            "id": i, "sector": r["sector"], "region": r["region"], "fx": r["fx"],
            "a": r["a"], "b": r["b"], "na": r["name_a"], "nb": r["name_b"],
            "ra": r["region_a"], "rb": r["region_b"], "ca": r["cur_a"], "cb": r["cur_b"],
            "p": fnum(r["p"], 4), "beta": fnum(r["beta"], 3), "corr": fnum(r["corr"], 3),
            "corr_full": fnum(r["corr_full"], 3), "hl": fnum(r["half_life"], 1), "hurst": fnum(r["hurst"], 3),
            "zc": r["zero_cross"], "dsc": r["days_since_cross"], "svol": fnum(r["spread_vol"], 1),
            "drift": fnum(r["beta_drift"], 3), "z": fnum(r["z"], 2), "z5": fnum(r["z5"], 2), "z20": fnum(r["z20"], 2),
            "move": fnum(r["exp_move_pct"], 1), "sd": fnum(r["spread_sd_pct"], 2),
            "q": fnum(r["quality"], 1), "score": fnum(r["score"], 1),
            "status": r["status"], "long": r["long"], "short": r["short"], "n": r["n"], "last": r["last_date"],
            "asset": r["asset"], "ma": r["mult_a"], "mb": r["mult_b"], "pxa": fnum(r["last_a"], 2), "pxb": fnum(r["last_b"], 2),
        }
        if id(r) in with_series:
            zs = r["_z_series"]
            pa, pb = r["_pa"], r["_pb"]
            d["series"] = {
                "dates": [x.strftime("%Y-%m-%d") for x in zs.index],
                "z": [fnum(v, 2) for v in zs.values],
                "pa": [fnum(v / pa.iloc[0] * 100, 1) for v in pa.values],
                "pb": [fnum(v / pb.iloc[0] * 100, 1) for v in pb.values],
            }
        pairs_json.append(d)

    universe_json = [{"t": t, "name": names[t], "sector": s, "region": region_of(t), "cur": currency_of(t),
                      "asset": asset_of(t), "mult": multiplier_of(t), "ok": t in px.columns}
                     for s, members in UNIVERSE.items() for t, _ in members]

    meta = {
        "generated": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "data_date": px.index.max().strftime("%Y-%m-%d"),
        "n_tickers": int(px.shape[1]), "n_universe": len(tickers), "n_tested": n_tested,
        "n_reported": len(results), "n_coint": int(sum(r["p"] < 0.05 for r in results)),
        "n_setup": int(sum(r["status"] == "SETUP" for r in results)),
        "n_watch": int(sum(r["status"] == "WATCH" for r in results)),
        "fx_ok": bool(fx_ok), "cfg": CFG, "sectors": list(UNIVERSE.keys()),
        # letzte EUR-Wechselkurse je Währung (Preis_EUR = Preis_lokal * Skala / Kurs)
        "fx_last": {cur: float(fx[tk].dropna().iloc[-1]) for cur, tk in FX_TICKERS.items()
                    if not fx.empty and tk in fx.columns and fx[tk].notna().any()},
    }
    track_json = {k: [v["dep"], fnum(v["z"], 2), fnum(v["sd"], 2), fnum(v["beta"], 3), fnum(v["hl"], 1)]
                  for k, v in track.items()}
    last_px = {t: fnum(px[t].dropna().iloc[-1], 4) for t in px.columns if px[t].notna().any()}
    payload = {"meta": meta, "pairs": pairs_json, "universe": universe_json, "track": track_json, "last_px": last_px}

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "pairs_data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pairs_template.html")
    with open(tpl_path, encoding="utf-8") as f:
        tpl = f.read()
    html = tpl.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    with open(os.path.join(args.out_dir, "pairs.html"), "w", encoding="utf-8") as f:
        f.write(html)
    log(f"Geschrieben: pairs_data.json, pairs.html ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
