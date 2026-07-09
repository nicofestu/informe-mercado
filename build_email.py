"""Arma el email a partir de data/latest.json, sin llamar a ninguna API paga.

Genera:
  data/email_body.html   — versión HTML (tablas, para el email)
  data/email_body.txt    — versión texto plano (fallback)
  data/prompt_ready.txt  — el prompt de redacción con el JSON ya pegado,
                            listo para copiar y pegar en un chat de Claude
                            si querés la versión narrada + noticias (gratis,
                            usando tu cuenta de claude.ai en vez de la API).

    python build_email.py
"""
from __future__ import annotations

import json
import os

PLACEHOLDER = "{PEGAR_AQUI_EL_CONTENIDO_DE_latest.json}"


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%" if abs(v) < 10 else f"{sign}{v:.1f}%"


def _color(v: float | None) -> str:
    if v is None:
        return "#666"
    return "#1a7f4e" if v > 0.05 else "#c0392b" if v < -0.05 else "#666"


def _span(v: float | None, text: str | None = None) -> str:
    text = text if text is not None else _fmt_pct(v)
    return f'<span style="color:{_color(v)};font-weight:600">{text}</span>'


def _table(headers: list[str], rows: list[list[str]], align_right_from: int = 1) -> str:
    th = "".join(
        f'<th style="text-align:{"right" if i>=align_right_from else "left"};'
        f'padding:6px 10px;font-size:11px;color:#888;text-transform:uppercase;'
        f'letter-spacing:.04em;border-bottom:1px solid #ddd">{h}</th>'
        for i, h in enumerate(headers)
    )
    trs = ""
    for row in rows:
        tds = "".join(
            f'<td style="text-align:{"right" if i>=align_right_from else "left"};'
            f'padding:6px 10px;border-bottom:1px solid #eee;font-size:13px">{c}</td>'
            for i, c in enumerate(row)
        )
        trs += f"<tr>{tds}</tr>"
    return (
        f'<table style="width:100%;border-collapse:collapse;margin:8px 0 20px" '
        f'cellpadding="0" cellspacing="0"><thead><tr>{th}</tr></thead>'
        f'<tbody>{trs}</tbody></table>'
    )


def _section_title(num: str, title: str) -> str:
    return (
        f'<p style="margin:28px 0 4px;font-size:13px;letter-spacing:.06em;'
        f'text-transform:uppercase;color:#333"><span style="color:#b8860b">{num}</span>'
        f'&nbsp;&nbsp;<b>{title}</b></p>'
    )


