# Dashboard de Marketing — Reversal Institute

Contexto para trabajar en este proyecto. Léelo antes de tocar código.

## Qué es
Dashboard **Streamlit multipágina** de marketing de Reversal Institute (certificación
en longevidad/healthspan). Mide del tráfico a la matrícula: Ads + GA4 + HubSpot.

- **Repo:** `WeRise-ESP/dashboard-reversal` (rama `main`)
- **App:** https://dashboard-reversal.streamlit.app
- **Entry point:** `Resumen_Total.py` (¡no `app.py`!)
- **Actualizar = `git push` a `main`** → Streamlit Cloud redespliega solo.

## Arrancar en local
```bash
source .venv/bin/activate        # o crear: python -m venv .venv && pip install -r requirements.txt
streamlit run Resumen_Total.py
```
Necesitas `.streamlit/secrets.toml` (NO está en git — pídelo por el gestor de
contraseñas del equipo). Sin él, la app cae a datos de ejemplo (`sample_data`).

## Arquitectura
- `Resumen_Total.py` = página principal · `pages/` = Google Ads, Meta Ads, Google
  Analytics, Leads - Comercial, Tracking & Atribución.
- `src/config.py` = fuente única (cuentas, tema, mapeos, helpers).
- `src/connectors/` = google_ads (SDK), meta_ads (Graph REST), ga4 (Data API + SA),
  hubspot (CRM v3/v4 REST). Cada uno: **API real → caché parquet → sample_data**.
- `src/data/` = loader (cache_data), metrics (CPL/ROAS/embudo), sample_data.
- `src/ui/` = theme + components.

## 4 fuentes EN VIVO por API
| Fuente | Cuenta |
|---|---|
| HubSpot | portal 147885062 |
| Google Ads | 2692996145 (OAuth reutilizado de UVIC, MCC 4885772142) |
| Meta Ads | act_1252583410186224 (token System User) |
| GA4 | property 542276987 |

Tema de marca: verde `#0E7C52` (`src/config.py` → `TEMA`).

## ⚠️ Trampas NO obvias (esto costó descubrirlo)
- **Matrículas = deals GANADOS** (`es_ganado`, dealstage `closedwon`), NUNCA contactos
  con lifecyclestage=cliente. Cada deal hereda canal+campaña de su contacto asociado.
- **Batches de HubSpot: máximo 100 inputs.** Con más, la API devuelve 400 y el
  `except` deja todo "Sin asignar". Ver `hubspot._lotes()`. Trocea SIEMPRE en ≤100.
- **La especialidad del lead está en la propiedad `profesion`** (168/172 rellenos),
  NO en `perfil_titulacion` (solo 4/172). Mapa en `config.PROFESION_LABEL`.
- **`ip_country` NO es fiable** para el país del lead: en leads de Meta refleja la IP
  del servidor de Meta (da "Francia" para leads españoles). El país fiable es el
  auto-declarado (`pais_de_residencia`/`country`). Para geografía real usa GA4.
- **Motivo de cierre perdido** = propiedad `motivo_de_cierre` ("Motivo de cierre
  perdido del negocio"), NO `closed_lost_reason` (vacía en este portal).
- **ROAS** usa ingresos reales (`amount` de deals ganados), no matrículas × ticket.
- Las campañas de Google/Meta se traen TODAS (activas y pausadas) con su Estado; las
  sin actividad en el periodo entran con métricas a 0.

## Pendiente (contexto)
- Servir bajo dominio propio `admin.reversal.institute/dashboard-m/` (reverse proxy +
  WebSocket + baseUrlPath). Aparcado a la espera de decisión de infraestructura.
