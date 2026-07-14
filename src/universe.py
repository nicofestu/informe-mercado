"""Definiciones del universo de tickers.

El listado del S&P 500 se baja de un CSV mantenido en GitHub (proyecto
"datasets/s-and-p-500-companies", actualizado regularmente) para no
hardcodear 500 tickers que cambian cada trimestre. Si esa fuente falla, se
intenta Wikipedia, y si también falla, se usa el cache local en
data/sp500_cache.csv (que build_data.py deja escrito la primera vez que
corre con éxito).
"""
from __future__ import annotations

import os

import pandas as pd
import requests

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sp500_cache.csv")

GITHUB_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/"
    "s-and-p-500-companies/master/data/constituents.csv"
)
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; informe-semanal/1.0)"}

# Los 11 sectores GICS via SPDR select sector ETFs.
SECTOR_ETFS = {
    "XLF": "Financieros",
    "XLC": "Comunicaciones",
    "XLY": "Consumo discrecional",
    "XLV": "Salud",
    "XLI": "Industriales",
    "XLB": "Materiales",
    "XLP": "Consumo básico",
    "XLK": "Tecnología",
    "XLU": "Servicios públicos",
    "XLE": "Energía",
    "XLRE": "Inmobiliario",
}

# Mapeo de sector GICS (como viene en el CSV de constituents, en inglés) al
# nombre en español usado en SECTOR_ETFS, para poder agrupar ganadores y
# perdedores por sector de forma consistente con la rotación sectorial.
GICS_SECTOR_TO_NAME = {
    "Information Technology": "Tecnología",
    "Health Care": "Salud",
    "Financials": "Financieros",
    "Consumer Discretionary": "Consumo discrecional",
    "Communication Services": "Comunicaciones",
    "Industrials": "Industriales",
    "Consumer Staples": "Consumo básico",
    "Energy": "Energía",
    "Utilities": "Servicios públicos",
    "Real Estate": "Inmobiliario",
    "Materials": "Materiales",
}

# Clasificación cíclico / defensivo, para el spread de rotación.
CYCLICAL = ["XLF", "XLY", "XLI", "XLB", "XLK", "XLE"]
DEFENSIVE = ["XLV", "XLP", "XLU", "XLRE"]

INDICES = {
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq Composite",
    "^DJI": "Dow Jones Industrial",
    "^RUT": "Russell 2000",
}

MACRO = {
    "GC=F": ("Oro", "price"),
    "CL=F": ("Petróleo WTI", "price"),
    "BTC-USD": ("Bitcoin", "price"),
    "^VIX": ("VIX (volatilidad)", "price"),
    "^TNX": ("Tasa 10 años EE.UU.", "yield"),  # ^TNX viene en % (ej. 4.49)
}

# Par -> (nombre, orientación). "direct" = el par cotiza XXXUSD (sube = USD débil).
# "inverse" = el par cotiza USDXXX (sube = USD fuerte).
FX = {
    "EURUSD=X": ("Euro", "EURUSD", "direct"),
    "GBPUSD=X": ("Libra esterlina", "GBPUSD", "direct"),
    "JPY=X": ("Yen japonés", "USDJPY", "inverse"),
    "CHF=X": ("Franco suizo", "USDCHF", "inverse"),
    "AUDUSD=X": ("Dólar australiano", "AUDUSD", "direct"),
    "CAD=X": ("Dólar canadiense", "USDCAD", "inverse"),
    "CNY=X": ("Yuan chino", "USDCNY", "inverse"),
    "MXN=X": ("Peso mexicano", "USDMXN", "inverse"),
    "BRL=X": ("Real brasileño", "USDBRL", "inverse"),
}

# Ponderadores del índice dólar ponderado por comercio (aprox. DXY).
# Se usan sobre la variación del USD contra cada divisa.
MAJORS_WEIGHTS = {
    "EURUSD=X": 0.576,
    "JPY=X": 0.136,
    "GBPUSD=X": 0.119,
    "CAD=X": 0.091,
    "CHF=X": 0.036,
    # AUD entra con 0.042 en el DXY real; lo incluimos para completar.
    "AUDUSD=X": 0.042,
}

# Spreads de retorno entre ETFs. (largo, corto, etiqueta)
POSITIONING_PROXIES = [
    ("RSP", "SPY", "Equiponderado - Cap-ponderado"),
    ("IWM", "SPY", "Small caps - S&P 500"),
    ("SPHB", "SPLV", "Alta beta - Baja volatilidad"),
    ("HYG", "TLT", "Crédito HY - Treasuries largos"),
]

VOLUME_TICKER = "SPY"

# Buckets del histograma de retornos semanales.
RETURN_BUCKETS = [
    (float("-inf"), -0.05, "< -5%"),
    (-0.05, -0.02, "-5% a -2%"),
    (-0.02, 0.0, "-2% a 0%"),
    (0.0, 0.02, "0% a +2%"),
    (0.02, 0.05, "+2% a +5%"),
    (0.05, float("inf"), "> +5%"),
]


def _normalize_ticker(t: str) -> str:
    """Wikipedia usa BRK.B; Yahoo usa BRK-B."""
    return t.strip().replace(".", "-")


def _from_github() -> pd.DataFrame:
    r = requests.get(GITHUB_CSV_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    df = pd.read_csv(pd.io.common.StringIO(r.text))
    return pd.DataFrame(
        {
            "ticker": df["Symbol"].map(_normalize_ticker),
            "name": df["Security"],
            "sector": df["GICS Sector"],
        }
    )


def _from_wikipedia() -> pd.DataFrame:
    r = requests.get(WIKI_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    tables = pd.read_html(pd.io.common.StringIO(r.text))
    df = tables[0]
    return pd.DataFrame(
        {
            "ticker": df["Symbol"].map(_normalize_ticker),
            "name": df["Security"],
            "sector": df["GICS Sector"],
        }
    )


def load_sp500(use_cache_on_fail: bool = True) -> pd.DataFrame:
    """Devuelve DataFrame con columnas: ticker, name, sector.

    Intenta, en orden: CSV de GitHub -> Wikipedia -> cache local.
    """
    last_exc = None
    for label, fn in (("GitHub", _from_github), ("Wikipedia", _from_wikipedia)):
        try:
            out = fn()
            os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
            out.to_csv(CACHE_PATH, index=False)
            return out
        except Exception as exc:  # noqa: BLE001
            print(f"[universe] Fuente {label} falló ({exc}); probando siguiente...")
            last_exc = exc
    if use_cache_on_fail and os.path.exists(CACHE_PATH):
        print("[universe] Todas las fuentes online fallaron; usando cache local.")
        return pd.read_csv(CACHE_PATH)
    raise RuntimeError(
        "No se pudo obtener la lista del S&P 500 (GitHub y Wikipedia fallaron, "
        "y no hay cache local)."
    ) from last_exc


def all_price_tickers(constituents: pd.DataFrame) -> list[str]:
    """Todos los tickers que hay que bajar en una sola llamada."""
    tickers = list(constituents["ticker"])
    tickers += list(SECTOR_ETFS)
    tickers += list(INDICES)
    tickers += list(MACRO)
    tickers += list(FX)
    for long, short, _ in POSITIONING_PROXIES:
        tickers += [long, short]
    tickers.append(VOLUME_TICKER)
    return sorted(set(tickers))
