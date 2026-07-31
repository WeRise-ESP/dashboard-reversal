"""
Conector de TikTok orgánico (Display API v2).

Cascada: API real -> caché -> CSV importado -> datos de ejemplo.

Credenciales esperadas en .streamlit/secrets.toml:
    [tiktok]
    client_key    = "..."
    client_secret = "..."
    refresh_token = "..."

⚠️ ESTADO: SIN VERIFICAR CONTRA NINGUNA CUENTA. La app de TikTok estaba sin
crear el 31-jul-2026, así que todo lo de aquí sale de la documentación. Por eso
`config.SOPORTE_POR_VERIFICAR` tiene a TikTok ENTERO: hasta que se sondee, sus
métricas salen a nulo en vez de mostrar números que nadie ha visto funcionar.

En esta misma página, la documentación ya ha fallado cuatro veces (Facebook
había retirado impresiones y alcance; YouTube devuelve `age65-`). Al llegar la
credencial: `scripts/verificar_social.py --red TikTok`.

⚠️ DIFERENCIA ESTRUCTURAL CON LAS OTRAS CUATRO REDES, y no es un detalle:

La Display API **no da series diarias**. Devuelve el estado ACTUAL de la cuenta
(seguidores, likes totales, nº de vídeos) y las métricas ACUMULADAS de cada
vídeo. No existe un endpoint de «visualizaciones del día 12».

Consecuencia: la serie diaria de TikTok no se pide, se CONSTRUYE. Cada
ejecución del job guarda una foto del día, y el histórico las va encadenando
hasta formar una serie. Eso significa que:

  - Un periodo anterior a la primera captura no tiene datos y NO se puede
    recuperar. Con TikTok no hay relleno hacia atrás, a diferencia de YouTube
    (histórico completo) o Facebook (~2 años).
  - Cuanto antes corra el job, antes empieza a existir la serie.

Las métricas diarias de verdad (visualizaciones por día, alcance, demografía)
solo las da la **Business API**, que exige cuenta TikTok Business y una revisión
aparte. Si se aprueba, este conector gana una segunda fuente; mientras tanto,
lo que hay es la foto diaria.
"""
from __future__ import annotations

import pandas as pd

from src.connectors.base import ResultadoConector, _leer_secreto
from src.connectors.social_base import resolver
from src.data import sample_data, social

RED = "TikTok"

_BASE = "https://open.tiktokapis.com/v2"

# Campos del perfil. `follower_count` y `likes_count` son totales ACTUALES, no
# del periodo: por eso alimentan `seguidores_total` (un stock) y no una métrica
# de flujo.
_CAMPOS_USUARIO = "open_id,display_name,follower_count,likes_count,video_count"

# Campos por vídeo. Todos son acumulados desde que se publicó, igual que en
# Instagram y Facebook — no del periodo consultado.
_CAMPOS_VIDEO = ("id,title,video_description,create_time,cover_image_url,"
                 "share_url,view_count,like_count,comment_count,share_count")

_TOPE_VIDEOS = 100


# --------------------------------------------------------------------------- #
# Entradas públicas
# --------------------------------------------------------------------------- #

