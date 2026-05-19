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
