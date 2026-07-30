"""
Cascada de resolución común a los conectores de social orgánico.

Los tres conectores (YouTube, Meta, LinkedIn) resuelven sus datos igual, con un
nivel MÁS que el resto del dashboard:

    API real  ->  caché parquet  ->  CSV importado  ->  datos de ejemplo

El nivel de CSV existe porque las APIs de social no dan todo el histórico hacia
atrás (Instagram es el caso extremo: seguidores solo 30 días). Los exports
manuales de cada plataforma son la única forma de cubrir el pasado, así que son
una fuente de primera clase, no un apaño.

Y por DEBAJO de todos ellos hay un suelo: el histórico que `scripts/
snapshot_social.py` acumula día a día. No es un nivel más de la cascada, es una
capa que se funde con el que gane, porque cubre un hueco distinto: la API sí
responde, pero solo de su ventana (30 días en Instagram) y lo de antes tiene que
seguir viéndose. La API manda en las fechas que cubre; el histórico rellena el
resto.

Cada red resuelve la suya de forma independiente: que LinkedIn no tenga todavía
la aprobación de su API no degrada lo que se ve de YouTube o Meta.
"""
from __future__ import annotations

from typing import Callable, Sequence

import pandas as pd

from src.connectors.base import (
    ResultadoConector,
    guardar_cache,
    leer_cache,
    leer_csv_importado,
    leer_historico,
)


def fusionar(base: pd.DataFrame, nuevo: pd.DataFrame,
             claves: Sequence[str]) -> pd.DataFrame:
    """Une dos tablas del mismo esquema. `nuevo` manda, CASILLA a casilla.

    - Fila cuya clave solo está en `base` -> se conserva tal cual.
    - Fila presente en las dos -> se combinan celda a celda: gana el valor de
      `nuevo` SALVO que sea nulo, en cuyo caso se mantiene el de `base`.

    Esa última regla es la importante: si hoy la API deja de dar una métrica
    (Meta renombra nombres de Page Insights a menudo), el refresco no puede
    borrar un dato que ya estaba capturado. Y como los nulos nunca pisan, la
    regla «nulo ≠ cero» sobrevive a la fusión.

    Lo usan los dos lados: `resolver` para pintar, y `snapshot_social.py` para
    acumular sobre el fichero que ya había.
    """
    if base is None or base.empty:
        return nuevo
    if nuevo is None or nuevo.empty:
        return base

    claves = [c for c in claves if c in base.columns and c in nuevo.columns]
    if not claves:
        return nuevo

    # Filas de `nuevo` sin clave completa: no se pueden casar con nada, así que
    # se apartan y se devuelven al final en vez de perderlas (un post sin fecha
    # sigue siendo un post).
    sin_clave = nuevo[nuevo[claves].isna().any(axis=1)]
    con_clave = nuevo.drop(sin_clave.index)
    if con_clave.empty:
        return nuevo

    b = (base.dropna(subset=claves)
             .drop_duplicates(subset=claves, keep="last")
             .set_index(claves))
    n = con_clave.drop_duplicates(subset=claves, keep="last").set_index(claves)

    fusion = n.combine_first(b).reset_index()
    if not sin_clave.empty:
        fusion = pd.concat([fusion, sin_clave], ignore_index=True)

    # `combine_first` reordena columnas alfabéticamente; el esquema de
    # `src/data/social.py` tiene un orden fijo del que dependen páginas y caché.
    orden = list(nuevo.columns) + [c for c in fusion.columns
                                   if c not in nuevo.columns]
    return fusion[[c for c in orden if c in fusion.columns]]


def _recortar(df: pd.DataFrame, periodo: tuple | None) -> pd.DataFrame:
    """Deja solo las filas dentro de [desde, hasta].

    Hace falta en los niveles cuyo contenido NO se corresponde con lo que se ha
    pedido: el histórico crece sin límite, y la caché guarda la última ventana
    que se consultó, que puede ser más ancha que la de ahora. Sin recortar, al
    elegir «últimos 7 días» los gráficos pintarían días de fuera del periodo.

    Al resultado de la API no se le aplica: se le pidió justo ese rango.
    """
    if df is None or df.empty or not periodo or "fecha" not in df.columns:
        return df
    desde, hasta = (pd.Timestamp(x).date() for x in periodo)
    fechas = pd.to_datetime(df["fecha"], errors="coerce").dt.date
    return df[fechas.notna() & (fechas >= desde) & (fechas <= hasta)].reset_index(drop=True)


