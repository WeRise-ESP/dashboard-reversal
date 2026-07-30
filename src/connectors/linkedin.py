"""
Conector de LinkedIn orgánico (Community Management API).

Cascada: API real -> caché -> CSV importado -> datos de ejemplo.

Credenciales esperadas en .streamlit/secrets.toml:
    [linkedin]
    client_id       = "..."
    client_secret   = "..."
    refresh_token   = "..."
    organization_id = "..."     # solo el número, sin "urn:li:organization:"
    version         = "202506"  # opcional, cabecera LinkedIn-Version

⚠️ ACCESO: la Community Management API exige revisión manual de LinkedIn y solo
se concede a organizaciones legales registradas. Además tiene que ser el ÚNICO
producto de la app: si ya hay una app con Marketing Developer Platform (Ads), NO
sirve, hace falta una app nueva y dedicada. El Development Tier basta para leer
las métricas de la propia página.

Mientras no llegue la aprobación, esta red se sirve del CSV importado o de los
datos de ejemplo, sin afectar a las demás.

⚠️ LinkedIn solo devuelve 12 meses de estadísticas de seguidores. El histórico
anterior solo se puede cubrir con los exports XLS de LinkedIn Analytics.

Estado: capa de API SIN VERIFICAR contra la página real (no hay acceso todavía).
"""
from __future__ import annotations

import pandas as pd

from src import config
from src.connectors.base import ResultadoConector, _leer_secreto
from src.connectors.social_base import resolver
from src.data import sample_data, social

RED = "LinkedIn"

_BASE = "https://api.linkedin.com/rest"
_VERSION_POR_DEFECTO = "202506"
_TOPE_POSTS = 100


