"""Orquestador principal. Corré esto en tu máquina:

    python build_data.py

Baja los datos, calcula todas las métricas y escribe data/report_<fecha>.json
más data/latest.json (que usa el dashboard).
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from src import econ_calendar as ECAL, fetch, metrics, universe as U


def _last_friday(prices: pd.DataFrame) -> pd.Timestamp:
    """Último viernes con datos (o el último día hábil disponible)."""
    idx = prices.index
    fridays = idx[idx.weekday == 4]
    return fridays[-1] if len(fridays) else idx[-1]


def _json_safe(obj):
    """Convierte numpy/pandas a tipos nativos para json.dumps."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def build() -> dict:
    print("[1/6] Universo...")
    constituents = U.load_sp500()
    tickers = U.all_price_tickers(constituents)

    print(f"[2/6] Bajando {len(tickers)} tickers (puede tardar 1-2 min)...")
    prices = fetch.fetch_prices(tickers)
    week_end = _last_friday(prices)
    print(f"       Semana al {week_end.date()}")

    print("[3/6] Métricas...")
    idx = metrics.index_returns(prices, week_end)
    sec = metrics.sector_rotation(prices, week_end)
    br = metrics.breadth(prices, constituents, week_end)
    hist = metrics.return_histogram(br["_returns"])
    wl = metrics.winners_losers(br["_returns"], constituents)
    fm = metrics.fx_and_macro(prices, week_end)
    pos = metrics.positioning(prices, week_end)

    print("[4/6] Volumen SPY...")
    try:
        vol = fetch.fetch_spy_volume()
        wk_vol = vol.loc[vol.index > week_end - pd.Timedelta(days=7)].mean()
        prev_4w = vol.loc[
            (vol.index <= week_end - pd.Timedelta(days=7))
            & (vol.index > week_end - pd.Timedelta(days=35))
        ].mean()
        pos["volume_note"] = round((wk_vol / prev_4w - 1) * 100, 0)
    except Exception as exc:  # noqa: BLE001
        print(f"       volumen falló: {exc}")

    score = metrics.aggregate_score(sec, br, fm, pos)

    print("[5/6] Calendario económico...")
    try:
        last_readings = ECAL.last_readings()
    except Exception as exc:  # noqa: BLE001
        print(f"       últimos datos falló: {exc}")
        last_readings = []
    try:
        upcoming = ECAL.upcoming_releases()
    except Exception as exc:  # noqa: BLE001
        print(f"       próximas publicaciones falló: {exc}")
        upcoming = []

    # Quitar campo interno pesado antes de serializar.
    br_public = {k: v for k, v in br.items() if not k.startswith("_")}

    spx = next((r for r in idx if r["ticker"] == "^GSPC"), {})
    report = {
        "meta": {
            "week_end": str(week_end.date()),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "spx_week_return": spx.get("week_return"),
            "vix_close": next((m["close"] for m in fm["macro"] if m["name"].startswith("VIX")), None),
            "aggregate_score": score,
        },
        "indices": idx,
        "sector_rotation": sec,
        "breadth": br_public,
        "histogram": hist,
        "winners_losers": wl,
        "fx_macro": fm,
        "positioning": pos,
        "econ_calendar": {"last_readings": last_readings, "upcoming": upcoming},
    }
    report = _json_safe(report)

    print("[6/6] Escribiendo JSON...")
    os.makedirs("data", exist_ok=True)
    stamp = week_end.date()
    with open(f"data/report_{stamp}.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"       -> data/latest.json  (score {score:+d}, S&P {spx.get('week_return'):+.1f}%)")
    return report


if __name__ == "__main__":
    build()
