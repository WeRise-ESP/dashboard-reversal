"""
Conector de Facebook e Instagram ORGÁNICO (Graph API).

Cascada por red: API real -> caché -> CSV importado -> datos de ejemplo.
Facebook e Instagram se resuelven POR SEPARADO (cachés y semáforos propios):
si Instagram no está vinculado a la Página, Facebook sigue funcionando.

Credenciales esperadas en .streamlit/secrets.toml:
    [social_meta]
    access_token = "..."   # System User del Business, o token de Página
    page_id      = "..."
    ig_user_id   = "..."   # opcional: si falta, se deriva de la Página
    api_version  = "v21.0" # opcional

⚠️ Este token NO es el de [meta_ads]. El de Ads solo tiene ads_management /
ads_read (comprobado: `/me/accounts` devuelve vacío con él). Aquí hacen falta:

    pages_show_list            listar las Páginas del System User
    pages_read_engagement      canjear por token de Página — sin esto, NADA de
                               Facebook funciona (Page Insights lo exige)
    read_insights              métricas de la Página
    pages_read_user_content    listar published_posts -> likes/comentarios/
                               compartidos. Distinto de read_insights: se puede
                               leer la métrica y no poder listar los posts.
    instagram_basic            cuenta de IG, usuario, seguidores, media
    instagram_manage_insights  métricas de IG (reach, follower_count, views)
    pages_messaging            solo la métrica de mensajes (opcional)

Y hay que asignar al System User la Página **y** la cuenta de Instagram por
separado. Comprueba el conjunto con `scripts/verificar_social.py --red Meta`.

⚠️ INSTAGRAM NO TIENE IMPRESIONES. Meta retiró `impressions` el 21-abr-2025
(Graph v22.0) y la sustituyó por `views`. La columna sale a nulo por config.

⚠️ Los nombres de métrica de Page Insights los renombra y deprecia Meta a
menudo, y esta capa está SIN VERIFICAR contra la página real. Por eso las
métricas se piden con `_insights_tolerante`: si un nombre ya no existe, esa
métrica queda a NULO en vez de tumbar la llamada entera.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from src import config
from src.connectors.base import ResultadoConector, _leer_secreto
from src.connectors.social_base import resolver
from src.data import sample_data, social

RED_FB = "Facebook"
RED_IG = "Instagram"

_VERSION_POR_DEFECTO = "v21.0"

# Métrica normalizada -> nombres de Page Insights a probar, en orden de
# preferencia. El primero que la API acepte es el que se usa.
# ⚠️ Nombres VERIFICADOS contra la Página real (1229909610199926) el 30-jul-2026
# sondeando 30 candidatos uno a uno. Meta ha retirado toda la familia
# `page_impressions*` a nivel de Página: `page_impressions`,
# `page_impressions_organic`, `page_impressions_organic_v2` y
# `page_impressions_unique` responden «(#100) The value must be a valid insights
# metric». Lo que sobrevive son las impresiones de las PUBLICACIONES.
#
# Si vuelves a tocar esto, sondea antes: `scripts/verificar_social.py --red Meta`
# prueba cada candidato y dice cuál acepta la cuenta. No añadas nombres "por si
# acaso" que midan otra cosa: un fallback que mide algo distinto es peor que un
# nulo, porque nadie se entera.
_MAPA_FB_DIA = {
    # Facebook NO publica alcance: no existe ningún nombre válido (probados
    # page_impressions_unique, page_reach, page_daily_reach, page_posts_*_unique).
    # Por eso Facebook está fuera de SOPORTE_METRICA_SOCIAL["alcance"].
    #
    # `visualizaciones` = impresiones orgánicas de las publicaciones. Es el mismo
    # concepto que el `views` de Instagram («veces que tu contenido se mostró o
    # reprodujo»); Meta lo renombró en Instagram y no en Facebook. NO se usa
    # page_video_views, que solo cuenta vídeo y dejaría a Facebook artificialmente
    # pequeño en el KPI que se compara entre redes.
    "visualizaciones": ["page_posts_impressions_organic"],
    "seguidores_nuevos": ["page_daily_follows_unique", "page_daily_follows",
                          "page_follows"],
    # Requiere pages_messaging; sin ese permiso queda a nulo.
    "mensajes": ["page_messages_new_conversations_unique"],
}

# Instagram: solo `reach` y `follower_count` vienen como serie diaria. Todo lo
# demás (views, likes, comments, shares, saves, profile_views…) la API lo exige
# con metric_type=total_value, que devuelve UN número por consulta en vez de una
# serie — ver `_ig_views_por_dia`.
_MAPA_IG_DIA = {
    "alcance": ["reach"],
    # ⚠️ La API solo devuelve follower_count de los últimos 30 días. Para un
    # periodo más largo Meta da error y esta métrica queda a nulo: el histórico
    # anterior solo se cubre con el job diario o con los CSV importados.
    "seguidores_nuevos": ["follower_count"],
}

# Tope de días a los que se pide `views` de Instagram: una llamada por día.
_TOPE_DIAS_VIEWS_IG = 100

# Tope de publicaciones a las que se piden insights (una llamada por publicación).
# Si se alcanza, el conector lo dice en el `detalle` para que la UI no dé a
# entender que están todas.
_TOPE_POSTS = 100


# --------------------------------------------------------------------------- #
# Entradas públicas
# --------------------------------------------------------------------------- #

def obtener_facebook(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("social_meta")
    return resolver(
        clave="social_facebook_diario",
        fn_api=(lambda: _api_fb_diario(creds, desde, hasta)) if creds else None,
        fn_muestra=lambda: _muestra(RED_FB, desde, hasta, "diario"),
        normalizar=social.normalizar_diario,
        detalle_api="Facebook Page Insights",
        periodo=(desde, hasta),
    )


def obtener_posts_facebook(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("social_meta")
    return resolver(
        clave="social_facebook_posts",
        fn_api=(lambda: _api_fb_posts(creds, desde, hasta)) if creds else None,
        fn_muestra=lambda: _muestra(RED_FB, desde, hasta, "posts"),
        normalizar=social.normalizar_posts,
        detalle_api="Facebook published_posts + insights",
        periodo=(desde, hasta),
        claves_historico=("red", "post_id"),
    )


def obtener_instagram(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("social_meta")
    return resolver(
        clave="social_instagram_diario",
        fn_api=(lambda: _api_ig_diario(creds, desde, hasta)) if creds else None,
        fn_muestra=lambda: _muestra(RED_IG, desde, hasta, "diario"),
        normalizar=social.normalizar_diario,
        detalle_api="Instagram Insights",
        periodo=(desde, hasta),
    )


def obtener_posts_instagram(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("social_meta")
    return resolver(
        clave="social_instagram_posts",
        fn_api=(lambda: _api_ig_posts(creds, desde, hasta)) if creds else None,
        fn_muestra=lambda: _muestra(RED_IG, desde, hasta, "posts"),
        normalizar=social.normalizar_posts,
        detalle_api="Instagram media + insights",
        periodo=(desde, hasta),
        claves_historico=("red", "post_id"),
    )


def _muestra(red: str, desde, hasta, ambito: str) -> pd.DataFrame:
    df = (sample_data.social_posts(desde, hasta) if ambito == "posts"
          else sample_data.social_diario(desde, hasta))
    return df[df["red"] == red]


# --------------------------------------------------------------------------- #
# Utilidades de Graph API
# --------------------------------------------------------------------------- #

def _version(creds: dict) -> str:
    return creds.get("api_version", _VERSION_POR_DEFECTO)


def _get(version: str, path: str, token: str, params: dict | None = None) -> dict:
    """GET a Graph API. Lanza excepción si la respuesta trae error."""
    import requests

    p = dict(params or {})
    p["access_token"] = token
    r = requests.get(f"https://graph.facebook.com/{version}/{path}", params=p,
                     timeout=60)
    datos = r.json()
    if isinstance(datos, dict) and "error" in datos:
        raise RuntimeError(datos["error"].get("message", "error de Graph API"))
    r.raise_for_status()
    return datos


def _tipo_de_token(version: str, token: str) -> str:
    """"PAGE" | "SYSTEM_USER" | "USER" | "" (si no se puede saber)."""
    try:
        return _get(version, "debug_token", token,
                    {"input_token": token}).get("data", {}).get("type", "")
    except Exception:  # noqa: BLE001
        return ""


def _token_pagina(creds: dict) -> tuple[str, str]:
    """(page_id, page_token).

    Page Insights EXIGE un token de Página. Un token de System User o de usuario
    no vale: la API responde «(#190) This method must be called with a Page
    Access Token». Así que hay que canjearlo pidiendo el campo `access_token` de
    la propia Página.

    ⚠️ Antes, si el canje fallaba, esta función devolvía el token original dando
    por hecho que «ya era de Página». Era una suposición peligrosa: cuando el
    canje falla por falta de `pages_read_engagement`, devolvía un token
    inservible y los errores aparecían después, repartidos por cada métrica,
    como si los nombres de las métricas estuvieran mal. Ahora se comprueba el
    TIPO del token y se falla aquí, con la causa real.
    """
    version = _version(creds)
    token = creds["access_token"]
    page_id = creds.get("page_id") or config.SOCIAL_FACEBOOK_PAGE_ID
    if not page_id:
        raise RuntimeError("Falta page_id en [social_meta] o en config")

    tipo = _tipo_de_token(version, token)
    if tipo == "PAGE":
        return page_id, token

    try:
        datos = _get(version, page_id, token, {"fields": "access_token"})
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            f"No se ha podido obtener el token de Página (token de tipo "
            f"{tipo or 'desconocido'}): {e}. Suele ser que al token le falta "
            f"pages_read_engagement, o que la Página no está asignada al "
            f"System User."
        ) from e

    if not datos.get("access_token"):
        raise RuntimeError(
            f"La Página {page_id} no ha devuelto access_token y el token es de "
            f"tipo {tipo or 'desconocido'}, no PAGE. Page Insights necesita un "
            f"token de Página."
        )
    return page_id, datos["access_token"]


def _contexto_ig(creds: dict) -> tuple[str, str]:
    """(ig_user_id, token) para los endpoints de Instagram.

    A diferencia de Page Insights, la Instagram Graph API acepta el token de
    System User tal cual. Por eso Instagram NO debe caerse cuando falla el canje
    a token de Página: son requisitos distintos, y el módulo entero se apoya en
    que cada red se resuelva por su cuenta. Comprobado contra la cuenta real:
    con el token de System User (sin `pages_read_engagement`) Facebook fallaba
    entero mientras Instagram devolvía seguidores, `reach` y `follower_count`.
    """
    page_id = creds.get("page_id") or config.SOCIAL_INSTAGRAM_USER_ID
    token = creds["access_token"]
    try:
        page_id, token = _token_pagina(creds)
    except Exception:  # noqa: BLE001
        page_id = creds.get("page_id") or config.SOCIAL_FACEBOOK_PAGE_ID
        token = creds["access_token"]
    return _ig_user_id(creds, page_id, token), token


def _ig_user_id(creds: dict, page_id: str, page_token: str) -> str:
    """ID de la cuenta de Instagram Business vinculada a la Página."""
    if creds.get("ig_user_id"):
        return creds["ig_user_id"]
    if config.SOCIAL_INSTAGRAM_USER_ID:
        return config.SOCIAL_INSTAGRAM_USER_ID
    datos = _get(_version(creds), page_id, page_token,
                 {"fields": "instagram_business_account"})
    cuenta = (datos.get("instagram_business_account") or {}).get("id")
    if not cuenta:
        raise RuntimeError(
            "La Página no tiene cuenta de Instagram Business vinculada "
            "(o al token le falta instagram_basic)"
        )
    return cuenta


# Días por petición de insights. Meta rechaza rangos largos, y no igual en
# todas las métricas: `follower_count` de Instagram solo admite 30 días. Pedir
# 730 de golpe no devuelve "lo que haya", devuelve un error y la métrica entera
# se pierde — así se quedaron vacíos `alcance` y `seguidores_nuevos` en la
# primera captura real. Se trocea en ventanas y se van uniendo.
_DIAS_POR_PETICION = 30


def _trocear(desde, hasta, dias: int = _DIAS_POR_PETICION):
    """Parte [desde, hasta] en ventanas de como mucho `dias`, de la más reciente
    a la más antigua: si la API corta por antigüedad, lo que se pierde es lo
    viejo, no lo de esta semana."""
    ini = pd.Timestamp(desde).date()
    fin = pd.Timestamp(hasta).date()
    ventanas = []
    while fin >= ini:
        arranque = max(ini, fin - timedelta(days=dias - 1))
        ventanas.append((arranque, fin))
        fin = arranque - timedelta(days=1)
    return ventanas


def _insights_tolerante(version: str, objeto_id: str, token: str,
                        mapa: dict[str, list[str]], desde, hasta,
                        ) -> dict[str, dict]:
    """Pide `mapa` troceando el periodo, y une las ventanas que respondan."""
    unido: dict[str, dict] = {}
    for ini, fin in _trocear(desde, hasta):
        trozo = _insights_de_ventana(version, objeto_id, token, mapa, ini, fin)
        for metrica, serie in trozo.items():
            unido.setdefault(metrica, {}).update(serie)
    return unido


def _insights_de_ventana(version: str, objeto_id: str, token: str,
                         mapa: dict[str, list[str]], desde, hasta,
                         ) -> dict[str, dict]:
    """Pide insights y devuelve {metrica_normalizada: {fecha: valor}}.

    Prueba los nombres candidatos de cada métrica en bloque. Si el bloque falla
    (Meta rechaza TODA la llamada cuando un nombre no existe), reintenta métrica
    a métrica y descarta solo las que no estén disponibles. Lo que no se puede
    obtener no aparece en el resultado, y acaba como nulo en el DataFrame.
    """
    params_base = {"period": "day", "since": str(desde), "until": str(hasta)}
    resultado: dict[str, dict] = {}

    # Primer intento: el candidato preferido de cada métrica, todos juntos.
    preferidos = {m: cands[0] for m, cands in mapa.items() if cands}
    intentos: list[dict[str, str]] = [preferidos]
    # Reintentos: cada (métrica, candidato) por separado.
    for metrica, candidatos in mapa.items():
        for cand in candidatos:
            intentos.append({metrica: cand})

    for i, intento in enumerate(intentos):
        pendientes = {m: c for m, c in intento.items() if m not in resultado}
        if not pendientes:
            continue
        try:
            datos = _get(version, f"{objeto_id}/insights", token,
                         {**params_base, "metric": ",".join(pendientes.values())})
        except Exception:  # noqa: BLE001
            continue

        # nombre de API -> métrica normalizada
        inverso = {c: m for m, c in pendientes.items()}
        for bloque in datos.get("data", []):
            metrica = inverso.get(bloque.get("name"))
            if not metrica:
                continue
            serie = {}
            for v in bloque.get("values", []):
                fecha = _fecha_de_periodo(v.get("end_time"))
                if fecha is not None:
                    serie[fecha] = v.get("value")
            if serie:
                resultado[metrica] = serie
        # Tras el intento en bloque seguimos con los individuales solo para las
        # métricas que no hayan salido.
        if i == 0:
            continue
    return resultado


def _fecha_de_periodo(end_time: str | None):
    """Convierte el `end_time` de un insight con period=day en SU fecha.

    Trampa clásica de Meta: con period=day el valor cubre las 24 h que TERMINAN
    en `end_time`, y `end_time` cae de madrugada del día SIGUIENTE. Usar su fecha
    tal cual desplaza toda la serie un día. Por eso se resta un día.
    """
    if not end_time:
        return None
    ts = pd.to_datetime(end_time, errors="coerce", utc=True)
    if pd.isna(ts):
        return None
    return (ts - timedelta(days=1)).date()


def _series_a_df(series: dict[str, dict], red: str) -> pd.DataFrame:
    """{metrica: {fecha: valor}} -> DataFrame con una fila por fecha."""
    fechas = sorted({f for serie in series.values() for f in serie})
    if not fechas:
        return pd.DataFrame()
    filas = []
    for f in fechas:
        fila = {"fecha": f, "red": red}
        for metrica, serie in series.items():
            valor = serie.get(f)
            # Algunas métricas devuelven dict (desglose por tipo); se suma.
            if isinstance(valor, dict):
                valor = sum(v for v in valor.values() if isinstance(v, (int, float)))
            fila[metrica] = valor
        filas.append(fila)
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------- #
# Facebook
# --------------------------------------------------------------------------- #

def _api_fb_diario(creds: dict, desde, hasta) -> pd.DataFrame:
    version = _version(creds)
    page_id, token = _token_pagina(creds)
    series = _insights_tolerante(version, page_id, token, _MAPA_FB_DIA, desde, hasta)
    df = _series_a_df(series, RED_FB)

    # Likes y comentarios de la Página no son métricas de Page Insights: se
    # agregan desde las publicaciones del periodo.
    #
    # Va en try porque listar las publicaciones necesita OTRO permiso
    # (`pages_read_user_content`) distinto del de los insights. Sin él, esta
    # llamada falla y antes se llevaba por delante las métricas diarias, que sí
    # funcionaban. Si falla, el engagement queda a NULO y el resto se salva.
    try:
        df = _sumar_engagement_de_posts(df, _api_fb_posts(creds, desde, hasta), RED_FB)
    except Exception:  # noqa: BLE001
        pass

    if not df.empty:
        total = _seguidores_pagina(version, page_id, token)
        if total is not None:
            df.loc[df.index[-1], "seguidores_total"] = total
    return df


def _seguidores_pagina(version: str, page_id: str, token: str) -> int | None:
    try:
        datos = _get(version, page_id, token, {"fields": "followers_count,fan_count"})
        return int(datos.get("followers_count") or datos.get("fan_count") or 0) or None
    except Exception:  # noqa: BLE001
        return None


def _api_fb_posts(creds: dict, desde, hasta) -> pd.DataFrame:
    version = _version(creds)
    page_id, token = _token_pagina(creds)

    campos = ("id,message,story,created_time,permalink_url,full_picture,"
              "shares,comments.summary(true).limit(0),"
              "reactions.summary(true).limit(0)")
    datos = _get(version, f"{page_id}/published_posts", token, {
        "fields": campos, "since": str(desde), "until": str(hasta), "limit": 100,
    })

    filas = []
    for p in datos.get("data", [])[:_TOPE_POSTS]:
        pid = p.get("id")
        insights = _insights_post_fb(version, pid, token)
        texto = (p.get("message") or p.get("story") or "").strip()
        filas.append(dict(
            red=RED_FB, post_id=pid,
            fecha=(p.get("created_time") or "")[:10],
            tipo="Publicación",
            titulo=(texto[:120] or "(sin texto)"),
            url=p.get("permalink_url", ""),
            miniatura=p.get("full_picture", ""),
            impresiones=insights.get("impresiones"),
            visualizaciones=insights.get("visualizaciones"),
            likes=(p.get("reactions", {}).get("summary", {}) or {}).get("total_count"),
            comentarios=(p.get("comments", {}).get("summary", {}) or {}).get("total_count"),
            compartidos=(p.get("shares", {}) or {}).get("count", 0),
        ))
    return pd.DataFrame(filas)


def _insights_post_fb(version: str, post_id: str, token: str) -> dict:
    """Impresiones y visualizaciones de UNA publicación. {} si no se pueden leer."""
    for metricas in (("post_impressions_organic", "post_video_views"),
                     ("post_impressions", "post_video_views"),
                     ("post_impressions",)):
        try:
            datos = _get(version, f"{post_id}/insights", token,
                         {"metric": ",".join(metricas)})
        except Exception:  # noqa: BLE001
            continue
        out = {}
        for bloque in datos.get("data", []):
            valores = bloque.get("values") or [{}]
            valor = valores[0].get("value")
            if bloque.get("name", "").startswith("post_impressions"):
                out["impresiones"] = valor
            elif bloque.get("name") == "post_video_views":
                out["visualizaciones"] = valor
        if out:
            return out
    return {}


def _sumar_engagement_de_posts(diario: pd.DataFrame, posts: pd.DataFrame,
                               red: str) -> pd.DataFrame:
    """Añade likes/comentarios/compartidos diarios agregando las publicaciones.

    Se atribuyen al día de PUBLICACIÓN, que es lo que hace Business Suite. No es
    lo mismo que «interacciones recibidas ese día» en publicaciones antiguas, y
    por eso la página lo advierte en la nota metodológica.
    """
    if posts is None or posts.empty:
        return diario
    p = posts.copy()
    p["fecha"] = pd.to_datetime(p["fecha"], errors="coerce").dt.date
    agg = (p.groupby("fecha", as_index=False)[["likes", "comentarios", "compartidos"]]
           .sum(min_count=1))
    if diario is None or diario.empty:
        agg["red"] = red
        return agg
    d = diario.copy()
    d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce").dt.date
    return d.merge(agg, on="fecha", how="left")


# --------------------------------------------------------------------------- #
# Instagram
# --------------------------------------------------------------------------- #

def _ig_views_por_dia(version: str, ig: str, token: str, desde, hasta) -> dict:
    """{fecha: views} de Instagram, pidiendo DÍA A DÍA.

    `views` no admite serie diaria: la API obliga a `metric_type=total_value`,
    que devuelve un único número agregado del rango consultado. Para llenar el
    esquema diario hay que consultar cada día por separado — una llamada por
    día. Verificado contra la cuenta real: 28-jul-2026 → 6.162 views.

    Por eso NO se llama al pintar la página (sería un puñado de llamadas por
    cada cambio de rango): lo hace el job diario, que paga 1 llamada al día y lo
    acumula en el histórico. Ver `scripts/snapshot_social.py`.

    Un día que falle se omite del resultado, y acaba como NULO en el DataFrame:
    nunca como 0.
    """
    dias = [d.date() for d in pd.date_range(desde, hasta, freq="D")]
    if len(dias) > _TOPE_DIAS_VIEWS_IG:
        dias = dias[-_TOPE_DIAS_VIEWS_IG:]  # los más recientes

    out = {}
    for d in dias:
        try:
            r = _get(version, f"{ig}/insights", token, {
                "metric": "views", "metric_type": "total_value", "period": "day",
                "since": str(d), "until": str(d + timedelta(days=1))})
            valor = ((r.get("data") or [{}])[0].get("total_value") or {}).get("value")
            if valor is not None:
                out[d] = valor
        except Exception:  # noqa: BLE001
            continue
    return out


def _api_ig_diario(creds: dict, desde, hasta, con_views: bool = False) -> pd.DataFrame:
    """Métricas diarias de Instagram.

    `con_views` activa el sondeo día a día de `views` (una llamada por día). Lo
    usa el job diario; la página lo deja apagado y lee esa columna del
    histórico, que `social_base.resolver` funde por debajo.
    """
    version = _version(creds)
    ig, token = _contexto_ig(creds)

    series = _insights_tolerante(version, ig, token, _MAPA_IG_DIA, desde, hasta)
    if con_views:
        views = _ig_views_por_dia(version, ig, token, desde, hasta)
        if views:
            series["visualizaciones"] = views
    df = _series_a_df(series, RED_IG)
    # Mismo motivo que en Facebook: si listar las publicaciones falla, no debe
    # arrastrar a las métricas de cuenta que sí se han obtenido.
    try:
        df = _sumar_engagement_de_posts(df, _api_ig_posts(creds, desde, hasta), RED_IG)
    except Exception:  # noqa: BLE001
        pass

    if not df.empty:
        try:
            datos = _get(version, ig, token, {"fields": "followers_count"})
            if datos.get("followers_count"):
                df.loc[df.index[-1], "seguidores_total"] = int(datos["followers_count"])
        except Exception:  # noqa: BLE001
            pass
    return df


_TIPO_IG = {"IMAGE": "Imagen", "VIDEO": "Reel", "CAROUSEL_ALBUM": "Carrusel",
            "REELS": "Reel", "STORY": "Story"}


def _api_ig_posts(creds: dict, desde, hasta) -> pd.DataFrame:
    version = _version(creds)
    ig, token = _contexto_ig(creds)

    campos = ("id,caption,media_type,media_product_type,permalink,thumbnail_url,"
              "media_url,timestamp,like_count,comments_count")
    datos = _get(version, f"{ig}/media", token, {"fields": campos, "limit": 100})

    desde_d = pd.to_datetime(desde).date()
    hasta_d = pd.to_datetime(hasta).date()

    filas = []
    for m in datos.get("data", []):
        fecha = pd.to_datetime(m.get("timestamp"), errors="coerce", utc=True)
        if pd.isna(fecha):
            continue
        fecha = fecha.date()
        # /media no filtra por fechas: se acota aquí.
        if not (desde_d <= fecha <= hasta_d):
            continue
        if len(filas) >= _TOPE_POSTS:
            break
        insights = _insights_post_ig(version, m["id"], token)
        caption = (m.get("caption") or "").strip()
        crudo = m.get("media_product_type") or m.get("media_type") or ""
        filas.append(dict(
            red=RED_IG, post_id=m["id"], fecha=fecha,
            tipo=_TIPO_IG.get(crudo.upper(), "Publicación"),
            titulo=(caption[:120] or "(sin texto)"),
            url=m.get("permalink", ""),
            miniatura=m.get("thumbnail_url") or m.get("media_url") or "",
            visualizaciones=insights.get("visualizaciones"),
            likes=m.get("like_count"),
            comentarios=m.get("comments_count"),
            compartidos=insights.get("compartidos"),
            guardados=insights.get("guardados"),
        ))
    return pd.DataFrame(filas)


def _insights_post_ig(version: str, media_id: str, token: str) -> dict:
    """views / shares / saved de UNA publicación. {} si no se pueden leer.

    `views` sustituyó a `impressions` en v22.0; se prueba primero.
    """
    for metricas in (("views", "shares", "saved"),
                     ("impressions", "saved"),
                     ("views",)):
        try:
            datos = _get(version, f"{media_id}/insights", token,
                         {"metric": ",".join(metricas)})
        except Exception:  # noqa: BLE001
            continue
        traduccion = {"views": "visualizaciones", "impressions": "visualizaciones",
                      "shares": "compartidos", "saved": "guardados"}
        out = {}
        for bloque in datos.get("data", []):
            clave = traduccion.get(bloque.get("name"))
            if clave:
                valores = bloque.get("values") or [{}]
                out[clave] = valores[0].get("value")
        if out:
            return out
    return {}
