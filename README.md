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
| **📣 Social Orgánico** | Resumen comparativo entre redes + **una pestaña por red** con KPIs contra el periodo anterior, evolución, rendimiento de publicaciones y demografía de audiencia. Solo alcance no pagado. |

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
3. Reinicia la app. El sidebar muestra el origen de cada fuente: **En vivo /
   Caché / CSV importado / Histórico propio / Ejemplo**.

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
├── pages/                     # 6 páginas de detalle
├── src/
│   ├── config.py              # cuentas, objetivos, mapeo de segmentos, tema
│   ├── connectors/            # google_ads, meta_ads, ga4, hubspot, base
│   │                          # + youtube, meta_organico, linkedin, social_base
│   ├── data/                  # loader, metrics, social, sample_data
│   └── ui/                    # theme, components
├── scripts/snapshot_social.py # job diario que acumula el histórico de RRSS
├── data/cache/                # caché de datos (git-ignored)
├── data/import_social/        # exports CSV manuales de RRSS
├── data/historico_social/     # histórico que acumula el job (sí va a git)
├── .streamlit/                # config.toml + secrets.toml.example
└── requirements.txt
```

## Social orgánico — accesos pendientes

La página funciona ya con datos de ejemplo. Cada red se enciende de forma
independiente en cuanto llega su credencial; que falte una no afecta a las demás.

| Red | Qué hace falta | Dónde |
|---|---|---|
| **YouTube** | Habilitar YouTube Data API v3 + YouTube Analytics API en el proyecto de Cloud de GA4, crear un OAuth client de tipo *Desktop* y generar el refresh token con la cuenta **propietaria del canal** (Analytics no admite service account). | [APIs](https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com) · [Credenciales](https://console.cloud.google.com/apis/credentials) · [Channel ID](https://www.youtube.com/account_advanced) |
| **Facebook + Instagram** | ✅ **Conectado (30-jul-2026).** Token de System User «Dashboard-Reversal», sin caducidad. Ver la lista completa de permisos más abajo. | [System Users](https://business.facebook.com/settings/system-users) · [Depurador de tokens](https://developers.facebook.com/tools/debug/accesstoken/) |
| **LinkedIn** | ⏳ **Solicitud enviada el 30-jul-2026, en revisión.** Nada que hacer salvo esperar y responder al correo de verificación. Cuando llegue la aprobación: `python scripts/linkedin_refresh_token.py 77hl0lbpekgnae`. | [App](https://www.linkedin.com/developers/apps) · [Requisitos](https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review) |

Secciones de `secrets.toml`: `[youtube]`, `[social_meta]` y `[linkedin]` (ver el
encabezado de cada conector en `src/connectors/`). Comprueba cualquiera de ellas
con `python scripts/verificar_social.py`.

### Permisos del token de Meta (`[social_meta]`)

Verificados contra la cuenta real. **No son intercambiables**: cada uno abre una
puerta distinta, y sobra con que falte uno para perder toda una parte.

| Permiso | Sin él se pierde |
|---|---|
| `pages_show_list` | listar las Páginas del System User |
| `pages_read_engagement` | **todo Facebook**: es lo que permite canjear el token de System User por uno de Página, y Page Insights exige el de Página |
| `read_insights` | las métricas de la Página |
| `pages_read_user_content` | listar `published_posts` → likes, comentarios y compartidos de Facebook |
| `instagram_basic` | la cuenta de Instagram entera |
| `instagram_manage_insights` | las métricas de Instagram (`reach`, `follower_count`, `views`) |
| `pages_messaging` | solo la métrica de mensajes (opcional) |

⚠️ `read_insights` y `pages_read_user_content` **son cosas distintas**: se puede
leer una métrica de la Página y aun así no poder listar sus publicaciones. Fue
justo lo que pasó en la primera captura real.

⚠️ El token de `[meta_ads]` NO sirve aquí: solo tiene `ads_*`. Comprobado —
con él `/me/accounts` devuelve vacío.

Hay que asignar al System User **la Página y la cuenta de Instagram por
separado**, en dos pestañas distintas del mismo diálogo. Y generar el token con
caducidad **Nunca**: con 60 días el cron deja de funcionar sin avisar.

Comprueba el conjunto con `python scripts/verificar_social.py --red Meta`.

### Estado de LinkedIn (30-jul-2026)

| | |
|---|---|
| App | client id `77hl0lbpekgnae`, Community Management API como **único** producto |
| Página verificada | ✅ contra *Reversal Institute* (`organization_id` 123114024) |
| Redirect URL | ✅ `http://localhost:8765/callback` |
| Formulario de acceso | ✅ enviado — Development Tier, caso de uso *Page analytics* (solo lectura) |
| Pendiente | ⏳ revisión de LinkedIn |

⚠️ **Vigilad el correo de Microsoft Vetting Services** en la dirección de
empresa: LinkedIn verifica la entidad por ahí y, si no se contesta, la solicitud
se queda parada sin más aviso. Puede pedir documentación adicional.

La solicitud va a nombre de **Risetech Solutions, S.L.**, que es la razón social
—*Reversal* y *Reversal — Longevity & Healthspan Institute* son nombres
comerciales—. El resto de datos registrales están en el aviso legal de
reversal.institute. Que la página de LinkedIn se llame distinto que la empresa
es justo lo que hay que explicar en cualquier formulario de este tipo.

**Histórico:** las APIs no llegan igual de atrás (YouTube todo · Facebook ~2 años
· LinkedIn 12 meses · **Instagram solo 30 días de seguidores**). Lo anterior solo
se cubre con exports CSV en `data/import_social/`, y lo que no se capture se
pierde de forma definitiva.

### Job diario de histórico

`scripts/snapshot_social.py` captura cada día lo que dan las APIs y lo acumula en
`data/historico_social/`, que `social_base.resolver` funde **por debajo** de lo
que devuelva la API (la API manda en las fechas que cubre; el histórico rellena
lo anterior). Sin él, la ventana de Instagram se desliza y el pasado desaparece.

```bash
python scripts/snapshot_social.py --dry-run   # ver qué haría, sin escribir
python scripts/snapshot_social.py             # últimos 30 días
python scripts/snapshot_social.py --dias 730  # relleno inicial hacia atrás
```

**El cron ya está instalado** (30-jul-2026), y usa el envoltorio
`scripts/cron_social.sh`, que además de capturar **commitea y sube** el
histórico — sin ese último paso producción se queda congelada mientras el Mac
sigue acumulando:

```
0 4 * * * /Users/misael/Documents/Reversal/Dashboard/scripts/cron_social.sh
```

| | |
|---|---|
| Ver qué hizo anoche | `tail -40 data/cron_social.log` |
| Ejecutarlo a mano | `./scripts/cron_social.sh` |
| Sin subir a producción | `PUSH=0 ./scripts/cron_social.sh` |
| Desactivarlo | `crontab -e` y comentar la línea |

Solo toca `data/historico_social/`: nunca commitea código ni caché, así que
convive con trabajo sin guardar. Si la captura falla no commitea nada; si el
push falla, deja el commit en local y lo dice en el log.

Salta las redes sin credencial sin tocar su histórico, así que se puede arrancar
con una sola red configurada. ⚠️ Streamlit Cloud no ejecuta cron: el histórico
llega a producción porque los CSV se commitean y se hace push.

### Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Los módulos de datos (`social_analisis`, `social_demografia`) no importan
Streamlit a propósito: se prueban con DataFrames sueltos, sin levantar la app.

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