def build_html(d: dict) -> str:
    m = d["meta"]
    parts = []

    parts.append(f"""
    <div style="font-family:Georgia,'Times New Roman',serif;max-width:640px;
      margin:0 auto;color:#1a1a1a;line-height:1.5">
      <p style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;
        color:#b8860b;margin:0">Monitor semanal de mercado</p>
      <h1 style="font-size:24px;margin:4px 0 2px">Renta variable EE.UU.</h1>
      <p style="font-size:13px;color:#666;margin:0 0 20px">Semana al {m['week_end']}</p>
    """)

    score = m.get("aggregate_score", 0)
    score_label = (
        "Apetito por riesgo amplio" if score > 40 else
        "Sesgo risk-on" if score > 15 else
        "Equilibrio" if score > -15 else
        "Sesgo defensivo" if score > -40 else "Aversión al riesgo"
    )
    parts.append(f"""
    <table style="width:100%;border-collapse:collapse;margin-bottom:8px">
      <tr>
        <td style="padding:10px 14px;background:#f7f5f0;border:1px solid #e5e0d5">
          <div style="font-size:10px;color:#888;text-transform:uppercase">S&P 500 semana</div>
          <div style="font-size:18px;font-weight:700">{_span(m.get('spx_week_return'))}</div>
        </td>
        <td style="padding:10px 14px;background:#f7f5f0;border:1px solid #e5e0d5">
          <div style="font-size:10px;color:#888;text-transform:uppercase">VIX cierre</div>
          <div style="font-size:18px;font-weight:700">{m.get('vix_close','—')}</div>
        </td>
        <td style="padding:10px 14px;background:#f7f5f0;border:1px solid #e5e0d5">
          <div style="font-size:10px;color:#888;text-transform:uppercase">Balance agregado</div>
          <div style="font-size:18px;font-weight:700;color:{_color(score)}">{score:+d}</div>
          <div style="font-size:10px;color:#888">{score_label}</div>
        </td>
      </tr>
    </table>
    """)

    # 01 Índices
    parts.append(_section_title("01", "Índices"))
    rows = [
        [r["name"], _span(r["week_return"]), f'{r["close"]:,.2f}', r["daily_pattern"]]
        for r in d["indices"]
    ]
    parts.append(_table(["Índice", "Semana", "Cierre", "L→V"], rows))

    # 02 Rotación sectorial
    sr = d["sector_rotation"]
    parts.append(_section_title("02", "Rotación sectorial"))
    parts.append(
        f'<p style="font-size:12px;color:#666;margin:0 0 6px">'
        f'{sr["n_positive"]} de {sr["n_total"]} sectores en positivo · '
        f'cíclicos vs. defensivos {_span(sr["cyclical_minus_defensive"])}</p>'
    )
    rows = [[s["name"], s["etf"], _span(s["week_return"])] for s in sr["sectors"]]
    parts.append(_table(["Sector", "ETF", "Semana"], rows, align_right_from=2))

    # 03 Amplitud
    br = d["breadth"]
    parts.append(_section_title("03", "Amplitud del mercado"))
    rows = [
        ["Suben / Bajan / Planos", f'{br["up"]} / {br["down"]} / {br["flat"]}'],
        ["% positivo", f'{br["pct_positive"]:.0f}%'],
        ["Retorno promedio (mediana)", f'{_span(br["mean_company_return"])} ({_span(br["median_company_return"])})'],
        ["Sobre EMA 50 / EMA 200", f'{br["above_ema50_pct"]:.0f}% / {br["above_ema200_pct"]:.0f}%'],
    ]
    parts.append(_table(["Métrica", "Valor"], rows, align_right_from=1))

    # 04 Ganadores y perdedores
    wl = d["winners_losers"]
    parts.append(_section_title("04", "Ganadores y perdedores (top 10)"))
    rows = []
    for i in range(max(len(wl["winners"]), len(wl["losers"]))):
        w = wl["winners"][i] if i < len(wl["winners"]) else {}
        l = wl["losers"][i] if i < len(wl["losers"]) else {}
        rows.append([
            f'{w.get("ticker","")} {w.get("name","")}', _span(w.get("return")) if w else "",
            f'{l.get("ticker","")} {l.get("name","")}', _span(l.get("return")) if l else "",
        ])
    parts.append(_table(["Suba", "%", "Baja", "%"], rows, align_right_from=1))

    # 05 Divisas / 06 Macro
    fm = d["fx_macro"]
    parts.append(_section_title("05", "Divisas"))
    parts.append(f'<p style="font-size:12px;color:#666;margin:0 0 6px">'
                  f'Índice dólar ponderado: {_span(fm["usd_index_move"])}</p>')
    rows = [[f["name"], f["pair"], f'{f["close"]}', _span(f["week_return"])] for f in fm["fx"]]
    parts.append(_table(["Divisa", "Par", "Cierre", "Semana"], rows))

    parts.append(_section_title("06", "Macro global"))
    rows = []
    for x in fm["macro"]:
        val = f'{x["change_bps"]:+.0f} bps' if x.get("change_bps") is not None else _span(x.get("week_return"))
        rows.append([x["name"], f'{x["close"]:,}', val])
    parts.append(_table(["Activo", "Cierre", "Variación"], rows))

    # 07 Posicionamiento
    pos = d["positioning"]
    parts.append(_section_title("07", "Proxies de posicionamiento"))
    if pos.get("volume_note") is not None:
        parts.append(f'<p style="font-size:12px;color:#666;margin:0 0 6px">'
                      f'Volumen SPY: {pos["volume_note"]:+.0f}% vs. promedio 4 semanas previas</p>')
    rows = [[p["label"], _span(p["spread"])] for p in pos["proxies"]]
    parts.append(_table(["Proxy", "Spread"], rows, align_right_from=1))

    # 08 Calendario económico
    ec = d.get("econ_calendar", {})
    readings = ec.get("last_readings", [])
    upcoming = ec.get("upcoming", [])
    if readings or upcoming:
        parts.append(_section_title("08", "Calendario económico"))
        if readings:
            rows = [[r["label"], r["period"][:7], f'{r["value"]:+g}{r["suffix"]}' if r["value"] > 0 else f'{r["value"]:g}{r["suffix"]}']
                    for r in readings]
            parts.append(_table(["Últimos datos publicados", "Período", "Valor"], rows))
        if upcoming:
            rows = [[u["label"], u["date"]] for u in upcoming]
            parts.append(_table(["Próxima semana", "Fecha"], rows))

    parts.append("""
      <p style="margin-top:24px;padding-top:14px;border-top:1px solid #ddd;
        font-size:11px;color:#999;line-height:1.6">
        Datos de cierre (EOD) vía Yahoo Finance, FRED y BLS · cálculos determinísticos,
        sin intervención de un modelo de lenguaje.<br>
        El "balance agregado" es una heurística propia, no una recomendación de inversión.<br>
        ¿Querés la versión narrada con contexto de noticias? Abrí el archivo adjunto
        <b>prompt_listo_para_pegar.txt</b> y pegalo en un chat de Claude con
        búsqueda web activada.
      </p>
    </div>
    """)

    return "".join(parts)


def build_text(d: dict) -> str:
    """Versión texto plano simple, por si el cliente de mail no muestra HTML."""
    m = d["meta"]
    lines = [
        f"INFORME SEMANAL DE MERCADO — Semana al {m['week_end']}",
        "=" * 50,
        f"S&P 500: {_fmt_pct(m.get('spx_week_return'))} | VIX: {m.get('vix_close')} | "
        f"Balance agregado: {m.get('aggregate_score'):+d}",
        "",
        "Ver el email en HTML para las tablas completas, o abrir el adjunto",
        "prompt_listo_para_pegar.txt para la versión narrada con noticias.",
    ]
    return "\n".join(lines)


def build_ready_prompt() -> str:
    tmpl_path = os.path.join("templates", "prompt_redaccion.md")
    data_path = os.path.join("data", "latest.json")
    tmpl = open(tmpl_path, encoding="utf-8").read()
    data = open(data_path, encoding="utf-8").read()
    return tmpl.replace(PLACEHOLDER, data)


def main() -> None:
    d = json.load(open(os.path.join("data", "latest.json"), encoding="utf-8"))
    os.makedirs("data", exist_ok=True)

    html = build_html(d)
    text = build_text(d)
    prompt = build_ready_prompt()

    with open("data/email_body.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("data/email_body.txt", "w", encoding="utf-8") as f:
        f.write(text)
    with open("data/prompt_ready.txt", "w", encoding="utf-8") as f:
        f.write(prompt)

    print("[build_email] data/email_body.html, .txt y prompt_ready.txt generados.")


if __name__ == "__main__":
    main()
