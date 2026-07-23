# Dashboard de Marketing — Reversal Institute

Dashboard en **Streamlit** que unifica **Google Ads, Meta Ads, Google Analytics 4
y HubSpot** para medir la captación de pago de la certificación de Reversal: leads,
CPL por plataforma, CPL neto, asociación de leads a segmentos, control de inversión
y ROAS.

> Clonado de la arquitectura del dashboard de UVic/WeRise, rebrandeado a Reversal.
> GA4 mide **todo el sitio** `reversal.institute` (por canal), no solo landings.

## Páginas

| Página | Contenido |
|---|---|
| **Resumen Global** (`app.py`) | Inversión, leads, CPL neto, ROAS, matrículas vs objetivo, embudo y tabla por segmento. |
| **🔍 Google Ads** | Inversión, CTR, CPC, conversiones y rendimiento por campaña. |
| **📱 Meta Ads** | Inversión, CPM, CPC y leads reales (vía HubSpot) frente a la atribución de la plataforma. |
| **📈 Google Analytics** | Tráfico de todo el sitio por canal: sesiones, usuarios, vistas, conversiones. |
| **🎯 Leads (HubSpot)** | Asociación lead↔segmento, CPL/coste-matrícula, embudo y leads recientes. |
| **🩺 Tracking & Atribución** | Semáforo de medición, diagnóstico de fugas de atribución y checklist de corrección. |

## Puesta en marcha

```bash
cd /Users/misael/Documents/Reversal/Dashboard
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run Resumen_Total.py
```

Se abre en `http://localhost:8501`. **Sin credenciales funciona ya** con datos de
ejemplo realistas (para validar la estructura y las visualizaciones).

## Conectar datos reales

1. Copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml`.
2. Rellena **solo** las plataformas que quieras conectar (las demás siguen con ejemplo).
3. Reinicia la app. El sidebar muestra el origen de cada fuente: **En vivo / Caché / Ejemplo**.

### Arquitectura de datos (importante)

Los conectores MCP de Claude (Google/Meta/HubSpot) **no** están disponibles dentro
de una app Streamlit desplegada. Por eso el dashboard usa **sus propias APIs**:

- **Google Ads** → SDK `google-ads` (OAuth refresh token).
- **Meta Ads** → Graph API vía `requests` (token de app/usuario del sistema).
- **GA4** → `google-analytics-data` con Service Account (por canal, todo el sitio).
- **HubSpot** → CRM API v3 vía `requests` (Private App token).

Orden de resolución de cada conector: **API → caché local → datos de ejemplo**.
La caché (`data/cache/*.parquet`) puede rellenarla Claude vía MCP para tener datos
reales sin configurar todas las APIs.

## ⚠️ Cuentas por rellenar (placeholders)

Todos los IDs viven en [`src/config.py`](src/config.py) marcados con `# TODO`.
Sustitúyelos por los de Reversal cuando estén disponibles:

- `GOOGLE_ADS_CUSTOMER_ID`, `GOOGLE_ADS_LOGIN_CUSTOMER_ID`
- `META_AD_ACCOUNT_ID`, `META_BUSINESS_ID`, `META_PIXEL_DATASET_ID`
- `GA4_PROPERTY_ID`
- `HUBSPOT_PORTAL_ID`, `HUBSPOT_PIPELINE_UVIC`/etapas, `HUBSPOT_PROP_SEGMENTO`

## Parámetros de negocio

En [`src/config.py`](src/config.py):

- `VALOR_MATRICULA` — **ajústalo al precio real** de la certificación (input clave del ROAS).
- `OBJETIVO_INVERSION_MENSUAL`, `OBJETIVO_MATRICULAS` — objetivos del periodo (TODO).
- `CPL_OBJETIVO`, `TASA_LEAD_A_MATRICULA` — umbrales del semáforo y del forecast.
- `SEGMENTOS` — mapeo campaña (Google/Meta) → segmento de audiencia del ICP.

## Estructura

```
Dashboard/
├── Resumen_Total.py           # Resumen Global (página principal)
├── pages/                     # 5 páginas de detalle
├── src/
│   ├── config.py              # cuentas, objetivos, mapeo de segmentos, tema
│   ├── connectors/            # google_ads, meta_ads, ga4, hubspot, base
│   ├── data/                  # loader, metrics, sample_data
│   └── ui/                    # theme, components
├── data/cache/                # caché de datos (git-ignored)
├── .streamlit/                # config.toml + secrets.toml.example
└── requirements.txt
```

## Despliegue en Streamlit Cloud

| | |
|---|---|
| **Repositorio** | `WeRise-ESP/dashboard-reversal` (privado, rama `main`) |
| **App en producción** | https://dashboard-reversal.streamlit.app |
| **Main file path** | `Resumen_Total.py` |

**Actualizar la app = hacer `git push` a `main`.** Streamlit Cloud redespliega
solo; no hay que hacer nada más.

### Credenciales
`secrets.toml` **no está en el repo** (lo protege `.gitignore`). Viven solo en
**App settings → Secrets** del panel de Streamlit, con el mismo formato que
`.streamlit/secrets.toml.example`. Secciones necesarias: `[hubspot]`,
`[google_ads]`, `[meta_ads]` y `[ga4]` + `[ga4.service_account]` (el JSON de la
service account de GA4 va **en línea**, no como fichero).

### Accesos
- **Administrar la app** (redeploy, secrets, invitados): cualquier miembro de
  WeRise-ESP con acceso al repositorio.
- **Ver el dashboard**: lista de invitados por email en **App settings →
  Sharing**. Esa lista vive en la app, no en el repo — si algún día se recrea la
  app, hay que volver a introducirla.
