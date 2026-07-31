"""
Análisis por red: comparativa contra el periodo anterior y rendimiento de
publicaciones.

Este módulo NO importa streamlit a propósito: así se puede probar con
DataFrames sueltos, sin levantar una app. Todo lo que devuelve son datos; de
pintarlos se encarga `src/ui/social_red.py`.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src import config


def periodo_anterior(desde: date, hasta: date) -> tuple[date, date]:
    """El intervalo de la MISMA longitud inmediatamente anterior a `desde`.

    Para 1–30 de julio devuelve 1–30 de junio. Se usa para dar contexto a los
    KPIs: un número sin el del periodo anterior no dice si va bien o mal.
    """
    dias = (hasta - desde).days
    fin = desde - timedelta(days=1)
    return fin - timedelta(days=dias), fin


def _total(diario: pd.DataFrame, red: str, metrica: str) -> float | None:
    """Suma de una métrica en un periodo, para una red. None si no hay dato.

    `min_count=1` es lo que mantiene la regla: si todas las casillas son nulas
    el resultado es nulo, no 0.
    """
    if diario is None or diario.empty or metrica not in diario.columns:
        return None
    d = diario[diario["red"] == red]
    if d.empty:
        return None
    total = d[metrica].sum(min_count=1)
    return None if pd.isna(total) else float(total)


def kpis_de_publicaciones(posts: pd.DataFrame, red: str) -> dict[str, float]:
    """Total del periodo sumando publicaciones, para las redes sin serie diaria.

    Es el único camino en TikTok: su Display API da el acumulado de cada vídeo y
    ningún endpoint de «visualizaciones del día 12». Ver
    `config.REDES_SIN_SERIE_DIARIA`, donde está escrito qué significa —y qué NO
    significa— el número que sale de aquí.

    Solo métricas de flujo: los stocks (`seguidores_total`) no se suman entre
    publicaciones porque no pertenecen a una publicación.
    """
    flujo = ("visualizaciones", "likes", "comentarios", "compartidos")
    if posts is None or posts.empty:
        return {}
    d = posts[posts["red"] == red]
    if d.empty:
        return {}

    totales = {}
    for m in flujo:
        if m not in d.columns:
            continue
        # `min_count=1` mantiene la regla: todo nulo suma nulo, no 0.
        total = d[m].sum(min_count=1)
        if not pd.isna(total):
            totales[m] = float(total)
    return totales


def serie_de_publicaciones(posts: pd.DataFrame, red: str,
                           metrica: str) -> pd.DataFrame:
    """Serie (fecha, red, valor) por FECHA DE PUBLICACIÓN, no por día de
    actividad.

    El sustituto de la serie diaria en las redes que no la tienen. Cada punto es
    el acumulado de lo publicado ese día, así que el eje X son fechas de
    publicación y hay huecos en los días sin publicar — no ceros. Ver
    `config.REDES_SIN_SERIE_DIARIA`.
    """
    vacia = pd.DataFrame(columns=["fecha", "red", "valor"])
    if posts is None or posts.empty or metrica not in posts.columns:
        return vacia
    d = posts[posts["red"] == red]
    if d.empty:
        return vacia

    d = d[["fecha", "red", metrica]].rename(columns={metrica: "valor"})
    d = d[d["valor"].notna()]
    if d.empty:
        return vacia
    return (d.groupby(["fecha", "red"], as_index=False)["valor"]
            .sum(min_count=1)
            .sort_values("fecha"))


def comparar_kpis(actual: pd.DataFrame, anterior: pd.DataFrame,
                  red: str, posts: pd.DataFrame | None = None,
                  posts_anterior: pd.DataFrame | None = None) -> pd.DataFrame:
    """Tabla `metrica · etiqueta · actual · anterior · delta_pct` para una red.

    Solo incluye las métricas que ESA red publica: las demás no aparecen, ni a
    cero ni con guion. Para esa red, sencillamente no existen.

    `delta_pct` es nulo cuando no hay periodo anterior o cuando el anterior es
    cero: dividir por cero daría un crecimiento del infinito por ciento, que es
    peor que no decir nada.
    """
    # En las redes sin serie diaria el total del periodo sale de sumar
    # publicaciones; si no, la tabla saldría entera vacía al lado de una lista
    # de vídeos con sus números a la vista, que es lo que pasaba con TikTok.
    de_posts = kpis_de_publicaciones(posts, red) if (
        posts is not None and red in config.REDES_SIN_SERIE_DIARIA) else {}
    de_posts_ant = kpis_de_publicaciones(posts_anterior, red) if (
        posts_anterior is not None
        and red in config.REDES_SIN_SERIE_DIARIA) else {}

    filas = []
    for metrica, etiqueta in config.METRICAS_SOCIAL.items():
        if not config.soporta_metrica(metrica, red):
            continue
        act = de_posts.get(metrica, _total(actual, red, metrica))
        ant = de_posts_ant.get(metrica, _total(anterior, red, metrica))
        delta = None
        if act is not None and ant not in (None, 0):
            delta = round((act - ant) / ant * 100, 1)
        filas.append({"metrica": metrica, "etiqueta": etiqueta,
                      "actual": act, "anterior": ant, "delta_pct": delta})
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------- #
# Rendimiento de publicaciones
# --------------------------------------------------------------------------- #

def criterio_ranking(red: str) -> str:
    """Por qué se ordenan las publicaciones de esta red.

    Lo normal es la TASA de engagement: ordenar por likes brutos hace ganar
    siempre a la publicación más vista, que es una observación circular («lo
    que más se vio es lo que más se vio»).

    Facebook es la excepción: solo sus vídeos y reels traen visualizaciones, así
    que en las estáticas no hay denominador y la tasa sale nula. Sus
    publicaciones se ordenan por interacciones absolutas, y la UI lo dice.

    El criterio se decide AQUÍ y en ningún otro sitio: el día que la mayoría de
    las publicaciones de Facebook sean vídeo, cambiarlo es una línea.
    """
    return "interacciones" if red == "Facebook" else "engagement"


def _con_puntuacion(posts: pd.DataFrame, red: str) -> pd.DataFrame:
    """Añade la columna `puntuacion` con la que se ordena esa red."""
    from src.data import social

    d = posts[posts["red"] == red].copy()
    if d.empty:
        return d
    if criterio_ranking(red) == "engagement":
        d["puntuacion"] = social.tasa_engagement(d)
    else:
        d["puntuacion"] = social.interacciones(d)
    return d


def ranking(posts: pd.DataFrame, red: str, n: int = 3,
            mejores: bool = True) -> pd.DataFrame:
    """Las `n` mejores (o peores) publicaciones de una red.

    Las publicaciones sin puntuación se descartan: no se puede afirmar que una
    publicación sin datos sea la peor.
    """
    if posts is None or posts.empty:
        return posts if posts is not None else pd.DataFrame()
    d = _con_puntuacion(posts, red)
    if d.empty:
        return d
    d = d[d["puntuacion"].notna()]
    return d.sort_values("puntuacion", ascending=not mejores).head(n)


def hay_muestra_para_bottom(posts: pd.DataFrame, red: str) -> bool:
    """Si hay publicaciones suficientes para que «las peores» signifiquen algo.

    Con dos publicaciones, «la peor» es simplemente «la segunda».
    """
    if posts is None or posts.empty:
        return False
    return int((posts["red"] == red).sum()) >= config.MIN_PUBLICACIONES_BOTTOM


def por_formato(posts: pd.DataFrame, red: str) -> pd.DataFrame:
    """Media por tipo de publicación (Reel, Carrusel, Short, Vídeo…).

    Es el bloque que responde «qué publico la semana que viene». Solo aparecen
    los formatos con al menos `config.MIN_PUBLICACIONES_FORMATO` publicaciones:
    una media de una sola no es una media, y ponerla al lado de otra de doce
    invita a compararlas como si pesaran igual.
    """
    from src.data import social

    if posts is None or posts.empty:
        return pd.DataFrame(columns=["tipo", "n", "visualizaciones_media",
                                     "engagement_medio"])
    d = posts[posts["red"] == red].copy()
    if d.empty:
        return pd.DataFrame(columns=["tipo", "n", "visualizaciones_media",
                                     "engagement_medio"])
    d["_eng"] = social.tasa_engagement(d)
    g = d.groupby("tipo", dropna=False).agg(
        n=("post_id", "count"),
        visualizaciones_media=("visualizaciones", "mean"),
        engagement_medio=("_eng", "mean"),
    ).reset_index()
    return g[g["n"] >= config.MIN_PUBLICACIONES_FORMATO].sort_values(
        "n", ascending=False).reset_index(drop=True)
