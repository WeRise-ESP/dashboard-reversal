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

# Exports manuales de las plataformas, ya normalizados al esquema del dashboard.
# Es el nivel que cubre el histórico que las APIs NO dan hacia atrás (sobre todo
# Instagram: `views` con histórico limitado y seguidores solo 30 días).
IMPORT_DIR = Path(__file__).resolve().parents[2] / "data" / "import_social"

# Histórico que acumula `scripts/snapshot_social.py` ejecutándose a diario.
#
# NO es un nivel más de la cascada: es un SUELO que se funde por debajo del
# nivel que gane (ver `social_base.resolver`). La diferencia importa: cuando
# llegue el token de Meta, la API devolverá 30 días de Instagram y el resto del
# histórico tiene que seguir viéndose, no quedar tapado.
HISTORICO_DIR = Path(__file__).resolve().parents[2] / "data" / "historico_social"


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


def leer_csv_importado(nombre: str) -> pd.DataFrame | None:
    """Lee `data/import_social/<nombre>.csv` si existe.

    Devuelve None si no hay fichero o no se puede leer, para que la cascada del
    conector siga al siguiente nivel sin romper la página.
    """
    ruta = IMPORT_DIR / f"{nombre}.csv"
    if not ruta.exists():
        return None
    try:
        return pd.read_csv(ruta)
    except Exception:  # noqa: BLE001
        return None


def leer_historico(nombre: str) -> pd.DataFrame | None:
    """Lee `data/historico_social/<nombre>.csv` si existe.

    Mismo contrato que `leer_csv_importado`: None si no hay fichero o no se
    puede leer, para que el conector siga sin romper la página.
    """
    ruta = HISTORICO_DIR / f"{nombre}.csv"
    if not ruta.exists():
        return None
    try:
        return pd.read_csv(ruta)
    except Exception:  # noqa: BLE001
        return None


def escribir_historico(df: pd.DataFrame, nombre: str) -> Path:
    """Vuelca `df` a `data/historico_social/<nombre>.csv` y devuelve la ruta.

    Escribe el fichero ENTERO: quien llama es responsable de haberlo fusionado
    antes con lo que ya había (`social_base.fusionar`). Los nulos salen como
    celda vacía, que es justo lo que la regla de nulos necesita — un 0 aquí
    significaría «la red lo mide y vale cero».
    """
    HISTORICO_DIR.mkdir(parents=True, exist_ok=True)
    ruta = HISTORICO_DIR / f"{nombre}.csv"
    df.to_csv(ruta, index=False)
    return ruta


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
