"""Calendario económico.

Dos partes, deliberadamente separadas porque vienen de fuentes distintas:

1. `last_readings()` — últimos datos publicados (CPI, PPI, empleo, tasas...)
   vía la API de FRED (Federal Reserve Bank of St. Louis). Gratis, pero
   requiere una API key personal gratuita: ver LEEME.md. Si no hay key
   configurada, esta sección devuelve una lista vacía sin romper nada más.

2. `upcoming_releases()` — próximas publicaciones de la semana entrante.
   Fechas oficiales (BLS, Fed), no pronóstico de consenso: eso es propiedad
   de proveedores pagos (Bloomberg, Trading Economics) y no hay fuente
   gratuita confiable. Se arma con tres estrategias:
     - CPI, PPI, Employment Situation: se leen en vivo de las páginas de
       calendario del BLS (bls.gov/schedule/news_release/...), que siempre
       muestran la próxima fecha programada.
     - ISM Manufacturing / Services PMI: regla fija y pública (1er y 3er
       día hábil del mes respectivamente). No requiere fetch.
     - FOMC: fechas 2026 verificadas contra federalreserve.gov (se anuncian
       con más de un año de anticipación y prácticamente no cambian).
     - Solicitudes iniciales de desempleo: todos los jueves (DOL), regla fija.

Cualquier fuente que falle se omite en silencio (con un print informativo);
nunca se inventa una fecha o un valor.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta

import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; informe-semanal/1.0)"}
FRED_KEY_PATH = os.path.join(os.path.dirname(__file__), "..", "fred_api_key.txt")
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# --------------------------------------------------------------------------- #
# 1. Últimos datos publicados (FRED)
# --------------------------------------------------------------------------- #
# (series_id, label, unidad FRED, sufijo de formato, multiplicador)
FRED_SERIES = [
    ("CPIAUCSL", "CPI interanual", "pc1", "%", 1),
    ("CPILFESL", "CPI Core interanual", "pc1", "%", 1),
    ("PPIACO", "PPI interanual", "pc1", "%", 1),
    ("PAYEMS", "Nómina no agrícola (var. mensual)", "chg", " mil", 1),
    ("UNRATE", "Tasa de desempleo", "lin", "%", 1),
    ("RSAFS", "Ventas minoristas (m/m)", "pch", "%", 1),
    ("A191RL1Q225SBEA", "PBI real (t/t anualizado)", "lin", "%", 1),
    ("ICSA", "Solicitudes iniciales de desempleo", "lin", " mil", 0.001),
    ("DFF", "Tasa de fondos federales (efectiva)", "lin", "%", 1),
]


def _read_fred_key() -> str | None:
    if not os.path.exists(FRED_KEY_PATH):
        return None
    key = open(FRED_KEY_PATH, encoding="utf-8").read().strip()
    return key or None


def _fetch_fred_series(series_id: str, units: str, api_key: str) -> dict | None:
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "units": units,
        "limit": 1,
    }
    r = requests.get(FRED_BASE, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    obs = r.json().get("observations", [])
    if not obs or obs[0]["value"] in (".", None):
        return None
    return {"date": obs[0]["date"], "value": float(obs[0]["value"])}


def last_readings() -> list[dict]:
    api_key = _read_fred_key()
    if not api_key:
        print("[econ_calendar] No hay fred_api_key.txt; se omite 'últimos datos publicados'.")
        return []
    out = []
    for series_id, label, units, suffix, mult in FRED_SERIES:
        try:
            r = _fetch_fred_series(series_id, units, api_key)
            if r is None:
                continue
            val = r["value"] * mult
            out.append({
                "label": label,
                "period": r["date"],
                "value": round(val, 2),
                "suffix": suffix,
            })
        except Exception as exc:  # noqa: BLE001
            print(f"[econ_calendar] FRED {series_id} falló: {exc}")
    return out


# --------------------------------------------------------------------------- #
# 2. Próximas publicaciones
# --------------------------------------------------------------------------- #
BLS_PAGES = [
    ("Consumer Price Index (CPI)", "https://www.bls.gov/schedule/news_release/cpi.htm"),
    ("Producer Price Index (PPI)", "https://www.bls.gov/schedule/news_release/ppi.htm"),
    ("Employment Situation (Nóminas)", "https://www.bls.gov/schedule/news_release/empsit.htm"),
]

DATE_RE = re.compile(
    r"scheduled to be released on ([A-Z][a-z]+ \d{1,2}, \d{4})"
)

# Fechas de decisión FOMC 2026, verificadas contra federalreserve.gov
# (segundo día de cada reunión de dos días). Actualizar si Anthropic
# entrena una versión nueva de este script para 2027.
FOMC_2026_DECISIONS = [
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29), date(2026, 6, 17),
    date(2026, 7, 29), date(2026, 9, 16), date(2026, 10, 28), date(2026, 12, 9),
]


def _fetch_bls_next_date(url: str) -> date | None:
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    matches = DATE_RE.findall(r.text)
    if not matches:
        return None
    dates = [datetime.strptime(m, "%B %d, %Y").date() for m in matches]
    future = [d for d in dates if d >= date.today()]
    return min(future) if future else None


def _ism_dates(window_start: date, window_end: date) -> list[dict]:
    """1er día hábil del mes = Manufacturing PMI; 3er día hábil = Services PMI."""
    out = []
    months = {(window_start.year, window_start.month), (window_end.year, window_end.month)}
    for year, month in months:
        bdays = pd.bdate_range(start=date(year, month, 1), periods=5)
        first, third = bdays[0].date(), bdays[2].date()
        if window_start <= first <= window_end:
            out.append({"label": "ISM Manufacturing PMI", "date": str(first),
                        "note": "1er día hábil del mes (regla fija)"})
        if window_start <= third <= window_end:
            out.append({"label": "ISM Services PMI", "date": str(third),
                        "note": "3er día hábil del mes (regla fija)"})
    return out


def _jobless_claims_dates(window_start: date, window_end: date) -> list[dict]:
    out = []
    d = window_start
    while d <= window_end:
        if d.weekday() == 3:  # jueves
            out.append({"label": "Solicitudes iniciales de desempleo", "date": str(d),
                        "note": "Semanal, todos los jueves salvo feriado"})
        d += timedelta(days=1)
    return out


def _fomc_dates(window_start: date, window_end: date) -> list[dict]:
    return [
        {"label": "Decisión FOMC (tasa de interés)", "date": str(d), "note": "Fecha oficial"}
        for d in FOMC_2026_DECISIONS if window_start <= d <= window_end
    ]


def upcoming_releases(days_ahead: int = 7) -> list[dict]:
    window_start = date.today()
    window_end = window_start + timedelta(days=days_ahead)
    out = []

    for label, url in BLS_PAGES:
        try:
            d = _fetch_bls_next_date(url)
            if d and window_start <= d <= window_end:
                out.append({"label": label, "date": str(d), "note": "Fecha oficial (BLS)"})
        except Exception as exc:  # noqa: BLE001
            print(f"[econ_calendar] BLS '{label}' falló: {exc}")

    out += _ism_dates(window_start, window_end)
    out += _jobless_claims_dates(window_start, window_end)
    out += _fomc_dates(window_start, window_end)

    out.sort(key=lambda r: r["date"])
    return out
