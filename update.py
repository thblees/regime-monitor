"""
Erweitertes Dashboard mit Ausklapp-Erklärungen.
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime

# Daten neu erzeugen
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")

START = "2008-01-01"
END = (datetime.now() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

def fetch(ticker):
    d = yf.download(ticker, start=START, end=END, progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d["Close"].dropna()

print("Lade Daten neu für Dashboard...")
data = {}
for nm, tk in [("VIX","^VIX"),("VIX3M","^VIX3M"),("MOVE","^MOVE"),
               ("HYG","HYG"),("IEF","IEF"),("XLY","XLY"),("XLP","XLP"),("SPX","^GSPC")]:
    data[nm] = fetch(tk)
    print(f"  {nm}: bis {data[nm].index[-1].date()}")

df = pd.concat(data.values(), axis=1)
df.columns = list(data.keys())
df = df.reindex(df["SPX"].dropna().index).ffill(limit=5)
df["VIX_TS"] = df["VIX"] / df["VIX3M"]
df["HYG_IEF"] = df["HYG"] / df["IEF"]
df["XLY_XLP"] = df["XLY"] / df["XLP"]

INDICATORS = {"VIX":"high","VIX_TS":"high","MOVE":"high","HYG_IEF":"low","XLY_XLP":"low"}
CLUSTERS = {"Vol":["VIX","VIX_TS","MOVE"],"Credit":["HYG_IEF"],"Risk_Off":["XLY_XLP"]}

pct = pd.DataFrame(index=df.index)
for name, dirn in INDICATORS.items():
    p = df[name].rolling(252).rank(pct=True)
    if dirn == "low":
        p = 1 - p
    pct[name] = p

for cname, members in CLUSTERS.items():
    df[f"cluster_{cname}"] = pct[members].max(axis=1)
for name in INDICATORS:
    df[f"ind_pct_{name}"] = pct[name]

def classify(row):
    if row.isna().any(): return np.nan
    high = (row >= 0.75).sum()
    extreme = (row >= 0.95).any()
    if extreme or high == 3: return "C_Stress"
    if high >= 1: return "B_Erhoeht"
    return "A_Ruhig"

df["regime"] = df[["cluster_Vol","cluster_Credit","cluster_Risk_Off"]].apply(classify, axis=1)

# Crash-Flag
close = df["SPX"].values
n = len(close)
mn = np.full(n, np.nan)
for i in range(n-1):
    e = min(i+1+20, n)
    if e > i+1: mn[i] = close[i+1:e].min()
df["max_dd_20d"] = mn/close - 1
df["pre_crash"] = df["max_dd_20d"] <= -0.10

# Forward-Returns
for h in [5,20,60]:
    df[f"fwd_{h}d"] = df["SPX"].pct_change(h).shift(-h)

# Statistik
valid = df.dropna(subset=["regime"])
base_rate = valid["pre_crash"].mean()
stats = {"base_rate": base_rate}
for r in ["A_Ruhig","B_Erhoeht","C_Stress"]:
    sub = df[df["regime"]==r]
    valid_sub = sub.dropna(subset=["pre_crash"])
    stats[r] = {
        "n": int(len(valid_sub)),
        "share": float(len(valid_sub)/len(valid)) if len(valid)>0 else 0,
        "crash_rate": float(valid_sub["pre_crash"].mean()) if len(valid_sub)>0 else 0,
        "median_20": float(sub["fwd_20d"].median()*100),
        "worst5_20": float(sub["fwd_20d"].quantile(0.05)*100),
        "worst5_60": float(sub["fwd_60d"].quantile(0.05)*100),
    }

# Aktueller Stand
latest = valid.iloc[-1]
latest_date = valid.index[-1]
curr_regime = latest["regime"]
days_in_regime = 0
for d in reversed(valid.index):
    if valid.loc[d,"regime"] == curr_regime:
        days_in_regime = (latest_date - d).days
    else: break

# Chart-Daten 5 Jahre
chart_data = valid.tail(252*5).copy()
chart_data["score"] = chart_data[["cluster_Vol","cluster_Credit","cluster_Risk_Off"]].mean(axis=1)*100
chart_json = []
for d, r in chart_data.iterrows():
    chart_json.append({
        "date": d.strftime("%Y-%m-%d"),
        "spx": round(float(r["SPX"]),2),
        "vol": round(float(r["cluster_Vol"]*100),1),
        "credit": round(float(r["cluster_Credit"]*100),1),
        "riskoff": round(float(r["cluster_Risk_Off"]*100),1),
        "score": round(float(r["score"]),1),
        "regime": r["regime"]
    })

real_crashes = [
    ("GFC","2007-10-09","2009-03-09"),("Flash/EU 2010","2010-04-23","2010-07-02"),
    ("US Downgrade","2011-07-07","2011-10-04"),("China-Schock","2015-07-20","2016-02-11"),
    ("Volmageddon","2018-01-26","2018-02-09"),("Powell-Pivot","2018-09-20","2018-12-24"),
    ("Covid","2020-01-17","2020-03-23"),("Fed-Hiking 2022","2022-01-03","2022-10-13"),
    ("Tariff-Schock","2025-02-19","2025-04-08"),
]
crash_markers = [{"name":n,"low":l} for n,_,l in real_crashes if pd.Timestamp(l) >= chart_data.index[0]]

ind_values = {
    "VIX":       (float(latest["VIX"]),     float(latest["ind_pct_VIX"])*100),
    "VIX/VIX3M": (float(latest["VIX_TS"]),  float(latest["ind_pct_VIX_TS"])*100),
    "MOVE":      (float(latest["MOVE"]),    float(latest["ind_pct_MOVE"])*100),
    "HYG/IEF":   (float(latest["HYG_IEF"]), float(latest["ind_pct_HYG_IEF"])*100),
    "XLY/XLP":   (float(latest["XLY_XLP"]), float(latest["ind_pct_XLY_XLP"])*100),
}

REGIME = {
    "A_Ruhig":   {"label":"RUHIG",  "color":"#4ade80", "code":"A"},
    "B_Erhoeht": {"label":"ERHÖHT", "color":"#fbbf24", "code":"B"},
    "C_Stress":  {"label":"STRESS", "color":"#ef4444", "code":"C"},
}
curr = REGIME[curr_regime]

# Cluster-Bars
def cb(name, val):
    v = val*100
    col = "var(--red)" if v>=75 else "var(--yellow)" if v>=50 else "var(--green)"
    return f'''<div class="cluster-bar">
        <div class="cluster-header"><span class="cluster-name">{name}</span>
        <span class="cluster-value">{v:.0f}<span style="color:var(--text-muted)">/100</span></span></div>
        <div class="cluster-track"><div class="cluster-fill" style="width:{v:.0f}%;background:{col}"></div></div></div>'''

cluster_html = cb("Volatility-Cluster", latest["cluster_Vol"]) + cb("Credit-Cluster", latest["cluster_Credit"]) + cb("Risk-Off-Cluster", latest["cluster_Risk_Off"])

ind_rows = ""
for name, (val, p) in ind_values.items():
    col = "var(--red)" if p>=75 else "var(--yellow)" if p>=50 else "var(--green)"
    ind_rows += f'''<div class="ind-row">
        <div class="ind-name">{name}</div><div class="ind-val">{val:.2f}</div>
        <div class="ind-bar-track"><div class="ind-bar-fill" style="width:{p:.0f}%;background:{col}"></div></div>
        <div class="ind-pct">P{p:.0f}</div></div>'''

# HTML
html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Markt-Regime-Monitor · Thomas Bleeß</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter+Tight:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root {{
    --bg:#0a0e1a; --bg-card:#121826; --bg-elevated:#1a2236; --border:#1f2a3e;
    --text:#e2e8f0; --text-dim:#94a3b8; --text-muted:#64748b;
    --green:#4ade80; --yellow:#fbbf24; --red:#ef4444; --blue:#60a5fa;
    --accent:{curr['color']};
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    background:var(--bg); color:var(--text); font-family:'Inter Tight',sans-serif;
    line-height:1.5; min-height:100vh;
    background-image:radial-gradient(at 20% 0%,rgba(96,165,250,0.05) 0,transparent 50%),
                     radial-gradient(at 80% 50%,rgba(74,222,128,0.03) 0,transparent 50%);
}}
.container {{ max-width:1400px; margin:0 auto; padding:32px 24px; }}

.header {{ display:flex; justify-content:space-between; align-items:flex-end;
    margin-bottom:32px; padding-bottom:20px; border-bottom:1px solid var(--border); }}
.title-block h1 {{ font-size:28px; font-weight:800; letter-spacing:-0.02em; margin-bottom:4px; }}
.title-block .subtitle {{ color:var(--text-dim); font-size:13px; font-family:'JetBrains Mono',monospace;
    letter-spacing:0.05em; text-transform:uppercase; }}
.title-block .author {{ color:var(--text-muted); font-size:12px; margin-top:4px; }}
.title-block .author a {{ color:var(--blue); text-decoration:none; }}
.title-block .author a:hover {{ text-decoration:underline; }}
.timestamp {{ color:var(--text-dim); font-family:'JetBrains Mono',monospace; font-size:13px; text-align:right; }}
.timestamp .label {{ color:var(--text-muted); font-size:11px; text-transform:uppercase;
    letter-spacing:0.1em; margin-bottom:4px; }}

.back-link {{ display:inline-block; color:var(--blue); font-size:13px; margin-bottom:20px;
    text-decoration:none; font-family:'JetBrains Mono',monospace; }}
.back-link:hover {{ text-decoration:underline; }}

.hero {{ background:var(--bg-card); border:1px solid var(--border); border-radius:12px;
    padding:40px; margin-bottom:24px; position:relative; overflow:hidden; }}
.hero::before {{ content:''; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--accent); }}
.hero-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:48px; align-items:center; }}
.regime-display {{ display:flex; flex-direction:column; gap:8px; }}
.regime-label {{ font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--text-muted);
    text-transform:uppercase; letter-spacing:0.15em; }}
.regime-code {{ font-family:'JetBrains Mono',monospace; font-size:14px; color:var(--accent); font-weight:500; }}
.regime-name {{ font-size:84px; font-weight:800; letter-spacing:-0.04em; line-height:1;
    color:var(--accent); margin:8px 0; }}
.regime-duration {{ color:var(--text-dim); font-size:14px; font-family:'JetBrains Mono',monospace; }}

.cluster-bars {{ display:flex; flex-direction:column; gap:16px; }}
.cluster-bar {{ display:flex; flex-direction:column; gap:6px; }}
.cluster-header {{ display:flex; justify-content:space-between; font-size:13px; }}
.cluster-name {{ font-weight:600; color:var(--text); }}
.cluster-value {{ font-family:'JetBrains Mono',monospace; color:var(--text-dim); font-weight:500; }}
.cluster-track {{ height:8px; background:var(--bg-elevated); border-radius:4px; overflow:hidden; position:relative; }}
.cluster-track::after {{ content:''; position:absolute; left:75%; top:-2px; bottom:-2px;
    width:1px; background:var(--text-muted); opacity:0.5; }}
.cluster-fill {{ height:100%; border-radius:4px; transition:width 0.5s ease; }}

.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; margin-bottom:24px; }}
.card {{ background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:24px; }}
.card-title {{ font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--text-muted);
    text-transform:uppercase; letter-spacing:0.15em; margin-bottom:16px; font-weight:500; }}
.card.full {{ grid-column:1/-1; }}

table {{ width:100%; border-collapse:collapse; font-family:'JetBrains Mono',monospace; font-size:13px; }}
th,td {{ text-align:left; padding:10px 12px; border-bottom:1px solid var(--border); }}
th {{ color:var(--text-muted); font-weight:500; font-size:11px; text-transform:uppercase; letter-spacing:0.1em; }}
td.num {{ text-align:right; }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px; vertical-align:middle; }}
.dot-a {{ background:var(--green); }} .dot-b {{ background:var(--yellow); }} .dot-c {{ background:var(--red); }}

.ind-list {{ display:flex; flex-direction:column; gap:12px; }}
.ind-row {{ display:grid; grid-template-columns:100px 80px 1fr 60px; gap:12px; align-items:center;
    font-family:'JetBrains Mono',monospace; font-size:13px; }}
.ind-name {{ font-weight:600; }}
.ind-val {{ color:var(--text-dim); }}
.ind-bar-track {{ height:6px; background:var(--bg-elevated); border-radius:3px; overflow:hidden; position:relative; }}
.ind-bar-track::after {{ content:''; position:absolute; left:75%; top:-2px; bottom:-2px;
    width:1px; background:var(--text-muted); opacity:0.4; }}
.ind-bar-fill {{ height:100%; border-radius:3px; }}
.ind-pct {{ text-align:right; color:var(--text-dim); font-weight:500; }}

.chart-wrapper {{ position:relative; height:360px; }}

.disclaimer {{
    background:linear-gradient(135deg,#1a1f2e 0%,#1a2236 100%);
    border:1px solid var(--border); border-left:3px solid var(--blue);
    border-radius:8px; padding:20px 24px; margin-bottom:24px;
    font-size:13px; line-height:1.7; color:var(--text-dim);
}}
.disclaimer strong {{ color:var(--text); }}
.disclaimer .head {{ font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--blue);
    text-transform:uppercase; letter-spacing:0.15em; font-weight:600; margin-bottom:8px; }}

/* AUSKLAPP-ERKLÄRUNGEN */
.explainer {{
    margin-top: 16px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-elevated);
    overflow: hidden;
    transition: all 0.2s ease;
}}
.explainer summary {{
    padding: 12px 16px;
    cursor: pointer;
    color: var(--blue);
    font-size: 13px;
    font-weight: 500;
    list-style: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    user-select: none;
    transition: background 0.2s;
}}
.explainer summary:hover {{ background: rgba(96,165,250,0.05); }}
.explainer summary::-webkit-details-marker {{ display: none; }}
.explainer summary::after {{
    content: '▾';
    font-size: 12px;
    color: var(--blue);
    transition: transform 0.2s;
}}
.explainer[open] summary::after {{ transform: rotate(180deg); }}
.explainer-content {{
    padding: 8px 20px 20px 20px;
    color: var(--text);
    font-size: 14px;
    line-height: 1.7;
    border-top: 1px solid var(--border);
    margin-top: 0;
}}
.explainer-content p {{ margin-bottom: 12px; }}
.explainer-content p:last-child {{ margin-bottom: 0; }}
.explainer-content strong {{ color: var(--text); }}
.explainer-content em {{ color: var(--text-dim); font-style: italic; }}
.explainer-content ul {{ margin: 8px 0 12px 20px; }}
.explainer-content li {{ margin-bottom: 6px; }}
.explainer-content .example {{
    background: var(--bg);
    border-left: 2px solid var(--accent);
    padding: 12px 16px;
    margin: 12px 0;
    border-radius: 0 6px 6px 0;
    font-size: 13px;
    color: var(--text-dim);
}}
.explainer-content .example strong {{ color: var(--accent); }}
.explainer-content .traffic-light {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 600;
    margin: 0 2px;
}}
.tl-green {{ background: rgba(74,222,128,0.15); color: var(--green); }}
.tl-yellow {{ background: rgba(251,191,36,0.15); color: var(--yellow); }}
.tl-red {{ background: rgba(239,68,68,0.15); color: var(--red); }}

.footer {{ color:var(--text-muted); font-size:12px; text-align:center; padding:24px 0;
    border-top:1px solid var(--border); margin-top:24px; font-family:'JetBrains Mono',monospace; }}

@media (max-width:900px) {{
    .hero-grid {{ grid-template-columns:1fr; gap:32px; }}
    .grid {{ grid-template-columns:1fr; }}
    .regime-name {{ font-size:64px; }}
}}
</style>
</head>
<body>
<div class="container">

<a href="https://thblees.github.io/trading-command-center/" class="back-link">← Zurück zum Command Center</a>

<div class="header">
    <div class="title-block">
        <h1>Markt-Regime-Monitor</h1>
        <div class="subtitle">US-Aktienmarkt · Risiko-Klassifizierung</div>
        <div class="author">Thomas Bleeß · <a href="https://www.meine-geldseite.de" target="_blank">meine-geldseite.de</a></div>
    </div>
    <div class="timestamp">
        <div class="label">Stand</div>
        <div>{latest_date.strftime('%d. %B %Y')}</div>
        <div style="margin-top:4px;color:var(--text-muted)">Letzter Handelstag SPX</div>
    </div>
</div>

<!-- HERO -->
<div class="hero">
    <div class="hero-grid">
        <div class="regime-display">
            <div class="regime-label">Aktuelles Regime</div>
            <div class="regime-code">▌ ZUSTAND {curr['code']}</div>
            <div class="regime-name">{curr['label']}</div>
            <div class="regime-duration">seit {days_in_regime} Tagen · SPX {int(latest['SPX'])}</div>
        </div>
        <div class="cluster-bars">{cluster_html}</div>
    </div>
</div>

<!-- ERKLÄRUNG: Was ist das Regime? -->
<details class="explainer">
    <summary>📖 Was bedeutet das Regime? · Erklärung für Einsteiger</summary>
    <div class="explainer-content">
        <p><strong>Der Marktzustand in einer Zahl.</strong> Statt dir 8 verschiedene Indikatoren gleichzeitig anschauen zu müssen, fasst dieses Tool den US-Aktienmarkt in <em>einem einzigen Wert</em> zusammen: das aktuelle Regime.</p>

        <p>Es gibt drei Stufen, ähnlich wie eine Ampel:</p>
        <ul>
            <li><span class="traffic-light tl-green">A · RUHIG</span> Der Markt ist entspannt. Volatilität niedrig, Credit-Märkte ruhig, Anleger sind risikobereit. <em>Historisch waren in diesem Zustand nur 1,0 % der Tage "Pre-Crash"-Tage.</em></li>
            <li><span class="traffic-light tl-yellow">B · ERHÖHT</span> Erste Stress-Signale. Ein oder zwei der drei Cluster sind im oberen 25 %-Bereich ihrer 1-Jahres-Verteilung. <em>Hier waren historisch 4,7 % der Tage Pre-Crash-Tage — also etwa die durchschnittliche Häufigkeit.</em></li>
            <li><span class="traffic-light tl-red">C · STRESS</span> Multiple Stress-Signale aktiv. Entweder schlagen alle drei Cluster gleichzeitig an, oder einer ist im extremen Bereich (oberes 5 %). <em>Hier waren historisch 11,5 % der Tage Pre-Crash-Tage — also 2,4× häufiger als im Durchschnitt.</em></li>
        </ul>

        <div class="example">
            <strong>Wichtig:</strong> Das ist <strong>keine</strong> Crash-Vorhersage. Es bedeutet nicht "Crash kommt morgen". Es sagt nur: "Aktuell sieht der Markt so aus wie in historischen Phasen, in denen häufiger (oder seltener) Crashs folgten." Die Entscheidung, was du daraus machst, liegt bei dir.
        </div>

        <p><strong>Wofür ist das gut?</strong> Statt blind durchgehend voll investiert zu bleiben oder panisch zu verkaufen, kannst du deine Hedging-Aktivität und Positionsgröße an das aktuelle Regime anpassen. In Zustand A sind Hedges meist günstig (niedrige Volatilität), in Zustand C werden sie teuer — also lohnt es sich, früher zu reagieren.</p>
    </div>
</details>

<div class="disclaimer">
    <div class="head">▌ Was dieses Tool ist – und was nicht</div>
    Dieser Monitor ist <strong>kein Crash-Vorhersage-System</strong>. Er klassifiziert ausschließlich den <strong>aktuellen</strong> Zustand des US-Aktienmarkts in drei Regime auf Basis von Volatilitäts-, Credit- und Risk-Off-Indikatoren. Er sagt <strong>nichts</strong> darüber aus, was als Nächstes passiert. Die historischen Statistiken (Pre-Crash-Häufigkeit pro Regime) sind <em>konditionale Beschreibungen der Vergangenheit</em>, keine Wahrscheinlichkeiten für die Zukunft. Marktstruktur verändert sich (Lucas-Kritik). Verwende dieses Tool, um deine <strong>Risiko-Exposition bewusst</strong> an das aktuelle Regime anzupassen – nicht, um Crashs zu "timen".
</div>

<!-- ERKLÄRUNG: Die 3 Cluster -->
<details class="explainer">
    <summary>📖 Was sind die drei Cluster? · Volatility, Credit, Risk-Off</summary>
    <div class="explainer-content">
        <p>Statt einzelne Indikatoren zu betrachten, bündelt das Tool sie zu <strong>drei Stress-Dimensionen</strong> — sogenannten Clustern. Jeder Cluster misst eine andere Art von Marktstress:</p>

        <p><strong>1. Volatility-Cluster</strong> (aus VIX, VIX/VIX3M-Verhältnis, MOVE)</p>
        <p>Misst, wie hoch die Marktteilnehmer das kurzfristige Risiko einschätzen. Ein hoher Wert bedeutet: Anleger sind nervös, kaufen Schutz (Puts), Optionen werden teurer. Das ist das klassische "Marktangst-Barometer".</p>

        <p><strong>2. Credit-Cluster</strong> (aus HYG/IEF-Verhältnis)</p>
        <p>Misst, ob Anleger Risiko vermeiden und in sichere Staatsanleihen flüchten. Wenn HYG (High-Yield-Bonds, also riskante Unternehmensanleihen) gegenüber IEF (US-Staatsanleihen) abrutscht, ist das ein klassisches "Risk-Off"-Signal aus dem Anleihenmarkt. Credit-Märkte gelten als "smart money" — wenn sie nervös werden, sollten Aktien-Investoren aufmerken.</p>

        <p><strong>3. Risk-Off-Cluster</strong> (aus XLY/XLP-Verhältnis)</p>
        <p>Misst die Sektor-Rotation innerhalb des Aktienmarkts. XLY ist der ETF für zyklische Konsumgüter (Tesla, Amazon — was Leute kaufen wenn's gut läuft), XLP für defensive Konsumgüter (Procter & Gamble, Coca-Cola — was Leute immer kaufen). Wenn defensive Werte besser laufen als zyklische, signalisiert das eine vorsichtige Stimmung im Markt.</p>

        <div class="example">
            <strong>Warum drei Cluster und nicht ein Score?</strong> Weil unterschiedliche Crashs unterschiedliche Signaturen haben. <strong>2008</strong> war primär ein Credit-Crash — der Credit-Cluster schlug Wochen vor dem Vol-Cluster an. <strong>Volmageddon 2018</strong> war reine Vol-Implosion, ohne Credit-Stress. <strong>Covid 2020</strong> war alles gleichzeitig. Die getrennte Anzeige hilft, die <em>Art</em> des Stresses zu verstehen.
        </div>

        <p><strong>Lesehilfe der Balken:</strong> Jeder Cluster wird als Perzentil über die letzten 252 Handelstage angezeigt. Die senkrechte Linie bei 75 markiert die Schwelle, ab der ein Cluster als "aktiv" gilt. Liegt der Wert links davon, ist der Cluster im Normalbereich. Rechts davon = Stress-Signal.</p>
    </div>
</details>

<div class="grid">

    <!-- TABELLE 1: Historische Regime-Statistik -->
    <div class="card">
        <div class="card-title">▌ Historische Regime-Statistik (2008–heute)</div>
        <table>
            <thead><tr><th>Regime</th><th class="num">Anteil</th><th class="num">Tage</th><th class="num">Pre-Crash-Rate</th></tr></thead>
            <tbody>
                <tr><td><span class="dot dot-a"></span>A · RUHIG</td><td class="num">{stats['A_Ruhig']['share']*100:.1f}%</td><td class="num">{stats['A_Ruhig']['n']}</td><td class="num">{stats['A_Ruhig']['crash_rate']*100:.2f}%</td></tr>
                <tr><td><span class="dot dot-b"></span>B · ERHÖHT</td><td class="num">{stats['B_Erhoeht']['share']*100:.1f}%</td><td class="num">{stats['B_Erhoeht']['n']}</td><td class="num">{stats['B_Erhoeht']['crash_rate']*100:.2f}%</td></tr>
                <tr><td><span class="dot dot-c"></span>C · STRESS</td><td class="num">{stats['C_Stress']['share']*100:.1f}%</td><td class="num">{stats['C_Stress']['n']}</td><td class="num">{stats['C_Stress']['crash_rate']*100:.2f}%</td></tr>
            </tbody>
        </table>
        <div style="margin-top:14px;font-size:12px;color:var(--text-muted);line-height:1.6">
            Pre-Crash-Rate = Anteil der Tage, an denen in den folgenden 20 Handelstagen ein SPX-Rückgang ≥10% auftrat. Basisrate über alle Tage: <strong style="color:var(--text-dim)">{base_rate*100:.2f}%</strong>.
        </div>
    </div>

    <!-- TABELLE 2: Tail-Risk -->
    <div class="card">
        <div class="card-title">▌ Tail-Risk pro Regime (Forward-Returns)</div>
        <table>
            <thead><tr><th>Regime</th><th class="num">20T Median</th><th class="num">20T 5%-Worst</th><th class="num">60T 5%-Worst</th></tr></thead>
            <tbody>
                <tr><td><span class="dot dot-a"></span>A · RUHIG</td><td class="num">{stats['A_Ruhig']['median_20']:+.2f}%</td><td class="num">{stats['A_Ruhig']['worst5_20']:+.2f}%</td><td class="num">{stats['A_Ruhig']['worst5_60']:+.2f}%</td></tr>
                <tr><td><span class="dot dot-b"></span>B · ERHÖHT</td><td class="num">{stats['B_Erhoeht']['median_20']:+.2f}%</td><td class="num">{stats['B_Erhoeht']['worst5_20']:+.2f}%</td><td class="num">{stats['B_Erhoeht']['worst5_60']:+.2f}%</td></tr>
                <tr><td><span class="dot dot-c"></span>C · STRESS</td><td class="num">{stats['C_Stress']['median_20']:+.2f}%</td><td class="num">{stats['C_Stress']['worst5_20']:+.2f}%</td><td class="num">{stats['C_Stress']['worst5_60']:+.2f}%</td></tr>
            </tbody>
        </table>
        <div style="margin-top:14px;font-size:12px;color:var(--text-muted);line-height:1.6">
            5%-Worst = 5%-Perzentil aller historischen Forward-Returns aus diesem Regime. Im Stress-Regime sind die negativen Tail-Risiken etwa <strong style="color:var(--text-dim)">2× so groß</strong> wie in ruhigen Phasen.
        </div>
    </div>

</div>

<!-- ERKLÄRUNG: Die zwei Tabellen -->
<details class="explainer">
    <summary>📖 Wie lese ich die Statistik-Tabellen? · Pre-Crash-Rate vs. Tail-Risk</summary>
    <div class="explainer-content">
        <p>Die beiden Tabellen beantworten dieselbe Frage aus zwei Perspektiven: <strong>Wie unterscheidet sich das Risiko in den drei Regimen?</strong></p>

        <p><strong>Tabelle 1: Pre-Crash-Rate</strong></p>
        <p>Sie zählt, in wie viel Prozent der Tage in einem bestimmten Regime ein 10%-Crash innerhalb der folgenden 20 Handelstage tatsächlich eingetreten ist.</p>
        <ul>
            <li>Zustand A: nur in 1,0 % der Tage gab es danach einen Crash → <strong>5× seltener als der historische Durchschnitt</strong></li>
            <li>Zustand B: 4,7 % — etwa <strong>normal</strong></li>
            <li>Zustand C: 11,5 % — <strong>2,4× häufiger</strong> als der Durchschnitt</li>
        </ul>
        <p>Das ist eine <em>binäre</em> Sichtweise: Crash ja oder nein.</p>

        <p><strong>Tabelle 2: Tail-Risk (5%-Worst)</strong></p>
        <p>Diese Tabelle ist subtiler und in der Praxis oft <strong>wichtiger</strong>. Sie zeigt nicht "Crash ja/nein", sondern wie schlimm die schlechtesten Tage in einem Regime im Schnitt waren.</p>
        <p>Das 5%-Worst-Perzentil bedeutet: Wenn du im Regime A 100 Mal zufällig einen Tag herausgreifst und schaust, was der SPX in den nächsten 20 Tagen macht, dann werden die 5 schlechtesten Fälle im Durchschnitt einen Verlust von etwa 5,2 % zeigen. Im Regime C sind es −10,4 %. <strong>Das Tail-Risk verdoppelt sich also etwa.</strong></p>

        <div class="example">
            <strong>Praktischer Nutzen:</strong> Wenn du eine Position von 100.000 € hältst und vor der Frage stehst "soll ich hedgen?", dann ist der Unterschied "im schlimmsten Fall 5.000 € Verlust" (Regime A) vs. "im schlimmsten Fall 10.000 € Verlust" (Regime C) die entscheidende Information. Du brauchst keine Crash-Vorhersage — du brauchst zu wissen, ob das Tail-Risiko aktuell normal oder erhöht ist.
        </div>

        <p><strong>Warum 60T-Worst noch dramatischer ist:</strong> In Regime C liegt das 5%-Worst-60-Tage-Return bei etwa −18,8 % vs. nur −9,1 % in Regime A. Das zeigt: Stress-Regime sind nicht nur kurzfristig gefährlicher, sondern haben auch <em>längere</em> Schmerz-Phasen.</p>
    </div>
</details>

<div class="grid">
    <!-- EINZEL-INDIKATOREN -->
    <div class="card full">
        <div class="card-title">▌ Einzel-Indikatoren · Aktueller Stand</div>
        <div class="ind-list">{ind_rows}</div>
        <div style="margin-top:16px;font-size:12px;color:var(--text-muted);line-height:1.6">
            P-Wert = Perzentil im 1-Jahres-Fenster (252 Handelstage). HYG/IEF und XLY/XLP sind invertiert (niedriger Markt-Wert = hohes Stress-Perzentil). Schwellenmarkierung bei P75.
        </div>
    </div>
</div>

<!-- ERKLÄRUNG: Die 5 Indikatoren -->
<details class="explainer">
    <summary>📖 Was bedeuten die 5 Indikatoren im Detail?</summary>
    <div class="explainer-content">
        <p><strong>VIX</strong> · Der "Angstindex" des Aktienmarkts</p>
        <p>Der VIX (CBOE Volatility Index) misst die erwartete 30-Tage-Volatilität des S&P 500, abgeleitet aus den Preisen von SPX-Optionen. Ein VIX von 15 bedeutet: Der Markt erwartet eine annualisierte Volatilität von 15 % über die nächsten 30 Tage. Ein VIX von 30+ signalisiert deutliche Marktangst. <em>Typische Werte: 12–15 in Ruhephasen, 20–25 in Stress, 40+ in echten Crashs.</em></p>

        <p><strong>VIX/VIX3M</strong> · Die Terminstrukturkurve der Volatilität</p>
        <p>Das Verhältnis zwischen kurzfristigem VIX (30 Tage) und 3-Monats-VIX. Normalerweise liegt das Verhältnis unter 1,0 — der Markt erwartet, dass die nahe Zukunft <em>ruhiger</em> ist als die mittlere Zukunft. Das nennt man "Contango". Wenn das Verhältnis über 1,0 steigt ("Backwardation"), zahlen Anleger einen Aufschlag für <em>kurzfristigen</em> Schutz — ein klassisches Stress-Signal. <em>Dieser Indikator ist oft sensibler als der reine VIX.</em></p>

        <p><strong>MOVE</strong> · Volatilität des US-Anleihenmarkts</p>
        <p>Der MOVE-Index ist sozusagen der "VIX für Treasuries". Er misst die erwartete Volatilität von US-Staatsanleihen. Hohe MOVE-Werte deuten auf Stress im Zinsmarkt hin — und Zinsstress hat eine Tendenz, sich auf den Aktienmarkt zu übertragen, weil Liquidität dann global teurer wird.</p>

        <p><strong>HYG/IEF</strong> · Risiko-Appetit im Anleihenmarkt</p>
        <p>HYG ist der ETF für High-Yield-Unternehmensanleihen ("Ramschanleihen"), IEF für sichere US-Staatsanleihen mit 7–10 Jahren Laufzeit. Wenn das Verhältnis fällt, bedeutet das: Anleger verkaufen riskante Bonds und flüchten in Treasuries. Das ist ein klassisches Risk-Off-Signal. <em>Im Backtest war dies der stärkste einzelne Indikator unseres Modells.</em></p>

        <p><strong>XLY/XLP</strong> · Zyklische vs. defensive Konsumgüter</p>
        <p>XLY = Consumer Discretionary (Tesla, Amazon, Home Depot — Sachen, die man <em>will</em> aber nicht <em>braucht</em>). XLP = Consumer Staples (Procter & Gamble, Coca-Cola, Walmart — Sachen, die man <em>braucht</em>). Wenn defensive Werte besser performen, signalisiert das Vorsicht im Markt — Anleger ziehen sich in defensive Sektoren zurück.</p>

        <div class="example">
            <strong>Was sagen die P-Werte (Perzentile)?</strong> Ein Perzentil von 75 bedeutet: Der aktuelle Wert ist höher als 75 % aller Werte der letzten 252 Handelstage. Das ist die Schwelle, ab der das Tool den Indikator als "aktiv" (= stress-relevant) bewertet. Die <span class="traffic-light tl-green">grünen</span>, <span class="traffic-light tl-yellow">gelben</span> und <span class="traffic-light tl-red">roten</span> Balken zeigen auf einen Blick, welche Indikatoren gerade in welcher Zone sind.
        </div>
    </div>
</details>

<div class="grid">
    <!-- CHART -->
    <div class="card full">
        <div class="card-title">▌ Regime-Historie · 5 Jahre</div>
        <div class="chart-wrapper"><canvas id="mainChart"></canvas></div>
        <div style="margin-top:14px;font-size:12px;color:var(--text-muted);line-height:1.6">
            Gestrichelte Linien markieren tatsächliche Crash-Tiefpunkte (≥10% Drawdown). Stress-Score = Mittelwert der drei Cluster-Perzentile.
        </div>
    </div>
</div>

<!-- ERKLÄRUNG: Der Chart -->
<details class="explainer">
    <summary>📖 Wie lese ich den 5-Jahres-Chart?</summary>
    <div class="explainer-content">
        <p>Der Chart zeigt zwei Linien über die letzten fünf Jahre:</p>
        <ul>
            <li><strong>Blau (linke Achse): SPX-Kurs</strong> — der S&P 500 als Vergleichsbasis.</li>
            <li><strong>Grau (rechte Achse): Stress-Score (0–100)</strong> — der Mittelwert der drei Cluster-Perzentile.</li>
        </ul>

        <p>Die rot gestrichelten vertikalen Linien markieren die <strong>Tiefpunkte tatsächlicher historischer Crashs</strong> (≥10 % SPX-Drawdown). So kannst du visuell überprüfen, wie sich der Stress-Score in der Vergangenheit bei echten Crashs verhalten hat.</p>

        <div class="example">
            <strong>Was du im Chart sehen solltest:</strong>
            <ul>
                <li>Der Stress-Score steigt typischerweise <em>während</em> der Crashs scharf an — was bestätigt, dass das Tool real existierenden Marktstress detektiert.</li>
                <li>Vor den Crashs zeigt der Score oft schon erhöhte Werte, aber <em>nicht zuverlässig</em>. Manchmal mit Vorlauf, manchmal erst gleichzeitig.</li>
                <li>Es gibt auch <strong>Fehlalarme</strong>: Phasen, in denen der Score hoch ist, aber kein Crash folgt (z.B. 2014, 2019). Das ist eine ehrliche Limitation.</li>
            </ul>
        </div>

        <p><strong>Hover-Tooltip:</strong> Wenn du mit der Maus über den Chart fährst, siehst du für jeden Tag die SPX- und Stress-Score-Werte plus die Aufschlüsselung in die drei Cluster.</p>
    </div>
</details>

<!-- HAUPTERKLÄRUNG: Die Methode -->
<details class="explainer" style="margin-top:24px;">
    <summary>📖 Die Methodik im Detail · Wie wurde das Tool gebaut?</summary>
    <div class="explainer-content">
        <p><strong>Das Ziel war ursprünglich anders.</strong> Die Idee war, ein "Crash-Frühwarnsystem" zu bauen — also einen Indikator, der vor einem Markt-Crash warnt. Nach umfangreichen Backtests (8 Indikatoren, Logistic-Regression-Modell, Walk-Forward-Validation) musste ich aber feststellen: <strong>Verlässliche Crash-Vorhersage ist statistisch nicht möglich.</strong> Out-of-Sample lag die AUC nur bei 0.63 — kaum besser als Zufall. Das ist konsistent mit der akademischen Literatur.</p>

        <p><strong>Stattdessen: ein Regime-Klassifizierer.</strong> Das Tool macht <em>keine</em> Vorhersage. Es klassifiziert den aktuellen Zustand und zeigt, welche historischen Statistiken in vergleichbaren Zuständen galten. Das ist epistemisch viel ehrlicher — und praktisch trotzdem nutzbar.</p>

        <p><strong>Datenbasis:</strong> S&P 500 plus 5 Stress-Indikatoren (VIX, VIX/VIX3M, MOVE, HYG/IEF, XLY/XLP) ab 2008. Alle Daten kommen von Yahoo Finance, das Update-Skript läuft täglich/wöchentlich.</p>

        <p><strong>Berechnung:</strong></p>
        <ol style="margin: 8px 0 12px 20px;">
            <li>Für jeden Indikator wird das rollende 252-Tage-Perzentil berechnet (also: "Wie hoch ist der heutige Wert im Vergleich zum letzten Jahr?").</li>
            <li>Die 5 Indikatoren werden zu 3 Clustern gebündelt (Vol, Credit, Risk-Off).</li>
            <li>Ein Cluster gilt als "aktiv", wenn sein höchster Indikator über dem 75. Perzentil liegt.</li>
            <li>Regime-Logik: kein Cluster aktiv → A. Mindestens 1, aber nicht alle → B. Alle 3 aktiv oder einer im 95. Perzentil → C.</li>
        </ol>

        <p><strong>Warum genau diese 5 Indikatoren?</strong> Vor der finalen Auswahl wurden 8 Indikatoren auf ihre Diskriminationskraft getestet (Likelihood-Ratio-Analyse). SKEW, VVIX und RSP/SPY wurden ausgesondert — sie liefern entweder zu schwache Signale (SKEW) oder sind durch andere Indikatoren bereits abgedeckt (VVIX in VIX, RSP/SPY in XLY/XLP).</p>

        <div class="example">
            <strong>Was das Tool NICHT kann:</strong>
            <ul style="margin-top:6px;">
                <li>Es kann nicht sagen, wann genau ein Crash kommt.</li>
                <li>Es kann nicht garantieren, dass ein Crash <em>nicht</em> kommt (auch in Regime A passieren manchmal Crashs).</li>
                <li>Es berücksichtigt keine geopolitischen Schocks, Black-Swan-Ereignisse oder strukturelle Markt-Veränderungen.</li>
                <li>Die historische Marktstruktur ist <em>nicht stabil</em> (Lucas-Kritik). Was 2008 funktionierte, kann 2026 anders sein.</li>
            </ul>
        </div>

        <p><strong>Was es kann:</strong> Es gibt dir eine strukturierte, datenbasierte Antwort auf die Frage "Wo stehen wir gerade?" — und das mit voller Transparenz, ohne Marketing-Hype, ohne Glaskugel-Versprechen.</p>
    </div>
</details>

<div class="footer">
    Datenquellen: Yahoo Finance (^VIX, ^VIX3M, ^MOVE), iShares HYG / IEF, SPDR XLY / XLP · Modell: 5-Indikatoren-Regime-Klassifizierung · Backtest 2008–{datetime.now().year} · Generiert am {datetime.now().strftime('%d.%m.%Y %H:%M')} · <a href="https://www.meine-geldseite.de" style="color:var(--blue);text-decoration:none;">meine-geldseite.de</a>
</div>

</div>

<script>
const chartData = {json.dumps(chart_json)};
const crashes = {json.dumps(crash_markers)};

const ctx = document.getElementById('mainChart').getContext('2d');
const dates = chartData.map(d => d.date);
const spx = chartData.map(d => d.spx);
const score = chartData.map(d => d.score);

new Chart(ctx, {{
    type: 'line',
    data: {{
        labels: dates,
        datasets: [
            {{ label:'SPX', data:spx, borderColor:'#60a5fa', backgroundColor:'rgba(96,165,250,0.05)',
               yAxisID:'y', fill:true, tension:0.1, pointRadius:0, borderWidth:1.5 }},
            {{ label:'Stress-Score (0-100)', data:score, borderColor:'#94a3b8', backgroundColor:'transparent',
               yAxisID:'y1', tension:0.3, pointRadius:0, borderWidth:1.5 }}
        ]
    }},
    options: {{
        responsive:true, maintainAspectRatio:false,
        interaction:{{ mode:'index', intersect:false }},
        plugins:{{
            legend:{{ position:'top', align:'end',
                labels:{{ color:'#94a3b8', font:{{ family:'JetBrains Mono', size:11 }}, usePointStyle:true }} }},
            tooltip:{{ backgroundColor:'#0a0e1a', borderColor:'#1f2a3e', borderWidth:1,
                titleFont:{{ family:'JetBrains Mono' }}, bodyFont:{{ family:'JetBrains Mono' }},
                callbacks:{{ afterBody:function(items){{
                    if(!items.length) return '';
                    const d = chartData[items[0].dataIndex];
                    const labels = {{ 'A_Ruhig':'A · RUHIG', 'B_Erhoeht':'B · ERHÖHT', 'C_Stress':'C · STRESS' }};
                    return ['Regime: ' + (labels[d.regime] || d.regime),
                            'Vol: ' + d.vol.toFixed(0) + ' · Credit: ' + d.credit.toFixed(0) + ' · RiskOff: ' + d.riskoff.toFixed(0)];
                }} }} }}
        }},
        scales:{{
            x:{{ ticks:{{ color:'#64748b', maxTicksLimit:8, font:{{ family:'JetBrains Mono', size:10 }} }},
                grid:{{ color:'rgba(31,42,62,0.4)' }} }},
            y:{{ position:'left', ticks:{{ color:'#60a5fa', font:{{ family:'JetBrains Mono', size:10 }} }},
                grid:{{ color:'rgba(31,42,62,0.4)' }},
                title:{{ display:true, text:'SPX', color:'#60a5fa', font:{{ family:'JetBrains Mono', size:11 }} }} }},
            y1:{{ position:'right', min:0, max:100,
                 ticks:{{ color:'#94a3b8', font:{{ family:'JetBrains Mono', size:10 }} }},
                 grid:{{ display:false }},
                 title:{{ display:true, text:'Stress-Score', color:'#94a3b8', font:{{ family:'JetBrains Mono', size:11 }} }} }}
        }}
    }}
}});
</script>
</body>
</html>
"""

import os
# Speichern als index.html im aktuellen Verzeichnis (GitHub Pages root)
output_dir = os.path.dirname(os.path.abspath(__file__))
out_path = os.path.join(output_dir, "index.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)

# Optional: Roh-Daten als CSV exportieren
df.to_csv(os.path.join(output_dir, "regime_data.csv"))

print(f"\nDashboard erstellt: index.html")
print(f"Aktuelles Regime: {curr['label']} (Zustand {curr['code']})")
print(f"Stand: {latest_date.date()}, SPX: {int(latest['SPX'])}")
