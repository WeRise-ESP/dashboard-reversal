"""
Esquema normalizado de la demografía de audiencia.

Formato largo: una fila por (fecha, red, dimensión, categoría). Es lo que
permite que redes con dimensiones distintas —Instagram da edad y género,
LinkedIn da cargo y sector— convivan en la misma tabla sin columnas vacías.

⚠️ LA UNIDAD NO ES LA MISMA EN TODAS LAS REDES, y es la trampa principal de
este módulo:

- Instagram cuenta PERSONAS que te siguen.
- YouTube da el PORCENTAJE de visualizaciones por tramo.

Son poblaciones distintas y magnitudes distintas. Un gráfico que las junte
está sumando peras y manzanas sin avisar, así que la unidad viaja pegada al
dato en su propia columna y la UI la escribe dentro del bloque.

- Facebook NO aparece: Meta retiró la demografía de Páginas en 2025. Los cinco
  nombres documentados responden «must be a valid insights metric».
- LinkedIn no publica edad ni género en ninguna versión de su API.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

COLUMNAS = ["fecha", "red", "dimension", "categoria", "valor", "unidad"]

# Qué mide cada red. Facebook no está porque no publica demografía.
UNIDAD_POR_RED = {
    "Instagram": "seguidores",
    "YouTube": "pct_visualizaciones",
    "LinkedIn": "seguidores",
}

_ETIQUETAS = {
    "seguidores": "seguidores",
    "pct_visualizaciones": "% de las visualizaciones",
}


def etiqueta_unidad(unidad: str) -> str:
    """Texto legible de la unidad, para escribirlo DENTRO del bloque."""
    return _ETIQUETAS.get(unidad, unidad)


def esquema_vacio() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNAS})


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Deja el df en el esquema fijo, con tipos correctos y la unidad puesta.

    La unidad se deduce de la red y se PISA siempre: que la escriba un conector
    es opcional, que sea correcta no.
    """
    if df is None or df.empty:
        return esquema_vacio()

    d = df.copy()
    for c in COLUMNAS:
        if c not in d.columns:
            d[c] = pd.NA
    d = d[COLUMNAS]

    d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce").dt.date
    d["valor"] = pd.to_numeric(d["valor"], errors="coerce")
    d["unidad"] = d["red"].map(UNIDAD_POR_RED)

    return d.reset_index(drop=True)


def ultima_foto(df: pd.DataFrame, red: str, hasta: date) -> pd.DataFrame:
    """La captura MÁS RECIENTE de una red, en o antes de `hasta`.

    La demografía es una foto acumulada, no un flujo: sumar dos capturas
    contaría a la misma persona dos veces. Por eso se toma una sola fecha.
    """
    if df is None or df.empty:
        return esquema_vacio()
    d = df[(df["red"] == red) & df["fecha"].notna()]
    d = d[d["fecha"] <= hasta]
    if d.empty:
        return esquema_vacio()
    return d[d["fecha"] == d["fecha"].max()].reset_index(drop=True)
