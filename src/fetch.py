"""Descarga de precios con yfinance. Se ejecuta en la máquina del usuario
(donde Yahoo está accesible). Devuelve un DataFrame de cierres ajustados.
"""
from __future__ import annotations

import time

import pandas as pd
import yfinance as yf

from . import universe as U


def fetch_prices(tickers: list[str], period: str = "400d", retries: int = 3) -> pd.DataFrame:
    """Baja cierres ajustados diarios. Divide en lotes para no saturar."""
    frames = []
    batch_size = 100
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        for attempt in range(retries):
            try:
                data = yf.download(
                    batch, period=period, auto_adjust=True,
                    progress=False, threads=True,
                )
                if isinstance(data.columns, pd.MultiIndex):
                    close = data["Close"]
                else:
                    close = data[["Close"]]
                    close.columns = batch
                frames.append(close)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == retries - 1:
                    print(f"[fetch] lote {i} falló: {exc}")
                else:
                    time.sleep(2 ** attempt)
    if not frames:
        raise RuntimeError("No se pudo bajar ningún dato.")
    prices = pd.concat(frames, axis=1)
    prices = prices.loc[:, ~prices.columns.duplicated()]
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    return prices.sort_index()


def fetch_spy_volume(period: str = "60d") -> pd.Series:
    v = yf.download("SPY", period=period, progress=False)["Volume"]
    v.index = pd.to_datetime(v.index).tz_localize(None)
    return v.sort_index().squeeze()
