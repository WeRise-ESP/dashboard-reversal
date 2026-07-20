"""
Conector de Google Analytics 4 (Data API v1) — analítica de marketing.

Analítica de TODO el sitio reversal.institute con métricas de marketing
(adquisición, engagement y conversión), por canal, página, dispositivo y
tipo de usuario (nuevo/recurrente).

Orden: API real -> caché -> datos de ejemplo.

Credenciales en .streamlit/secrets.toml [ga4] (property_id + service account).
"""
from __future__ import annotations

import pandas as pd

from src import config
from src.connectors.base import (
    ResultadoConector,
    _leer_secreto,
    guardar_cache,
    leer_cache,
)
from src.data import sample_data

# Métricas de la serie principal (fecha × canal). Todas ADITIVAS -> los ratios
# (engagement, duración, conv. rate) se recalculan luego sobre los totales.
_MET_MAIN = {
    "sessions": "sesiones",
    "totalUsers": "usuarios",
    "newUsers": "usuarios_nuevos",
    "engagedSessions": "sesiones_activas",
    "screenPageViews": "vistas",
    "userEngagementDuration": "tiempo_interaccion",
    "conversions": "conversiones",
}


def _cliente(creds: dict):
    from google.analytics.data_v1beta import BetaAnalyticsDataClient  # type: ignore
    from google.oauth2 import service_account  # type: ignore

    if creds.get("service_account_file"):
        cred = service_account.Credentials.from_service_account_file(
            creds["service_account_file"])
    else:
        cred = service_account.Credentials.from_service_account_info(
            dict(creds["service_account"]))
    return BetaAnalyticsDataClient(credentials=cred)


def _run(client, prop, dims, mets, desde, hasta, limit=None, order=None):
    from google.analytics.data_v1beta.types import (  # type: ignore
        DateRange, Dimension, Metric, OrderBy, RunReportRequest,
    )
    req = RunReportRequest(
        property=prop,
        dimensions=[Dimension(name=d) for d in dims],
        metrics=[Metric(name=m) for m in mets],
        date_ranges=[DateRange(start_date=str(desde), end_date=str(hasta))],
    )
    if limit:
        req.limit = limit
    if order:
        req.order_bys = [OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order), desc=True)]
    return client.run_report(req)


