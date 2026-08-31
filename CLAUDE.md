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
  Analytics, Leads - Comercial, Tracking & Atribución, **Social Orgánico**.
- `src/config.py` = fuente única (cuentas, tema, mapeos, helpers).
- `src/connectors/` = google_ads (SDK), meta_ads (Graph REST), ga4 (Data API + SA),
  hubspot (CRM v3/v4 REST). Cada uno: **API real → caché parquet → sample_data**.
- **Social orgánico** = youtube, meta_organico (FB+IG), linkedin. Cascada con un
  nivel MÁS: **API → caché → CSV importado → sample_data** (`social_base.resolver`),
  y por debajo de todos ellos el **histórico propio** que se funde con el que gane.
  Va por `loader.cargar_social()`, NO por `cargar_todo()`, para que las páginas de
  pago no paguen 8 llamadas que no usan.
- `scripts/snapshot_social.py` = job diario que acumula ese histórico en
  `data/historico_social/`. Sin cron corriendo, el histórico de Instagram se
  pierde a razón de un día por día.
- `src/data/` = loader (cache_data), metrics (CPL/ROAS/embudo), social (esquema
  normalizado de RRSS), sample_data.
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
- **SOCIAL: nulo ≠ cero.** Las 4 redes no dan las mismas métricas. Si una red no
  publica una métrica, la casilla va a **NaN**, nunca a 0: un 0 haría que los
  totales agregados salieran bajos y que la comparativa entre redes mintiera. Lo
  declara `config.SOPORTE_METRICA_SOCIAL` y lo IMPONE `data/social.py` (pisa
  cualquier 0 que escriba un conector). En la UI usa `num_o_guion`/`pct_o_guion`,
  **nunca `num()`**, que devuelve "0" ante un nulo y rompería la regla.
- **Instagram NO tiene impresiones.** Meta la retiró el 21-abr-2025 (Graph v22.0)
  y la sustituyó por `views`. Por eso el KPI comparable entre redes es
  *visualizaciones*, no impresiones.
- **Instagram solo da 30 días de seguidores** (y `views` con histórico limitado).
  Lo anterior es irrecuperable por API: solo se cubre con los exports CSV en
  `data/import_social/` o con lo que haya acumulado `snapshot_social.py`. Cuanto
  más tarde se capture, más se pierde.
- **El histórico propio es un SUELO, no un nivel de la cascada.** `data/
  historico_social/` se funde por DEBAJO del nivel que gane, no se consulta solo
  cuando los demás fallan. Si fuese un nivel más, el día que entre el token de
  Meta la API devolvería sus 30 días de Instagram y taparía todo el histórico
  acumulado — justo cuando empieza a valer. La API manda en las fechas que
  cubre; el histórico rellena el resto (`social_base.fusionar`, celda a celda,
  y un nulo nuevo nunca pisa un dato ya capturado).
- **`snapshot_social.py` NO llama a `obtener()`.** Usa las funciones `_api_*`
  directamente: `obtener()` pasa por `resolver`, que ante un fallo cae a datos de
  EJEMPLO, y unos datos inventados escritos en el histórico se volverían
  «reales» para siempre. Si esto se refactoriza, mantén esa propiedad.
- **OOM por caché sin tope.** Cada `@st.cache_data(ttl=…)` del loader se indexa por `(desde, hasta)`: sin `max_entries` la memoria crece con cada cambio de periodo hasta reventar el ~1 GB de Streamlit Cloud (la app cicla arranca→error 498→reinicia). TODAS las cachés de datos llevan `max_entries=config.CACHE_MAX_ENTRIES` (=6). Si añades una caché nueva de datos por periodo, ponle el tope.
- **Caché e histórico se recortan al periodo pedido; la API no.** La caché no
  está indexada por rango de fechas: guarda la última ventana consultada, que
  puede ser más ancha que la de ahora (`social_base._recortar`). Al resultado de
  la API no se le aplica porque se le pidió justo ese rango.
- **LinkedIn Community Management API tiene que ser el ÚNICO producto de la app.**
  Y «único» es literal: LinkedIn deja *Request access* en gris si hay **cualquier
  otro producto concedido O una solicitud pendiente sin resolver** («This product
  cannot be requested because there are currently other provisioned products or
  other pending product requests»). No basta con no tener Marketing Developer
  Platform. Ojo con los productos que la propia app trae de serie: cuentan.
  La app tiene que estar además verificada contra la Company Page, y el acceso
  requiere revisión manual de LinkedIn y organización registrada.
  Comprobado en jul-2026: la primera app se quedó bloqueada por esto y hubo que
  rehacerla desde cero. La actual es la de client id `77hl0lbpekgnae`.
  Señal rápida de que el producto NO está concedido: en *Auth* → *OAuth 2.0
  scopes* pone «No permissions added». Sin producto no hay scopes, y sin scopes
  el OAuth falla siempre.
