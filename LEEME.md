# Monitor semanal de mercado — guía de uso

Sistema para replicar el informe semanal del S&P 500: baja datos de mercado,
calcula todas las métricas y las muestra en un dashboard que consultás cuando
querés. La redacción del informe la hace un modelo aparte, con el prompt incluido.

> **Importante:** yo (Claude, en la conversación) no puedo dejar esto
> "corriendo solo". Este paquete es el sistema; vos lo ejecutás. Una vez
> configurado, funciona sin mí.

---

## Qué hay en la carpeta

```
informe/
├── build_data.py            <- corré ESTE para actualizar los datos
├── dashboard.html           <- abrí ESTE para ver los datos
├── requirements.txt
├── fred_api_key.txt         <- (opcional) tu API key de FRED, ver abajo
├── src/
│   ├── universe.py          definiciones (tickers, sectores, FX)
│   ├── fetch.py             descarga con yfinance
│   ├── metrics.py           todos los cálculos
│   └── econ_calendar.py     calendario económico (FRED + BLS + reglas fijas)
├── data/
│   └── latest.json          datos que lee el dashboard
└── templates/
    └── prompt_redaccion.md  el prompt para redactar el informe
```

---

## Instalación (una sola vez)

Necesitás Python 3.10 o más nuevo. Para chequear, abrí una terminal y escribí:

```
python --version
```

Después, parado en la carpeta `informe`, instalá las dependencias:

```
pip install -r requirements.txt
```

---

## Uso semanal — 3 pasos

### 1. Actualizar los datos

```
python build_data.py
```

Tarda 1-2 minutos (baja ~530 tickers). Al terminar deja `data/latest.json`
actualizado. Corrélo el lunes a la mañana, o el domingo a la noche.

### 2. Ver el dashboard

Por seguridad, los navegadores no dejan que una página lea archivos locales
con doble clic. Levantá un servidor mínimo (viene con Python):

```
python -m http.server 8000
```

Y abrí en el navegador: **http://localhost:8000/dashboard.html**

Dejá esa terminal abierta mientras lo mirás. Para cerrarlo, Ctrl+C.

### 3. Generar el texto del informe

**Manual (lo que veníamos haciendo):** abrí `templates/prompt_redaccion.md`,
copiá todo, y al final reemplazá `{PEGAR_AQUI...}` por el contenido de
`data/latest.json`. Pegáselo a Claude (con búsqueda web activada, para la
sección de noticias). Te devuelve el informe redactado en tu estilo.
Revisás, ajustás, y lo mandás.

**Automático:** ver **`AUTOMATIZACION.md`** — configurás una vez y a partir
de ahí te llega solo por mail todos los lunes, sin que corras nada a mano.

---

## Calendario económico (opcional pero recomendado)

El dashboard incluye una sección con datos macro (CPI, PPI, empleo, tasas,
PBI) y las próximas publicaciones de la semana. La parte de "próximas
publicaciones" funciona sin configurar nada. La parte de "últimos datos
publicados" necesita una API key gratuita de FRED (Reserva Federal de
St. Louis):

1. Andá a **https://fredaccount.stlouisfed.org/apikeys**
2. Create Account (gratis) → API Keys → Request API Key. Poné cualquier
   descripción, por ejemplo "informe personal".
3. Te da una clave de 32 caracteres. Copiala.
4. En la carpeta `informe`, creá un archivo de texto llamado
   `fred_api_key.txt` (fijate que el nombre final sea exactamente ese,
   sin ".txt.txt" si Windows esconde la extensión) y pegá ahí la clave,
   sola, sin comillas ni espacios.
5. Volvé a correr `python build_data.py`.

Si no configurás la key, esa parte del dashboard simplemente queda vacía
con un aviso — el resto funciona igual.

**Para ser preciso sobre el calendario:** las fechas de publicación son
oficiales (BLS, Reserva Federal). Lo que **no** incluye es pronóstico de
consenso de mercado (cuánto "espera" el mercado que dé cada dato) — eso es
propiedad de proveedores pagos como Bloomberg o Trading Economics y no hay
fuente gratuita confiable. Si más adelante lo querés, avisame.

---

## Preguntas frecuentes

**¿Los datos son confiables?**
Los precios de cierre de Yahoo son buenos para índices, ETFs, FX y macro.
El único dato flojo es el consenso de EPS para la tabla de sorpresas de
earnings (Yahoo no lo da gratis y por eso esa sección no está incluida). Si
la querés, hace falta una fuente paga (FMP, ~USD 20/mes) — avisame y la sumo.

**¿Puedo hacer que se actualice solo?**
Sí, pero es el paso "B" del plan (GitHub Actions + una web desplegada). Cuando
quieras migrar, el script de datos es el mismo; solo cambia dónde corre.

**¿Puedo mandarle esto a clientes de Puente?**
Los números sí. La parte narrativa la firmás vos: revisá siempre el texto del
modelo antes de mandarlo, sobre todo cualquier frase que atribuya causas
("subió por tal noticia"). Eso el modelo no lo verifica.

**El "balance agregado" ¿de dónde sale?**
Es una heurística nuestra (ver `metrics.py`, función `aggregate_score`).
Combina rotación cíclico/defensivo, amplitud, tendencia (EMA200), spread de
crédito y dólar, normalizado a -100/+100. Es transparente y editable, pero no
es un indicador de consenso: aclaralo si lo mostrás.