# --------------------------------------------------------------------------- #
# Serie principal: fecha × canal (para el loader / caché)
# --------------------------------------------------------------------------- #
def obtener(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("ga4")
    if creds and (creds.get("service_account") or creds.get("service_account_file")):
        try:
            df = _consultar_api(creds, desde, hasta)
            if df is not None and not df.empty:
                guardar_cache(df, "ga4")
                return ResultadoConector(df, "api", "GA4 Data API")
        except Exception as e:  # noqa: BLE001
            cache = leer_cache("ga4")
            if cache is not None:
                return ResultadoConector(cache, "cache", f"API falló ({e}); uso caché")

    cache = leer_cache("ga4")
    if cache is not None and not cache.empty:
        return ResultadoConector(cache, "cache", "Caché local")
    return ResultadoConector(sample_data.ga4_diario(desde, hasta), "sample", "Datos de ejemplo")


def _consultar_api(creds: dict, desde, hasta) -> pd.DataFrame:
    client = _cliente(creds)
    prop = creds.get("property_id", config.GA4_PROPERTY_ID)
    resp = _run(client, prop, ["date", "sessionDefaultChannelGroup"],
                list(_MET_MAIN.keys()), desde, hasta)
    filas = []
    for row in resp.rows:
        d = row.dimension_values
        m = row.metric_values
        fila = dict(
            fecha=pd.to_datetime(d[0].value).date(),
            canal=d[1].value or "(sin canal)",
        )
        for i, col in enumerate(_MET_MAIN.values()):
            fila[col] = float(m[i].value or 0)
        filas.append(fila)
    df = pd.DataFrame(filas)
    if not df.empty:
        for col in _MET_MAIN.values():
            df[col] = df[col].astype(int) if col != "tiempo_interaccion" else df[col]
    return df


# --------------------------------------------------------------------------- #
# Desgloses extra (KPIs del periodo, páginas, dispositivo, nuevos/recurrentes)
# --------------------------------------------------------------------------- #
def obtener_extra(desde, hasta) -> dict:
    """Devuelve KPIs del periodo y desgloses. Si la API falla, cae a ejemplo.

    Cada desglose se calcula de forma independiente (`_safe`): si uno falla
    (p. ej. una dimensión concreta) el resto sigue disponible en vez de perderse
    todo el bloque."""
    creds = _leer_secreto("ga4")
    if creds and (creds.get("service_account") or creds.get("service_account_file")):
        try:
            client = _cliente(creds)
            prop = creds.get("property_id", config.GA4_PROPERTY_ID)
            return {
                "origen": "api",
                "totales": _totales(client, prop, desde, hasta),
                "paginas": _paginas(client, prop, desde, hasta),
                "dispositivo": _dispositivo(client, prop, desde, hasta),
                "nuevos": _nuevos(client, prop, desde, hasta),
                # Geográficos: cada uno degrada a vacío (tarjeta "sin datos") si falla,
                # sin tirar todo el bloque a datos de ejemplo.
                "paises": _safe(_paises, client, prop, desde, hasta),
                "regiones": _safe(_regiones, client, prop, desde, hasta),
                "ciudades": _safe(_ciudades, client, prop, desde, hasta),
            }
        except Exception:  # noqa: BLE001
            pass
    return sample_data.ga4_extra(desde, hasta)


def _safe(fn, client, prop, desde, hasta):
    """Ejecuta un desglose geográfico; si falla, devuelve DataFrame vacío."""
    try:
        return fn(client, prop, desde, hasta)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def _totales(client, prop, desde, hasta) -> dict:
    mets = ["sessions", "totalUsers", "newUsers", "engagedSessions",
            "engagementRate", "averageSessionDuration",
            "screenPageViewsPerSession", "conversions"]
    r = _run(client, prop, [], mets, desde, hasta)
    v = {m: float(r.rows[0].metric_values[i].value or 0) for i, m in enumerate(mets)}
    ses = v["sessions"] or 1
    return dict(
        sesiones=int(v["sessions"]),
        usuarios=int(v["totalUsers"]),
        usuarios_nuevos=int(v["newUsers"]),
        pct_nuevos=v["newUsers"] / (v["totalUsers"] or 1),
        engagement_rate=v["engagementRate"],
        duracion_media=v["averageSessionDuration"],
        paginas_sesion=v["screenPageViewsPerSession"],
        conversiones=int(v["conversions"]),
        tasa_conversion=v["conversions"] / ses,
    )


def _paginas(client, prop, desde, hasta) -> pd.DataFrame:
    r = _run(client, prop, ["landingPage"],
             ["sessions", "totalUsers", "engagementRate", "conversions"],
             desde, hasta, limit=8, order="sessions")
    filas = []
    for row in r.rows:
        pag = row.dimension_values[0].value or "(sin definir)"
        m = row.metric_values
        filas.append(dict(
            pagina=pag,
            sesiones=int(m[0].value or 0),
            usuarios=int(m[1].value or 0),
            engagement_rate=float(m[2].value or 0),
            conversiones=int(float(m[3].value or 0)),
        ))
    return pd.DataFrame(filas)


def _dispositivo(client, prop, desde, hasta) -> pd.DataFrame:
    r = _run(client, prop, ["deviceCategory"],
             ["sessions", "totalUsers", "conversions"], desde, hasta, order="sessions")
    trad = {"mobile": "Móvil", "desktop": "Escritorio", "tablet": "Tablet"}
    filas = []
    for row in r.rows:
        dev = row.dimension_values[0].value
        m = row.metric_values
        filas.append(dict(
            dispositivo=trad.get(dev, dev or "Otro"),
            sesiones=int(m[0].value or 0),
            usuarios=int(m[1].value or 0),
            conversiones=int(float(m[2].value or 0)),
        ))
    return pd.DataFrame(filas)


def _paises(client, prop, desde, hasta) -> pd.DataFrame:
    """Sesiones y usuarios por país (visitas del sitio, top 8)."""
    r = _run(client, prop, ["country"],
             ["sessions", "totalUsers"], desde, hasta, limit=15, order="sessions")
    filas = []
    for row in r.rows:
        filas.append(dict(
            pais=row.dimension_values[0].value or "(no definido)",
            sesiones=int(row.metric_values[0].value or 0),
            usuarios=int(row.metric_values[1].value or 0),
        ))
    return pd.DataFrame(filas)


def _regiones(client, prop, desde, hasta) -> pd.DataFrame:
    """Sesiones y usuarios por región/comunidad (top 8)."""
    r = _run(client, prop, ["region"],
             ["sessions", "totalUsers"], desde, hasta, limit=15, order="sessions")
    filas = []
    for row in r.rows:
        filas.append(dict(
            region=row.dimension_values[0].value or "(no definido)",
            sesiones=int(row.metric_values[0].value or 0),
            usuarios=int(row.metric_values[1].value or 0),
        ))
    return pd.DataFrame(filas)


def _ciudades(client, prop, desde, hasta) -> pd.DataFrame:
    """Sesiones y usuarios por ciudad (top 8)."""
    r = _run(client, prop, ["city"],
             ["sessions", "totalUsers"], desde, hasta, limit=15, order="sessions")
    filas = []
    for row in r.rows:
        filas.append(dict(
            ciudad=row.dimension_values[0].value or "(no definido)",
            sesiones=int(row.metric_values[0].value or 0),
            usuarios=int(row.metric_values[1].value or 0),
        ))
    return pd.DataFrame(filas)


def _nuevos(client, prop, desde, hasta) -> pd.DataFrame:
    r = _run(client, prop, ["newVsReturning"], ["sessions", "totalUsers"], desde, hasta)
    trad = {"new": "Nuevos", "returning": "Recurrentes"}
    acc: dict = {}
    for row in r.rows:
        t = trad.get(row.dimension_values[0].value, "Sin determinar")
        m = row.metric_values
        a = acc.setdefault(t, {"sesiones": 0, "usuarios": 0})
        a["sesiones"] += int(m[0].value or 0)
        a["usuarios"] += int(m[1].value or 0)
    return pd.DataFrame([{"tipo": k, **v} for k, v in acc.items()])
