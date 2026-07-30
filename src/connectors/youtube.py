"""
Conector de YouTube orgánico (Data API v3 + YouTube Analytics API v2).

Cascada: API real -> caché -> CSV importado -> datos de ejemplo.

Credenciales esperadas en .streamlit/secrets.toml:
    [youtube]
    client_id     = "..."
    client_secret = "..."
    refresh_token = "..."      # OAuth de la cuenta PROPIETARIA del canal
    channel_id    = "UC..."

⚠️ YouTube Analytics NO acepta service account: exige OAuth de usuario. Por eso
aquí hay refresh_token y no el JSON de service account que usa GA4.

⚠️ IMPRESIONES: no se piden. En YouTube Analytics API v2 no está confirmado que
`impressions` esté disponible para reportes de canal (en Studio sí se ve), así
que `config.SOPORTE_POR_VERIFICAR` lo marca como no soportado y la columna sale
a nulo. Cuando haya acceso al canal real: añade "impressions" a _METRICAS_DIA,
comprueba que la API no devuelve error y mueve YouTube en la config.

Estado: la capa de API está SIN VERIFICAR contra el canal real (no hay
credenciales todavía). Cualquier fallo cae al siguiente nivel de la cascada.
"""
from __future__ import annotations

import pandas as pd

from src import config
from src.connectors.base import ResultadoConector, _leer_secreto
from src.connectors.social_base import resolver
from src.data import sample_data, social

RED = "YouTube"

# Métricas de canal por día. Nombres de la YouTube Analytics API v2.
_METRICAS_DIA = "views,likes,comments,shares,subscribersGained"
# Métricas por vídeo.
_METRICAS_VIDEO = "views,likes,comments,shares"


