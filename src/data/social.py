"""
Esquema normalizado y métricas derivadas del social orgánico.

Las 4 redes (YouTube, Facebook, Instagram, LinkedIn) devuelven cosas distintas
con nombres distintos. Este módulo las lleva a DOS tablas de forma fija:

- **diario**  : una fila por (fecha, red)  -> métricas de cuenta.
- **posts**   : una fila por publicación   -> métricas de la publicación.

Y, sobre todo, es el único sitio que IMPONE la regla de los nulos: si una red no
publica una métrica (ver `config.SOPORTE_METRICA_SOCIAL`), la casilla queda a
NaN aunque el conector haya escrito un 0. Así un total agregado nunca suma un
cero falso, y `total_comparable()` puede decir qué redes quedan fuera.
"""
from __future__ import annotations

import pandas as pd

from src import config

# Orden fijo de columnas. Las páginas y la caché parquet dependen de él.
COLUMNAS_DIARIO = ["fecha", "red"] + list(config.METRICAS_SOCIAL) + ["seguidores_total"]

COLUMNAS_POSTS = [
    "red", "post_id", "fecha", "tipo", "titulo", "url", "miniatura",
] + list(config.METRICAS_POST)


def esquema_diario_vacio() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNAS_DIARIO})


def esquema_posts_vacio() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNAS_POSTS})


def _normalizar(df: pd.DataFrame, columnas: list[str], metricas: dict[str, str],
                ambito: str) -> pd.DataFrame:
    """Deja el df en el esquema fijo, con tipos correctos y la regla de nulos
    aplicada. Común a diario y posts."""
    if df is None or df.empty:
        return (esquema_posts_vacio() if ambito == "post" else esquema_diario_vacio())

    d = df.copy()

    # Columnas que falten -> las crea vacías; sobrantes -> se descartan.
    for c in columnas:
        if c not in d.columns:
            d[c] = pd.NA
    d = d[columnas]

    if "fecha" in d.columns:
        d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce").dt.date

    # Métricas a numérico. `seguidores_total` es métrica de stock, no de flujo,
    # así que no está en `metricas` pero también es numérica.
    numericas = list(metricas) + (["seguidores_total"] if ambito != "post" else [])
    for c in numericas:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")

    # --- La regla: nulo donde la red no publica el dato ---------------------- #
    # Se aplica DESPUÉS de convertir a numérico, para pisar cualquier 0 que un
    # conector haya escrito por defecto en una casilla que no le corresponde.
    for metrica in metricas:
        if metrica not in d.columns:
            continue
        no_soportada = d["red"].map(
            lambda r: not config.soporta_metrica(metrica, r, ambito)
        )
        d.loc[no_soportada, metrica] = pd.NA
        # Re-tipar: la asignación de pd.NA puede volver la columna a object.
        d[metrica] = pd.to_numeric(d[metrica], errors="coerce")

    return d.reset_index(drop=True)


def normalizar_diario(df: pd.DataFrame) -> pd.DataFrame:
    """Lleva métricas diarias de cuenta al esquema fijo y aplica la regla de nulos."""
    d = _normalizar(df, COLUMNAS_DIARIO, config.METRICAS_SOCIAL, "diario")
    return d.sort_values(["fecha", "red"], na_position="last").reset_index(drop=True)


def normalizar_posts(df: pd.DataFrame) -> pd.DataFrame:
    """Lleva métricas por publicación al esquema fijo y aplica la regla de nulos."""
    d = _normalizar(df, COLUMNAS_POSTS, config.METRICAS_POST, "post")
    return d.sort_values("fecha", ascending=False, na_position="last").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Agregados
# --------------------------------------------------------------------------- #

def interacciones(df: pd.DataFrame) -> pd.Series:
    """Likes + comentarios + compartidos, fila a fila.

    Las 3 las publican las 4 redes, así que el agregado es comparable. Se suma
    con `min_count=1`: si las 3 fueran nulas el resultado es nulo, no 0.
    """
    cols = [c for c in config.METRICAS_INTERACCION if c in df.columns]
    if not cols:
        return pd.Series([pd.NA] * len(df), index=df.index, dtype="Float64")
    return df[cols].sum(axis=1, min_count=1)