def obtener(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("tiktok")
    return resolver(
        clave="social_tiktok_diario",
        fn_api=(lambda: _api_diario(creds, desde, hasta)) if creds else None,
        fn_muestra=lambda: _muestra(desde, hasta, "diario"),
        normalizar=social.normalizar_diario,
        detalle_api="TikTok Display API (foto del día)",
        periodo=(desde, hasta),
    )


def obtener_posts(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("tiktok")
    return resolver(
        clave="social_tiktok_posts",
        fn_api=(lambda: _api_posts(creds, desde, hasta)) if creds else None,
        fn_muestra=lambda: _muestra(desde, hasta, "posts"),
        normalizar=social.normalizar_posts,
        detalle_api="TikTok Display API",
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

    Los access token de TikTok duran 24 h y el refresh token 365 días, así que
    se canjea en cada carga (la caché de Streamlit evita que sea en cada clic).
    """
    import requests

    r = requests.post(
        f"{_BASE}/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": creds["client_key"],
            "client_secret": creds["client_secret"],
            "grant_type": "refresh_token",
            "refresh_token": creds["refresh_token"],
        },
        timeout=60,
    )
    r.raise_for_status()
    datos = r.json()
    if "access_token" not in datos:
        raise RuntimeError(f"TikTok no devolvió access_token: {str(datos)[:200]}")
    return datos["access_token"]


def _post(ruta: str, token: str, campos: str, cuerpo: dict | None = None) -> dict:
    """POST a la Display API. Lanza excepción si la respuesta trae error.

    TikTok mete el error DENTRO del cuerpo con HTTP 200, así que no basta con
    `raise_for_status`: hay que mirar `error.code`, que vale «ok» cuando todo
    ha ido bien.
    """
    import requests

    r = requests.post(
        f"{_BASE}/{ruta}", params={"fields": campos},
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json=cuerpo or {}, timeout=60,
    )
    datos = r.json() if r.content else {}
    error = (datos.get("error") or {})
    if error.get("code") not in (None, "ok"):
        raise RuntimeError(f"{error.get('code')}: {error.get('message', '')}")
    r.raise_for_status()
    return datos.get("data", {})


def _api_diario(creds: dict, desde, hasta) -> pd.DataFrame:
    """UNA fila con la foto de hoy: seguidores actuales de la cuenta.

    No es un error que devuelva una sola fila. La Display API no publica series
    diarias (ver la cabecera del módulo), así que la serie se construye
    acumulando estas fotos en `data/historico_social/` con el job diario.

    Deliberadamente NO se rellenan `visualizaciones`, `likes` ni el resto de
    métricas de flujo con los totales de la cuenta: `likes_count` es el total
    histórico de la cuenta, no los likes del día, y ponerlo en una columna de
    flujo dispararía cualquier suma del periodo.
    """
    token = _token(creds)
    datos = _post("user/info/", token, _CAMPOS_USUARIO)
    usuario = datos.get("user", {})
    if not usuario:
        return pd.DataFrame()

    return pd.DataFrame([{
        "fecha": pd.Timestamp(hasta).date(),
        "red": RED,
        "seguidores_total": usuario.get("follower_count"),
    }])


def _api_posts(creds: dict, desde, hasta) -> pd.DataFrame:
    """Vídeos publicados en el periodo, con sus métricas acumuladas.

    Se pagina con el cursor de TikTok y se filtra por fecha en Python: la API
    no acepta un rango, devuelve los vídeos del más reciente hacia atrás. En
    cuanto aparece uno anterior a `desde` se corta, porque vienen ordenados.
    """
    token = _token(creds)
    desde_d = pd.Timestamp(desde).date()
    hasta_d = pd.Timestamp(hasta).date()

    filas, cursor, quedan = [], None, True
    while quedan and len(filas) < _TOPE_VIDEOS:
        cuerpo = {"max_count": 20}
        if cursor:
            cuerpo["cursor"] = cursor
        datos = _post("video/list/", token, _CAMPOS_VIDEO, cuerpo)

        videos = datos.get("videos", [])
        if not videos:
            break

        for v in videos:
            creado = v.get("create_time")
            fecha = (pd.to_datetime(creado, unit="s", errors="coerce").date()
                     if creado else None)
            if fecha is None:
                continue
            if fecha < desde_d:
                quedan = False   # vienen del más nuevo al más viejo
                break
            if fecha > hasta_d:
                continue
            texto = (v.get("title") or v.get("video_description") or "").strip()
            filas.append(dict(
                red=RED, post_id=v.get("id"), fecha=fecha, tipo="Vídeo",
                titulo=texto[:120] or "(sin texto)",
                url=v.get("share_url", ""),
                miniatura=v.get("cover_image_url", ""),
                visualizaciones=v.get("view_count"),
                likes=v.get("like_count"),
                comentarios=v.get("comment_count"),
                compartidos=v.get("share_count"),
            ))

        cursor = datos.get("cursor")
        if not datos.get("has_more") or not cursor:
            break

    return pd.DataFrame(filas)