def obtener(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("youtube")
    return resolver(
        clave="social_youtube_diario",
        fn_api=(lambda: _api_diario(creds, desde, hasta)) if creds else None,
        fn_muestra=lambda: _muestra_diario(desde, hasta),
        normalizar=social.normalizar_diario,
        detalle_api="YouTube Analytics API v2",
        periodo=(desde, hasta),
    )


def obtener_posts(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("youtube")
    return resolver(
        clave="social_youtube_posts",
        fn_api=(lambda: _api_posts(creds, desde, hasta)) if creds else None,
        fn_muestra=lambda: _muestra_posts(desde, hasta),
        normalizar=social.normalizar_posts,
        detalle_api="YouTube Analytics + Data API v3",
        periodo=(desde, hasta),
        claves_historico=("red", "post_id"),
    )


def _muestra_diario(desde, hasta) -> pd.DataFrame:
    df = sample_data.social_diario(desde, hasta)
    return df[df["red"] == RED]


def _muestra_posts(desde, hasta) -> pd.DataFrame:
    df = sample_data.social_posts(desde, hasta)
    return df[df["red"] == RED]


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #

def _servicios(creds: dict):
    """(analytics, data) autenticados con el refresh token del propietario."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    c = Credentials(
        None,
        refresh_token=creds["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
    )
    return (build("youtubeAnalytics", "v2", credentials=c, cache_discovery=False),
            build("youtube", "v3", credentials=c, cache_discovery=False))


def _canal(creds: dict) -> str:
    return creds.get("channel_id") or config.YOUTUBE_CHANNEL_ID


def _api_diario(creds: dict, desde, hasta) -> pd.DataFrame:
    analytics, data = _servicios(creds)
    canal = _canal(creds)
    ids = f"channel=={canal}" if canal else "channel==MINE"

    resp = analytics.reports().query(
        ids=ids, startDate=str(desde), endDate=str(hasta),
        metrics=_METRICAS_DIA, dimensions="day", sort="day",
    ).execute()

    # Las columnas vienen en el orden de columnHeaders, no en el de la petición.
    cols = [c["name"] for c in resp.get("columnHeaders", [])]
    filas = []
    for fila in resp.get("rows", []):
        v = dict(zip(cols, fila))
        filas.append(dict(
            fecha=v.get("day"), red=RED,
            visualizaciones=v.get("views"),
            likes=v.get("likes"),
            comentarios=v.get("comments"),
            compartidos=v.get("shares"),
            seguidores_nuevos=v.get("subscribersGained"),
        ))

    df = pd.DataFrame(filas)
    # Total de suscriptores: es un stock "a día de hoy", no una serie histórica.
    # Se ancla al último día del periodo; `social.totales_por_red` toma el último
    # valor no nulo, así que es el que se muestra como total de la red.
    if not df.empty:
        total = _suscriptores(data, canal)
        if total is not None:
            df.loc[df.index[-1], "seguidores_total"] = total
    return df


def _suscriptores(data, canal: str) -> int | None:
    """subscriberCount actual del canal. None si está oculto o falla."""
    try:
        params = {"part": "statistics"}
        if canal:
            params["id"] = canal
        else:
            params["mine"] = True
        items = data.channels().list(**params).execute().get("items", [])
        if not items:
            return None
        return int(items[0]["statistics"]["subscriberCount"])
    except Exception:  # noqa: BLE001
        return None


def _api_posts(creds: dict, desde, hasta) -> pd.DataFrame:
    analytics, data = _servicios(creds)
    canal = _canal(creds)
    ids = f"channel=={canal}" if canal else "channel==MINE"

    resp = analytics.reports().query(
        ids=ids, startDate=str(desde), endDate=str(hasta),
        metrics=_METRICAS_VIDEO, dimensions="video",
        sort="-views", maxResults=200,
    ).execute()

    cols = [c["name"] for c in resp.get("columnHeaders", [])]
    metricas = {}
    for fila in resp.get("rows", []):
        v = dict(zip(cols, fila))
        vid = v.get("video")
        if vid:
            metricas[vid] = v

    if not metricas:
        return pd.DataFrame()

    meta = _detalles_videos(data, list(metricas))
    filas = []
    for vid, v in metricas.items():
        info = meta.get(vid, {})
        filas.append(dict(
            red=RED, post_id=vid,
            fecha=info.get("fecha"),
            tipo=info.get("tipo", "Vídeo"),
            titulo=info.get("titulo", vid),
            url=f"https://www.youtube.com/watch?v={vid}",
            miniatura=info.get("miniatura", ""),
            visualizaciones=v.get("views"),
            likes=v.get("likes"),
            comentarios=v.get("comments"),
            compartidos=v.get("shares"),
        ))
    return pd.DataFrame(filas)


def _detalles_videos(data, ids: list[str]) -> dict:
    """{video_id: {titulo, fecha, miniatura, tipo}} vía Data API v3.

    La API acepta como máximo 50 ids por llamada, así que se trocea.
    """
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        lote = ids[i:i + 50]
        try:
            resp = data.videos().list(
                part="snippet,contentDetails", id=",".join(lote), maxResults=50,
            ).execute()
        except Exception:  # noqa: BLE001
            continue
        for item in resp.get("items", []):
            sn = item.get("snippet", {})
            dur = item.get("contentDetails", {}).get("duration", "")
            out[item["id"]] = dict(
                titulo=sn.get("title", ""),
                fecha=(sn.get("publishedAt") or "")[:10],
                miniatura=(sn.get("thumbnails", {}).get("medium", {}).get("url", "")),
                tipo=_tipo_por_duracion(dur),
            )
    return out


def _tipo_por_duracion(iso: str) -> str:
    """Short si dura <= 3 min (criterio de YouTube), Vídeo en el resto.

    `iso` es una duración ISO-8601 tipo "PT1M30S". Ante cualquier cosa rara
    devuelve "Vídeo", que es el caso mayoritario.
    """
    if not iso.startswith("PT") or "H" in iso:
        return "Vídeo"
    minutos = segundos = 0
    resto = iso[2:]
    if "M" in resto:
        cab, resto = resto.split("M", 1)
        minutos = int(cab) if cab.isdigit() else 0
    if resto.endswith("S"):
        cab = resto[:-1]
        segundos = int(cab) if cab.isdigit() else 0
    return "Short" if minutos * 60 + segundos <= 180 else "Vídeo"


# Género de la API -> categoría del esquema, alineada con la de Instagram.
_GENERO_YT = {"female": "F", "male": "M", "user_specified": "U", "gender_other": "U"}


def _api_demografia(creds: dict, desde, hasta) -> pd.DataFrame:
    """Demografía de la audiencia de YouTube, en el esquema largo.

    ⚠️ Esto NO es la demografía de tus suscriptores: `viewerPercentage` es el
    porcentaje de VISUALIZACIONES por tramo en el periodo. Otra población y
    otra unidad que la de Instagram, que cuenta personas. `social_demografia`
    lo marca con la unidad `pct_visualizaciones` y la UI lo escribe en el
    bloque.

    Los tramos vienen como «age45-54»; se les quita el prefijo para que
    coincidan con los de Instagram y puedan compartir eje (nunca gráfico).
    """
    analytics, _ = _servicios(creds)
    canal = _canal(creds)
    ids = f"channel=={canal}" if canal else "channel==MINE"
    base = dict(ids=ids, startDate=str(desde), endDate=str(hasta))

    filas = []
    try:
        r = analytics.reports().query(
            **base, metrics="viewerPercentage", dimensions="ageGroup,gender").execute()
        por_edad: dict[str, float] = {}
        for tramo, genero, pct in (fila[:3] for fila in r.get("rows", [])):
            etiqueta = str(tramo).removeprefix("age")
            por_edad[etiqueta] = por_edad.get(etiqueta, 0.0) + float(pct)
            filas.append({"fecha": hasta, "red": RED, "dimension": "genero",
                          "categoria": _GENERO_YT.get(genero, "U"), "valor": pct})
        for etiqueta, pct in por_edad.items():
            filas.append({"fecha": hasta, "red": RED, "dimension": "edad",
                          "categoria": etiqueta, "valor": round(pct, 2)})
    except Exception:  # noqa: BLE001
        pass

    try:
        r = analytics.reports().query(
            **base, metrics="views", dimensions="country").execute()
        for pais, vistas in (fila[:2] for fila in r.get("rows", [])):
            filas.append({"fecha": hasta, "red": RED, "dimension": "pais",
                          "categoria": pais, "valor": vistas})
    except Exception:  # noqa: BLE001
        pass

    return pd.DataFrame(filas)
