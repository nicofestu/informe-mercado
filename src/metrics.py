"""Motor de métricas.

Todas las funciones reciben datos ya bajados (DataFrames de precios) y devuelven
estructuras planas listas para serializar a JSON. No hay llamadas de red acá:
eso permite testear con datos sintéticos y mantiene la lógica auditable.

Convención de precios: `prices` es un DataFrame con índice de fechas (diario) y
una columna por ticker (precio de cierre ajustado).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import universe as U


# --------------------------------------------------------------------------- #
# Helpers de ventana
# --------------------------------------------------------------------------- #
def _week_slice(prices: pd.DataFrame, week_end: pd.Timestamp) -> pd.DataFrame:
    """Filas de la semana bursátil que termina en week_end (viernes)."""
    week_start = week_end - pd.Timedelta(days=6)
    return prices.loc[(prices.index >= week_start) & (prices.index <= week_end)]


def _weekly_return(prices: pd.Series, week_end: pd.Timestamp) -> float:
    """Retorno de la semana: cierre viernes vs. cierre del viernes previo."""
    s = prices.dropna()
    s = s.loc[s.index <= week_end]
    if len(s) < 6:
        return float("nan")
    # Último cierre de esta semana vs. último cierre de la semana anterior.
    this_friday = s.loc[s.index <= week_end].iloc[-1]
    prev_week_end = week_end - pd.Timedelta(days=7)
    prev = s.loc[s.index <= prev_week_end]
    if prev.empty:
        return float("nan")
    return this_friday / prev.iloc[-1] - 1.0


# --------------------------------------------------------------------------- #
# Secciones
# --------------------------------------------------------------------------- #
def index_returns(prices: pd.DataFrame, week_end: pd.Timestamp) -> list[dict]:
    out = []
    for tk, name in U.INDICES.items():
        if tk not in prices:
            continue
        wk = _week_slice(prices[tk], week_end).dropna()
        ret = _weekly_return(prices[tk], week_end)
        # Signo día a día (L a V).
        daily = wk.pct_change().dropna()
        pattern = "".join("+" if d > 0.0005 else "-" if d < -0.0005 else "·" for d in daily)
        out.append(
            {
                "ticker": tk,
                "name": name,
                "week_return": round(ret * 100, 2),
                "close": round(float(wk.iloc[-1]), 2) if not wk.empty else None,
                "daily_pattern": pattern,
            }
        )
    return out


def sector_rotation(prices: pd.DataFrame, week_end: pd.Timestamp) -> dict:
    rows = []
    for etf, name in U.SECTOR_ETFS.items():
        if etf not in prices:
            continue
        ret = _weekly_return(prices[etf], week_end)
        rows.append({"etf": etf, "name": name, "week_return": round(ret * 100, 2)})
    rows.sort(key=lambda r: r["week_return"], reverse=True)

    cyc = np.nanmean([_weekly_return(prices[e], week_end) for e in U.CYCLICAL if e in prices])
    dfn = np.nanmean([_weekly_return(prices[e], week_end) for e in U.DEFENSIVE if e in prices])
    positive = sum(1 for r in rows if r["week_return"] > 0)
    return {
        "sectors": rows,
        "n_positive": positive,
        "n_total": len(rows),
        "cyclical_minus_defensive": round((cyc - dfn) * 100, 2),
    }


def breadth(prices: pd.DataFrame, constituents: pd.DataFrame, week_end: pd.Timestamp) -> dict:
    tickers = [t for t in constituents["ticker"] if t in prices.columns]
    rets = {}
    for t in tickers:
        r = _weekly_return(prices[t], week_end)
        if not np.isnan(r):
            rets[t] = r
    vals = np.array(list(rets.values()))
    up = int((vals > 0.0005).sum())
    down = int((vals < -0.0005).sum())
    flat = len(vals) - up - down

    # EMA50 / EMA200 sobre el histórico disponible hasta week_end.
    hist = prices.loc[prices.index <= week_end, list(rets)]
    above_50 = above_200 = 0
    for t in rets:
        s = hist[t].dropna()
        if len(s) < 200:
            continue
        ema50 = s.ewm(span=50).mean().iloc[-1]
        ema200 = s.ewm(span=200).mean().iloc[-1]
        last = s.iloc[-1]
        above_50 += int(last > ema50)
        above_200 += int(last > ema200)

    # Amplitud media diaria: % de valores al alza por rueda durante la semana.
    wk = _week_slice(prices[list(rets)], week_end)
    daily_ret = wk.pct_change().dropna(how="all")
    daily_breadth = (daily_ret > 0).sum(axis=1) / daily_ret.notna().sum(axis=1)
    mean_daily_breadth = round(float(daily_breadth.mean()) * 100, 0)

    n = len(vals)
    return {
        "up": up,
        "down": down,
        "flat": flat,
        "pct_positive": round(up / n * 100, 0) if n else 0,
        "mean_company_return": round(float(vals.mean()) * 100, 2),
        "median_company_return": round(float(np.median(vals)) * 100, 2),
        "mean_daily_breadth": mean_daily_breadth,
        "above_ema50": above_50,
        "above_ema50_pct": round(above_50 / n * 100, 0) if n else 0,
        "above_ema200": above_200,
        "above_ema200_pct": round(above_200 / n * 100, 0) if n else 0,
        "n_total": n,
        "_returns": rets,  # interno, para histograma y ranking
    }


def return_histogram(returns: dict) -> list[dict]:
    vals = np.array(list(returns.values()))
    out = []
    for lo, hi, label in U.RETURN_BUCKETS:
        count = int(((vals >= lo) & (vals < hi)).sum())
        out.append({"bucket": label, "count": count})
    return out


def winners_losers(returns: dict, constituents: pd.DataFrame, n: int = 10) -> dict:
    name_map = dict(zip(constituents["ticker"], constituents["name"]))
    sector_map = dict(zip(constituents["ticker"], constituents["sector"]))
    ordered = sorted(returns.items(), key=lambda kv: kv[1], reverse=True)
    top = [
        {"ticker": t, "name": name_map.get(t, t), "sector": sector_map.get(t, ""),
         "return": round(r * 100, 1)}
        for t, r in ordered[:n]
    ]
    bottom = [
        {"ticker": t, "name": name_map.get(t, t), "sector": sector_map.get(t, ""),
         "return": round(r * 100, 1)}
        for t, r in ordered[-n:][::-1]
    ]
    return {"winners": top, "losers": bottom}


def sector_movers(returns: dict, constituents: pd.DataFrame, n: int = 5) -> dict:
    """Top n ganadores y perdedores DENTRO de cada uno de los 11 sectores.

    A diferencia de `winners_losers` (que da el top/bottom global del S&P
    500), esto agrupa por sector para poder mostrar, sector por sector,
    quién lideró y quién rezagó — útil para el gráfico de barras por sector
    en el informe.
    """
    sector_map = dict(zip(constituents["ticker"], constituents["sector"]))
    name_map = dict(zip(constituents["ticker"], constituents["name"]))
    by_sector: dict[str, list[tuple[str, float]]] = {}
    for t, r in returns.items():
        gics = sector_map.get(t, "")
        sec_name = U.GICS_SECTOR_TO_NAME.get(gics, gics or "Sin sector")
        by_sector.setdefault(sec_name, []).append((t, r))

    out: dict[str, dict] = {}
    for sec_name, items in by_sector.items():
        items.sort(key=lambda kv: kv[1], reverse=True)
        winners = [
            {"ticker": t, "name": name_map.get(t, t), "return": round(r * 100, 1)}
            for t, r in items[:n]
        ]
        losers = [
            {"ticker": t, "name": name_map.get(t, t), "return": round(r * 100, 1)}
            for t, r in items[-n:][::-1]
        ]
        out[sec_name] = {"winners": winners, "losers": losers, "n": len(items)}
    return out


def fx_and_macro(prices: pd.DataFrame, week_end: pd.Timestamp) -> dict:
    fx_rows = []
    usd_moves = []  # variación del USD frente a cada divisa (signo: + = USD sube)
    for tk, (name, pair, orient) in U.FX.items():
        if tk not in prices:
            continue
        wk = _week_slice(prices[tk], week_end).dropna()
        ret = _weekly_return(prices[tk], week_end)
        close = float(wk.iloc[-1]) if not wk.empty else None
        # USD move: si el par es directo (EURUSD), USD sube cuando el par baja.
        usd_move = -ret if orient == "direct" else ret
        fx_rows.append({
            "name": name, "pair": pair,
            "close": round(close, 4) if close else None,
            "week_return": round(ret * 100, 2),
        })
        if tk in U.MAJORS_WEIGHTS:
            usd_moves.append((U.MAJORS_WEIGHTS[tk], usd_move))

    tw = sum(w for w, _ in usd_moves)
    usd_index_move = sum(w * m for w, m in usd_moves) / tw if tw else float("nan")

    macro_rows = []
    for tk, (name, kind) in U.MACRO.items():
        if tk not in prices:
            continue
        wk = _week_slice(prices[tk], week_end).dropna()
        close = float(wk.iloc[-1]) if not wk.empty else None
        if kind == "yield":
            # ^TNX en %: variación en puntos básicos.
            prev = prices[tk].dropna()
            prev = prev.loc[prev.index <= week_end - pd.Timedelta(days=7)]
            change_bps = round((close - float(prev.iloc[-1])) * 100, 0) if not prev.empty else None
            macro_rows.append({"name": name, "close": round(close, 2), "change_bps": change_bps})
        else:
            ret = _weekly_return(prices[tk], week_end)
            macro_rows.append({"name": name, "close": round(close, 2), "week_return": round(ret * 100, 1)})

    return {
        "fx": fx_rows,
        "macro": macro_rows,
        "usd_index_move": round(usd_index_move * 100, 1),
    }


def fixed_income(prices: pd.DataFrame, week_end: pd.Timestamp) -> dict:
    """Curva de treasuries (nivel + variación en bps) y proxies de crédito
    (retorno semanal de ETFs IG/HY/EM), para la sección de renta fija.
    """
    curve = []
    for tk, label in U.TREASURY_CURVE.items():
        if tk not in prices:
            continue
        wk = _week_slice(prices[tk], week_end).dropna()
        close = float(wk.iloc[-1]) if not wk.empty else None
        prev = prices[tk].dropna()
        prev = prev.loc[prev.index <= week_end - pd.Timedelta(days=7)]
        change_bps = round((close - float(prev.iloc[-1])) * 100, 0) if (close is not None and not prev.empty) else None
        curve.append({"label": label, "close": round(close, 2) if close is not None else None, "change_bps": change_bps})

    credit = []
    for tk, label in U.CREDIT_ETFS.items():
        if tk not in prices:
            continue
        ret = _weekly_return(prices[tk], week_end)
        wk = _week_slice(prices[tk], week_end).dropna()
        close = float(wk.iloc[-1]) if not wk.empty else None
        credit.append({
            "label": label,
            "close": round(close, 2) if close is not None else None,
            "week_return": round(ret * 100, 2) if not np.isnan(ret) else None,
        })

    # Pendiente 10a-3m, en puntos básicos, y su variación en la semana (proxy
    # simple de empinamiento/aplanamiento de curva).
    slope_now = slope_prev = None
    if "^TNX" in prices and "^IRX" in prices:
        y10 = prices["^TNX"].dropna()
        y3m = prices["^IRX"].dropna()
        y10_now = y10.loc[y10.index <= week_end]
        y3m_now = y3m.loc[y3m.index <= week_end]
        if not y10_now.empty and not y3m_now.empty:
            slope_now = round((float(y10_now.iloc[-1]) - float(y3m_now.iloc[-1])) * 100, 0)
        prev_end = week_end - pd.Timedelta(days=7)
        y10_prev = y10.loc[y10.index <= prev_end]
        y3m_prev = y3m.loc[y3m.index <= prev_end]
        if not y10_prev.empty and not y3m_prev.empty:
            slope_prev = round((float(y10_prev.iloc[-1]) - float(y3m_prev.iloc[-1])) * 100, 0)

    return {
        "curve": curve,
        "credit": credit,
        "slope_10y_3m_bps": slope_now,
        "slope_change_bps": (round(slope_now - slope_prev, 0) if slope_now is not None and slope_prev is not None else None),
    }


def positioning(prices: pd.DataFrame, week_end: pd.Timestamp) -> dict:
    rows = []
    for long, short, label in U.POSITIONING_PROXIES:
        if long not in prices or short not in prices:
            continue
        rl = _weekly_return(prices[long], week_end)
        rs = _weekly_return(prices[short], week_end)
        rows.append({"label": label, "spread": round((rl - rs) * 100, 2)})

    # Volumen SPY vs. promedio de 4 semanas previas.
    vol_note = None
    return {"proxies": rows, "volume_note": vol_note}


def aggregate_score(sector: dict, breadth_d: dict, macro: dict, positioning_d: dict) -> int:
    """Score propio -100/+100. Suma ponderada de señales normalizadas.

    Es una heurística transparente, no un modelo. Documentá los pesos si lo
    mostrás a clientes.
    """
    signals = []
    # Rotación cíclico-defensivo (cap a +/-3%).
    signals.append(np.clip(sector["cyclical_minus_defensive"] / 3.0, -1, 1))
    # Amplitud: % positivo centrado en 50.
    signals.append(np.clip((breadth_d["pct_positive"] - 50) / 30.0, -1, 1))
    # % sobre EMA200 centrado en 50.
    signals.append(np.clip((breadth_d["above_ema200_pct"] - 50) / 30.0, -1, 1))
    # HY - Treasuries (risk-on si positivo).
    hy = next((p["spread"] for p in positioning_d["proxies"]
               if p["label"].startswith("Crédito")), 0.0)
    signals.append(np.clip(hy / 2.0, -1, 1))
    # Debilidad del dólar como viento de cola (USD baja = risk-on).
    signals.append(np.clip(-macro["usd_index_move"] / 1.0, -1, 1))
    score = float(np.mean(signals)) * 100
    return int(round(score))
