"""
Utilidades comunes a los conectores.

Cada conector devuelve un `ResultadoConector` con el DataFrame y el origen de
los datos ("api", "cache" o "sample") para que la UI pueda mostrar un aviso
claro de qué está viendo el usuario.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ResultadoConector:
    df: pd.DataFrame
    origen: str  # "api" | "cache" | "sample"
    detalle: str = ""


def _leer_secreto(seccion: str) -> dict | None:
    """Lee una sección de st.secrets sin romper si no existe secrets.toml."""
    try:
        import streamlit as st

        if seccion in st.secrets:
            return dict(st.secrets[seccion])
    except Exception:
        pass
    return None


def guardar_cache(df: pd.DataFrame, nombre: str) -> None:
    if df is None or df.empty:
        return
    try:
        df.to_parquet(CACHE_DIR / f"{nombre}.parquet", index=False)
    except Exception:
        # Fallback a CSV si no hay pyarrow.
        df.to_csv(CACHE_DIR / f"{nombre}.csv", index=False)


def leer_cache(nombre: str) -> pd.DataFrame | None:
    pq = CACHE_DIR / f"{nombre}.parquet"
    csv = CACHE_DIR / f"{nombre}.csv"
    try:
        if pq.exists():
            return pd.read_parquet(pq)
        if csv.exists():
            return pd.read_csv(csv, parse_dates=["fecha"], dayfirst=False,
                               infer_datetime_format=True)
    except Exception:
        return None
    return None
