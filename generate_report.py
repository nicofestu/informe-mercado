"""Redacta el informe llamando a la API de Anthropic con búsqueda web activada
(necesaria para la sección de Noticias). Se ejecuta después de build_data.py.

Requiere la variable de entorno ANTHROPIC_API_KEY.

    python generate_report.py

Escribe data/report_latest.md (texto del informe) y data/report_latest.html
(versión simple en HTML, para el email).
"""
from __future__ import annotations

import os
import sys

import anthropic

MODEL = "claude-sonnet-5"
MAX_TOKENS = 8000

PLACEHOLDER = "{PEGAR_AQUI_EL_CONTENIDO_DE_latest.json}"


def build_prompt() -> str:
    tmpl_path = os.path.join("templates", "prompt_redaccion.md")
    data_path = os.path.join("data", "latest.json")
    tmpl = open(tmpl_path, encoding="utf-8").read()
    data = open(data_path, encoding="utf-8").read()
    if PLACEHOLDER not in tmpl:
        raise RuntimeError(
            "El template no tiene el placeholder esperado; ¿se editó "
            "templates/prompt_redaccion.md por fuera de lo esperado?"
        )
    return tmpl.replace(PLACEHOLDER, data)


def generate() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Falta la variable de entorno ANTHROPIC_API_KEY.")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_prompt()

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    report = "\n\n".join(text_blocks).strip()
    if not report:
        raise RuntimeError("La respuesta de Claude no trajo texto (revisar tool_use/errores).")
    return report


def main() -> None:
    os.makedirs("data", exist_ok=True)
    try:
        report = generate()
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        # No dejamos que la corrida se caiga en silencio: si algo falla,
        # igual escribimos un archivo para que send_email.py te avise por
        # mail en vez de que la semana pase sin que sepas que se rompió.
        report = (
            "⚠️ No se pudo generar el informe automáticamente.\n\n"
            f"Error: {exc}\n\n"
            "Los datos de mercado (data/latest.json) sí se actualizaron; "
            "podés redactarlo a mano pegando el prompt en claude.ai."
        )
        status = "error"
        print(f"[generate_report] FALLÓ: {exc}", file=sys.stderr)

    with open("data/report_latest.md", "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[generate_report] status={status}  ({len(report)} caracteres)")
    if status == "error":
        # No hacemos sys.exit(1): send_email.py debe correr igual para
        # avisarte del fallo por mail en vez de que la corrida quede muda.
        print("[generate_report] Se guardó un mensaje de error como reporte "
              "para que igual te llegue un aviso por mail.", file=sys.stderr)


if __name__ == "__main__":
    main()