def _historico(clave: str,
               normalizar: Callable[[pd.DataFrame], pd.DataFrame],
               periodo: tuple | None) -> pd.DataFrame | None:
    """Histórico acumulado de `clave`, normalizado y recortado al periodo."""
    bruto = leer_historico(clave)
    if bruto is None or bruto.empty:
        return None
    return _recortar(normalizar(bruto), periodo)


def _con_historico(df: pd.DataFrame, origen: str, detalle: str,
                   historico: pd.DataFrame | None,
                   claves: Sequence[str]) -> ResultadoConector:
    """Funde el histórico por debajo de `df` y anota cuánto ha aportado."""
    if historico is None or historico.empty:
        return ResultadoConector(df, origen, detalle)

    fusion = fusionar(historico, df, claves)
    extra = len(fusion) - len(df)
    if extra > 0:
        detalle = f"{detalle} + {extra} filas de histórico propio"
    return ResultadoConector(fusion, origen, detalle)


def resolver(clave: str,
             fn_api: Callable[[], pd.DataFrame] | None,
             fn_muestra: Callable[[], pd.DataFrame],
             normalizar: Callable[[pd.DataFrame], pd.DataFrame],
             detalle_api: str,
             periodo: tuple | None = None,
             claves_historico: Sequence[str] = ("fecha", "red"),
             ) -> ResultadoConector:
    """Resuelve un dataset recorriendo la cascada y lo devuelve NORMALIZADO.

    `normalizar` se aplica a todos los niveles por igual (API, caché, CSV,
    histórico y ejemplo). Es lo que garantiza que la regla de los nulos se
    cumpla sea cual sea el origen: un CSV mal montado a mano no puede meter un 0
    en una casilla que la red no publica.

    La caché se guarda con el dato CRUDO de la API, antes de normalizar, para no
    perder columnas si el esquema cambia más adelante.

    `periodo` es el (desde, hasta) que se ha pedido, y sirve para recortar el
    histórico. `claves_historico` identifica una fila para fusionar: (fecha,
    red) en las tablas diarias, (red, post_id) en las de publicaciones.

    Con los datos de EJEMPLO no se funde nada: mezclar histórico real con datos
    inventados daría una tabla imposible de interpretar.
    """
    historico = _historico(clave, normalizar, periodo)

    fallo_api = ""
    if fn_api is not None:
        try:
            df = fn_api()
            if df is not None and not df.empty:
                guardar_cache(df, clave)
                return _con_historico(normalizar(df), "api", detalle_api,
                                      historico, claves_historico)
        except Exception as e:  # noqa: BLE001
            fallo_api = str(e)

    cache = leer_cache(clave)
    if cache is not None and not cache.empty:
        detalle = f"API falló ({fallo_api}); uso caché" if fallo_api else "Caché local"
        return _con_historico(_recortar(normalizar(cache), periodo), "cache",
                              detalle, historico, claves_historico)

    csv = leer_csv_importado(clave)
    if csv is not None and not csv.empty:
        return _con_historico(_recortar(normalizar(csv), periodo), "csv",
                              "Export CSV importado", historico, claves_historico)

    if historico is not None and not historico.empty:
        return ResultadoConector(historico, "historico",
                                 "Histórico propio (snapshot_social.py)")

    return ResultadoConector(normalizar(fn_muestra()), "sample", "Datos de ejemplo")


def peor_origen(origenes: list[str]) -> str:
    """Origen «resumen» de varias redes, para el semáforo global de la página.

    Se queda con el PEOR de la lista: si una sola red está en ejemplo, el
    conjunto no es un dato en vivo y la UI no debe insinuar que sí.
    """
    for nivel in ("sample", "csv", "historico", "cache", "api"):
        if nivel in origenes:
            return nivel
    return "sample"
