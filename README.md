# Markt-Regime-Monitor

Klassifiziert den aktuellen Zustand des US-Aktienmarkts in drei Regime auf Basis von Volatilitäts-, Credit- und Risk-Off-Indikatoren.

**Live-Dashboard:** [thblees.github.io/regime-monitor](https://thblees.github.io/regime-monitor/)

## Was das Tool macht

Statt eine "Crash-Wahrscheinlichkeit" zu prognostizieren (was statistisch nicht funktioniert), beschreibt der Monitor den **aktuellen Marktzustand**:

- **A · RUHIG** — Markt entspannt, Volatilität und Credit-Stress niedrig
- **B · ERHÖHT** — Erste Stress-Signale in 1–2 Clustern
- **C · STRESS** — Multi-Cluster-Aktivität oder extreme Werte

Für jedes Regime werden die historischen Pre-Crash-Raten und Tail-Risiken seit 2008 ausgegeben.

## Datenquellen

Alles über Yahoo Finance, keine API-Keys nötig:

- `^VIX`, `^VIX3M`, `^MOVE` (CBOE / ICE Volatilität)
- `HYG`, `IEF` (iShares Bond-ETFs)
- `XLY`, `XLP` (SPDR Sektor-ETFs)
- `^GSPC` (S&P 500)

## Update-Skript

```bash
pip install yfinance pandas numpy
python update.py
```

Generiert `index.html` und `regime_data.csv` neu. Läuft in unter einer Minute.

## Automatisierung via GitHub Actions

`.github/workflows/update.yml`:

```yaml
name: Update Regime Monitor
on:
  schedule:
    - cron: '0 23 * * SUN'  # Sonntag 23:00 UTC
  workflow_dispatch:
jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install yfinance pandas numpy
      - run: python update.py
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: 'Auto-update regime data'
```

## Methodik

Siehe Ausklapp-Erklärungen im Dashboard. Kurzfassung:

1. Rolling 252-Tage-Perzentile pro Indikator
2. Cluster-Bündelung (Vol / Credit / Risk-Off)
3. Schwellen-basierte Klassifizierung (P75 / P95)
4. Historische Backtest-Statistik 2008–heute

## Lizenz / Disclaimer

Keine Anlageberatung. Modellierungs-Tool zur Beobachtung von Marktphasen. Marktstruktur verändert sich (Lucas-Kritik) — historische Statistiken sind Beschreibungen der Vergangenheit, keine Garantien für die Zukunft.

---

Thomas Bleeß · [meine-geldseite.de](https://www.meine-geldseite.de)

---

# Pairs-Trading-Screener

Zweites Dashboard im selben Repository: findet Aktienpaare, die sich für Pairs Trades (Long/Short) eignen.

**Live-Dashboard:** [thblees.github.io/regime-monitor/pairs.html](https://thblees.github.io/regime-monitor/pairs.html)

## Was der Screener macht

- Universum: ~400 Aktien aus DAX/MDAX, Euro Stoxx 50 + UK/Schweiz, S&P 100 + Sektorergänzungen (`pairs_universe.py`), eingeteilt in 25 Sektoren
- Paare nur innerhalb eines Sektors (~3.300 Paare), Cross-Region-Paare werden in EUR umgerechnet und als **FX** markiert
- Pro Paar: Korrelation der Tagesrenditen (252d), Engle-Granger-Kointegrationstest (504d), Hedge Ratio β, Half-Life, Hurst-Exponent, Beta-Stabilität, Nulldurchgänge, aktueller Spread-Z-Score
- Qualitäts-Score (0–100) × Signal (|z|/2) = Gesamt-Score; Status **SETUP** (|z| ≥ 2), **WATCH** (|z| ≥ 1.5), **EXTREM** (|z| ≥ 4, Strukturbruch prüfen)
- Dashboard mit Filtern (Region, Sektor, Status, Korrelation, p-Wert, Half-Life), sortierbarer Tabelle und Detail-Charts (Z-Score, indexierte Kurse)

## Dateien

| Datei | Zweck |
|---|---|
| `pairs_universe.py` | Aktienuniversum nach Sektoren, Währungs-/Regions-Zuordnung |
| `pairs_screener.py` | Datenabruf, Statistik, erzeugt `pairs_data.json` und `pairs.html` |
| `pairs_template.html` | HTML/JS-Vorlage des Dashboards (Daten werden eingebettet) |
| `.github/workflows/pairs.yml` | Täglicher Lauf Di–Sa 22:30 UTC |

## Manuell ausführen

```bash
pip install yfinance pandas numpy statsmodels scipy
python pairs_screener.py              # Daten via Yahoo Finance, ~2–4 Minuten
python pairs_screener.py --offline    # nur lokaler Cache (cache/prices_cache.csv, cache/fx_cache.csv)
python pairs_screener.py --sectors "Autos,Banken"   # Teilmenge zum Testen
```

Schwellen und Fenster stehen oben in `pairs_screener.py` im `CFG`-Dict. Universum erweitern: Ticker (Yahoo-Format) in `pairs_universe.py` zum passenden Sektor hinzufügen.