def totales_por_red(diario: pd.DataFrame) -> pd.DataFrame:
    """Una fila por red con el total del periodo de cada métrica.

    Las métricas de flujo se suman; `seguidores_total` es un stock, así que se
    toma el ÚLTIMO valor del periodo (sumarlo no significaría nada).
    """
    if diario is None or diario.empty:
        return pd.DataFrame()

    d = diario.copy()
    agregados = {m: (m, lambda s: s.sum(min_count=1)) for m in config.METRICAS_SOCIAL
                 if m in d.columns}

    filas = []
    for red, g in d.groupby("red", sort=False):
        fila = {"red": red}
        for metrica in agregados:
            fila[metrica] = g[metrica].sum(min_count=1)
        if "seguidores_total" in g.columns:
            ultimos = g.sort_values("fecha")["seguidores_total"].dropna()
            fila["seguidores_total"] = ultimos.iloc[-1] if len(ultimos) else pd.NA
        fila["interacciones"] = sum(
            fila[m] for m in config.METRICAS_INTERACCION
            if m in fila and pd.notna(fila[m])
        ) or pd.NA
        filas.append(fila)

    res = pd.DataFrame(filas)
    # Orden estable: el de config.REDES_SOCIAL.
    orden = {r: i for i, r in enumerate(config.REDES_SOCIAL)}
    res["_o"] = res["red"].map(lambda r: orden.get(r, 99))
    return res.sort_values("_o").drop(columns="_o").reset_index(drop=True)


def total_comparable(diario: pd.DataFrame, metrica: str,
                     ambito: str = "diario") -> tuple[float | None, list[str]]:
    """Total de `metrica` sumando SOLO las redes que la publican.

    Devuelve `(total, redes_excluidas)`. Si `redes_excluidas` no está vacía, la
    UI debe decirlo: el número no cubre todas las redes. Un total de None
    significa que ninguna red del periodo publica la métrica.
    """
    excluidas = config.redes_sin_metrica(metrica, ambito)
    if diario is None or diario.empty or metrica not in diario.columns:
        return None, excluidas
    total = diario[metrica].sum(min_count=1)
    return (None if pd.isna(total) else float(total)), excluidas


def tasa_engagement(posts: pd.DataFrame) -> pd.Series:
    """Interacciones / visualizaciones de cada publicación.

    Se usa `visualizaciones` como denominador (no impresiones) porque es la
    única base que publican las 4 redes. Nulo cuando no hay denominador.
    """
    if posts is None or posts.empty:
        return pd.Series(dtype="Float64")
    inter = interacciones(posts)
    base = pd.to_numeric(posts.get("visualizaciones"), errors="coerce")
    return (inter / base.where(base > 0)).astype("Float64")


def serie_diaria(diario: pd.DataFrame, metrica: str) -> pd.DataFrame:
    """Serie (fecha, red, valor) de una métrica, solo con las redes que la dan.

    Las redes sin el dato se omiten en vez de dibujarse como una línea a cero,
    que es lo que haría parecer que la red no rinde cuando lo que pasa es que no
    informa.
    """
    if diario is None or diario.empty or metrica not in diario.columns:
        return pd.DataFrame(columns=["fecha", "red", "valor"])
    d = diario[["fecha", "red", metrica]].rename(columns={metrica: "valor"})
    d = d[d["valor"].notna()]
    return (d.groupby(["fecha", "red"], as_index=False)["valor"]
            .sum(min_count=1)
            .sort_values("fecha"))


def crecimiento_seguidores(diario: pd.DataFrame) -> pd.DataFrame:
    """Serie acumulada de seguidores ganados en el periodo, por red.

    Se acumulan los NUEVOS seguidores en vez de dibujar `seguidores_total`,
    porque el total absoluto de cada red es de órdenes de magnitud distintos y
    en un mismo gráfico aplasta a las redes pequeñas.
    """
    if diario is None or diario.empty or "seguidores_nuevos" not in diario.columns:
        return pd.DataFrame(columns=["fecha", "red", "acumulado"])
    d = (diario[["fecha", "red", "seguidores_nuevos"]]
         .dropna(subset=["seguidores_nuevos"])
         .groupby(["fecha", "red"], as_index=False)["seguidores_nuevos"].sum())
    d = d.sort_values("fecha")
    d["acumulado"] = d.groupby("red")["seguidores_nuevos"].cumsum()
    return d
