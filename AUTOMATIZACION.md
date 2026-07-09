# Automatización — informe semanal por email (100% gratis)

Esta versión es completamente gratuita: sin API paga, sin tarjeta de
crédito. El mail que te llega trae los datos en tablas (como el dashboard,
pero en tu bandeja de entrada) y un archivo adjunto listo para pegar en un
chat de Claude si un lunes puntual querés la versión narrada con noticias.

**Tiempo estimado: 15-20 minutos, una sola vez.**

---

## Qué vas a necesitar

1. Una cuenta de **GitHub** (gratis) — es donde vive el código y donde corre
   el robot que lo ejecuta cada semana, gratis, sin límite práctico para
   este uso.
2. Una **contraseña de aplicación de Gmail** (gratis, 2 minutos).

Eso es todo. No hace falta ninguna API paga.

---

## Paso 1 — Crear el repositorio en GitHub

1. Andá a **https://github.com** y creá una cuenta si no tenés (botón "Sign up").
2. Arriba a la derecha, **+** → **New repository**.
3. Nombre: `informe-mercado` (o el que quieras). Marcá **Private**.
4. NO tildes "Add a README".
5. Create repository.

## Paso 2 — Subir tus archivos

No hace falta instalar git ni usar la terminal — se sube arrastrando desde
la web.

1. En la página vacía del repositorio, hacé clic en
   **"uploading an existing file"**.
2. Abrí, en el Explorador de Windows, la carpeta `informe` que ya tenés en
   tu máquina.
3. Seleccioná **todo el contenido de adentro** de la carpeta (`src`, `data`,
   `templates`, `.github`, los archivos `.py` sueltos, `dashboard.html`,
   `requirements.txt`, `LEEME.md`) y arrastralo a la ventana del navegador.

   **Importante:** arrastrá el *contenido* de la carpeta `informe`, no la
   carpeta en sí — si no, todo queda un nivel más adentro de lo que espera
   el workflow.

   La carpeta `.github` a veces Windows no la muestra fácil por el punto
   inicial. Si no aparece al arrastrar, activá "mostrar archivos ocultos"
   en el Explorador, o subila aparte con "Add file → Upload files"
   navegando manualmente a `.github/workflows/weekly_report.yml`.

4. Abajo, **Commit changes** (botón verde).
5. Confirmá que en la vista del repo aparezcan `src`, `data`, `templates`,
   `.github` y los `.py` sueltos en la raíz — no adentro de una carpeta
   `informe/` extra.

## Paso 3 — Contraseña de aplicación de Gmail

1. Necesitás la **verificación en 2 pasos** activada en tu cuenta de
   Google. Si no la tenés: **https://myaccount.google.com/security** →
   "Verificación en 2 pasos" → activarla.
2. Con eso activo, andá a **https://myaccount.google.com/apppasswords**
3. Nombre: "informe semanal" (o cualquiera). Generar.
4. Te da una contraseña de 16 caracteres. Copiala tal cual, sin espacios.

## Paso 4 — Cargar los secrets en GitHub

Los secrets son variables que el script puede usar pero que nadie puede ver.

1. En tu repositorio: **Settings** → **Secrets and variables** → **Actions**.
2. **New repository secret**, tres en total:

| Nombre exacto | Valor |
|---|---|
| `GMAIL_ADDRESS` | tu dirección de Gmail |
| `GMAIL_APP_PASSWORD` | la del Paso 3 |
| `RECIPIENT_EMAIL` | a dónde querés que llegue (puede ser la misma) |

Opcional, si ya sacaste la key de FRED para el calendario económico:

| Nombre exacto | Valor |
|---|---|
| `FRED_API_KEY` | tu key de FRED (también gratis) |

El nombre tiene que ser exactamente ese (mayúsculas y guiones bajos
incluidos).

## Paso 5 — Habilitar permisos de escritura

Esto es necesario para que el robot pueda guardar los datos actualizados en
el repositorio cada semana (así el dashboard siempre refleja la última
corrida si después lo hosteás).

1. **Settings** → **Actions** → **General**.
2. Abajo, en "Workflow permissions", elegí **"Read and write permissions"**.
3. Save.

## Paso 6 — Probarlo manualmente

1. Pestaña **Actions** de tu repositorio.
2. Si pregunta si querés habilitar los workflows, decí que sí.
3. A la izquierda, **"Informe semanal de mercado"**.
4. Botón **"Run workflow"** → confirmá.
5. Hacé clic en la corrida para ver el progreso paso por paso. Tarda 2-4
   minutos. Si todo salió bien, te llega el mail — revisá spam la primera
   vez.

---

## Listo

A partir de acá corre solo, todos los lunes a las 8am hora Argentina. El
mail trae los números en tablas. Si un lunes puntual querés la versión con
análisis narrado y noticias:

1. Abrí el adjunto **`prompt_listo_para_pegar.txt`** del mail.
2. Copiá todo el contenido.
3. Pegalo en una conversación de Claude con **búsqueda web activada**.
4. Te devuelve el informe completo, igual que veníamos probando en el chat.

Cero configuración adicional, cero costo — usás tu cuenta de Claude normal.

---

## Si más adelante querés que la narración también llegue sola

Es un paso más, no gratis (la API de Anthropic se cobra por uso, algo así
como USD 0.10-0.50 por informe semanal): conseguís una API key en
**console.anthropic.com**, la agregás como secret `ANTHROPIC_API_KEY`, y la
próxima corrida del workflow automáticamente empieza a mandarte la versión
narrada con noticias en el cuerpo del mail — no hay que tocar ningún otro
archivo, el workflow ya está preparado para detectar el secret y usarlo si
existe.

---

## Errores comunes

- **"pip install" falla en el log**: revisá que `requirements.txt` haya
  quedado en la raíz del repo (no adentro de una subcarpeta).
- **El mail nunca llega pero el workflow dice "success"**: revisá spam, y
  que `GMAIL_APP_PASSWORD` no tenga espacios pegados al copiarla.
- **Falla el paso "Guardar datos actualizados" (git push)**: repasá el
  Paso 5 (permisos de escritura).
- **El calendario económico llega vacío en "últimos datos publicados"**:
  falta el secret `FRED_API_KEY` — es opcional, el resto del mail funciona
  igual sin él.