- **Los errores de OAuth de LinkedIn no dicen la causa.** `invalid_scope_error`
  y `unauthorized_scope_error` («The requested permission scope is not valid»)
  significan casi siempre lo mismo: el producto no está concedido, así que esos
  scopes no existen para la app. Igual que recibir un access token SIN
  refresh_token. Lo traduce `scripts/linkedin_refresh_token.py`.
- **Page Insights de Meta con `period=day`**: el valor cubre las 24 h que TERMINAN
  en `end_time`, y `end_time` cae de madrugada del día siguiente. Usar su fecha
  tal cual desplaza la serie un día. Ver `meta_organico._fecha_de_periodo()`.
- **`ui.tabla` inyecta HTML sin escapar.** Escapa tú los textos que vengan de una
  API (títulos de publicaciones) antes de pasárselos.
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
- **La demografía NO mide lo mismo en cada red.** Instagram cuenta PERSONAS que
  te siguen; YouTube da el % de VISUALIZACIONES por tramo. Poblaciones y
  unidades distintas: `social_demografia` las marca con `unidad` y la UI la
  escribe dentro del bloque. Nunca comparten gráfico.
- **Facebook no tiene demografía ni impresiones por publicación.** Meta retiró
  `page_fans_*` y `post_impressions*`. Lo que sí da y nadie más: `post_clicks`
  y `post_reactions_by_type_total`. Por eso su ranking se ordena por
  interacciones y no por tasa de engagement (`social_analisis.criterio_ranking`).
- **TikTok no da series diarias.** La Display API devuelve el estado ACTUAL de
  la cuenta y las métricas acumuladas de cada vídeo; no existe «visualizaciones
  del día 12». Su serie diaria NO se pide, se CONSTRUYE acumulando una foto al
  día con el job — así que un periodo anterior a la primera captura no tiene
  datos y no hay forma de rellenarlo. Las métricas diarias de verdad y la
  demografía solo las da la Business API, que va por revisión aparte.
- **LinkedIn no publica edad ni género.** Da cargo, función, sector, tamaño de
  empresa y país. Hay un test que lo fija.
- **En la Display API de TikTok el método NO es uniforme: `user/info/` es GET y
  `video/list/` es POST.** Equivocarlo devuelve un 404 en **texto plano**
  («Unsupported path(Janus)»), y al parsearlo como JSON revienta con «Expecting
  value: line 1 column 1», que parece un problema de scopes y no lo es. Por eso
  `tiktok._peticion` rechaza toda respuesta que no venga en `application/json`.
- **TikTok no da altas de seguidores por día**, solo el `follower_count` actual.
  `seguidores_nuevos` está fuera de `SOPORTE_METRICA_SOCIAL` para TikTok: restar
  dos fotos consecutivas del histórico daría un número que la API nunca dijo.
- **El sandbox de TikTok no necesita aprobación.** Es la vía para integrar y
  grabar el vídeo de revisión: se autoriza una cuenta concreta (*Target users*,
  que debe ACEPTAR la invitación desde la app) y la API devuelve datos reales.
  Tiene su **propio client_key y client_secret**, distintos de producción.
- **La paleta está validada para CINCO series, y el margen es estrecho.** El
  peor par (TikTok↔Instagram) queda en ΔE 6,2 bajo protanopia, admisible solo
  porque cada red lleva su propio símbolo de punto. Si se quitan los símbolos,
  la paleta deja de ser válida. TikTok NO lleva su color de marca: su rojo está
  a ΔE 7,0 del de YouTube y, con el rojo ocupado, toda la mitad cálida del
  círculo de tonos es inviable en deuteranopia.
- **Los umbrales de muestra están en `config`** (`MIN_PUBLICACIONES_BOTTOM`,
  `MIN_PUBLICACIONES_FORMATO`), no repartidos: el volumen está creciendo.

## Pendiente (contexto)
- Servir bajo dominio propio `admin.reversal.institute/dashboard-m/` (reverse proxy +
  WebSocket + baseUrlPath). Aparcado a la espera de decisión de infraestructura.