def obtener(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("linkedin")
    return resolver(
        clave="social_linkedin_diario",
        fn_api=(lambda: _api_diario(creds, desde, hasta)) if creds else None,
        fn_muestra=lambda: _muestra(desde, hasta, "diario"),
        normalizar=social.normalizar_diario,
        detalle_api="LinkedIn Community Management API",
        periodo=(desde, hasta),
    )


def obtener_posts(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("linkedin")
    return resolver(
        clave="social_linkedin_posts",
        fn_api=(lambda: _api_posts(creds, desde, hasta)) if creds else None,
        fn_muestra=lambda: _muestra(desde, hasta, "posts"),
        normalizar=social.normalizar_posts,
        detalle_api="LinkedIn posts + shareStatistics",
        periodo=(desde, hasta),
        claves_historico=("red", "post_id"),
    )


def _muestra(desde, hasta, ambito: str) -> pd.DataFrame:
    df = (sample_data.social_posts(desde, hasta) if ambito == "posts"
          else sample_data.social_diario(desde, hasta))
    return df[df["red"] == RED]


# --------------------------------------------------------------------------- #
# Autenticación y llamadas
# --------------------------------------------------------------------------- #

def _token(creds: dict) -> str:
    """Access token a partir del refresh token.

    Los access tokens de LinkedIn caducan a los 60 días y el refresh token dura
    12 meses, así que se canjea en cada carga (la caché de Streamlit evita que
    esto se haga en cada interacción).
    """
    import requests

    r = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "refresh_token",
            "refresh_token": creds["refresh_token"],
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _cabeceras(creds: dict, token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": creds.get("version", _VERSION_POR_DEFECTO),
    }


def _org_urn(creds: dict) -> str:
    org = creds.get("organization_id") or config.LINKEDIN_ORGANIZATION_ID
    if not org:
        raise RuntimeError("Falta organization_id en [linkedin] o en config")
    return f"urn:li:organization:{org}"


def _get(ruta: str, creds: dict, token: str, params: dict | None = None) -> dict:
    import requests

    r = requests.get(f"{_BASE}/{ruta}", headers=_cabeceras(creds, token),
                     params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def _ms(fecha) -> int:
    """Fecha -> epoch en milisegundos (lo que espera timeIntervals)."""
    return int(pd.Timestamp(fecha).timestamp() * 1000)


def _intervalo_diario(desde, hasta) -> str:
    """Valor de `timeIntervals` con granularidad diaria.

    LinkedIn usa notación Rest.li, no JSON: hay que construir la cadena a mano.
    """
    return (f"(timeRange:(start:{_ms(desde)},end:{_ms(hasta)}),"
            f"timeGranularityType:DAY)")


# --------------------------------------------------------------------------- #
# Métricas
# --------------------------------------------------------------------------- #

def _api_diario(creds: dict, desde, hasta) -> pd.DataFrame:
    token = _token(creds)
    org = _org_urn(creds)
    intervalo = _intervalo_diario(desde, hasta)

    # Engagement e impresiones por día.
    por_fecha: dict = {}
    try:
        datos = _get("organizationalEntityShareStatistics", creds, token, {
            "q": "organizationalEntity", "organizationalEntity": org,
            "timeIntervals": intervalo,
        })
        for e in datos.get("elements", []):
            fecha = _fecha_de_elemento(e)
            s = e.get("totalShareStatistics", {}) or {}
            if fecha is None:
                continue
            por_fecha.setdefault(fecha, {}).update(
                impresiones=s.get("impressionCount"),
                alcance=s.get("uniqueImpressionsCount"),
                visualizaciones=s.get("impressionCount"),
                likes=s.get("likeCount"),
                comentarios=s.get("commentCount"),
                compartidos=s.get("shareCount"),
            )
    except Exception:  # noqa: BLE001
        pass

    # Seguidores ganados por día (orgánicos + de pago).
    try:
        datos = _get("organizationalEntityFollowerStatistics", creds, token, {
            "q": "organizationalEntity", "organizationalEntity": org,
            "timeIntervals": intervalo,
        })
        for e in datos.get("elements", []):
            fecha = _fecha_de_elemento(e)
            g = e.get("followerGains", {}) or {}
            if fecha is None:
                continue
            nuevos = (g.get("organicFollowerGain") or 0) + (g.get("paidFollowerGain") or 0)
            por_fecha.setdefault(fecha, {})["seguidores_nuevos"] = nuevos
    except Exception:  # noqa: BLE001
        pass

    if not por_fecha:
        return pd.DataFrame()

    filas = [{"fecha": f, "red": RED, **vals} for f, vals in sorted(por_fecha.items())]
    df = pd.DataFrame(filas)

    total = _seguidores_total(creds, token, org)
    if total is not None and not df.empty:
        df.loc[df.index[-1], "seguidores_total"] = total
    return df


def _fecha_de_elemento(elemento: dict):
    """Fecha de inicio del intervalo de un elemento de estadísticas."""
    rango = (elemento.get("timeRange") or {})
    inicio = rango.get("start")
    if not inicio:
        return None
    return pd.to_datetime(inicio, unit="ms", utc=True).date()


def _seguidores_total(creds: dict, token: str, org: str) -> int | None:
    """Total de seguidores actual (sin desglose temporal)."""
    try:
        datos = _get("networkSizes/" + org, creds, token,
                     {"edgeType": "COMPANY_FOLLOWED_BY_MEMBER"})
        return int(datos.get("firstDegreeSize")) or None
    except Exception:  # noqa: BLE001
        return None


_TIPO_LI = {"ARTICLE": "Artículo", "VIDEO": "Vídeo", "IMAGE": "Publicación",
            "NONE": "Publicación", "CAROUSEL": "Carrusel"}


def _api_posts(creds: dict, desde, hasta) -> pd.DataFrame:
    token = _token(creds)
    org = _org_urn(creds)

    datos = _get("posts", creds, token, {
        "q": "author", "author": org, "count": 50, "sortBy": "LAST_MODIFIED",
    })

    desde_d = pd.to_datetime(desde).date()
    hasta_d = pd.to_datetime(hasta).date()

    posts = []
    for p in datos.get("elements", []):
        creado = p.get("createdAt") or p.get("firstPublishedAt")
        if not creado:
            continue
        fecha = pd.to_datetime(creado, unit="ms", utc=True).date()
        if not (desde_d <= fecha <= hasta_d):
            continue
        if len(posts) >= _TOPE_POSTS:
            break
        urn = p.get("id") or ""
        contenido = p.get("content") or {}
        crudo = "ARTICLE" if "article" in contenido else (
            "VIDEO" if "media" in contenido else "NONE")
        posts.append(dict(
            red=RED, post_id=urn, fecha=fecha,
            tipo=_TIPO_LI.get(crudo, "Publicación"),
            titulo=(p.get("commentary") or "").strip()[:120] or "(sin texto)",
            url=f"https://www.linkedin.com/feed/update/{urn}" if urn else "",
            miniatura="",
        ))

    if not posts:
        return pd.DataFrame()

    stats = _stats_por_post(creds, token, org, [p["post_id"] for p in posts])
    for p in posts:
        s = stats.get(p["post_id"], {})
        p.update(
            impresiones=s.get("impressionCount"),
            visualizaciones=s.get("impressionCount"),
            likes=s.get("likeCount"),
            comentarios=s.get("commentCount"),
            compartidos=s.get("shareCount"),
        )
    return pd.DataFrame(posts)


def _stats_por_post(creds: dict, token: str, org: str,
                    urns: list[str]) -> dict[str, dict]:
    """{urn: totalShareStatistics} en lotes de 20 (límite del parámetro `shares`)."""
    out: dict[str, dict] = {}
    for i in range(0, len(urns), 20):
        lote = [u for u in urns[i:i + 20] if u]
        if not lote:
            continue
        params = {"q": "organizationalEntity", "organizationalEntity": org}
        for j, urn in enumerate(lote):
            params[f"shares[{j}]"] = urn
        try:
            datos = _get("organizationalEntityShareStatistics", creds, token, params)
        except Exception:  # noqa: BLE001
            continue
        for e in datos.get("elements", []):
            urn = e.get("share") or e.get("ugcPost")
            if urn:
                out[urn] = e.get("totalShareStatistics", {}) or {}
    return out
