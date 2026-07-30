"""
Tema visual y utilidades de formato compartidas por todas las páginas.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.config import SIMBOLO_MONEDA, TEMA

_ASSETS = Path(__file__).resolve().parents[2] / "assets"

CSS = f"""
<style>
    .block-container {{ padding-top: 2rem; padding-bottom: 3rem; }}
    [data-testid="stMetricValue"] {{ font-size: 1.7rem; }}
    .kpi-card {{
        background: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,0.15);
        border-left: 4px solid {TEMA.primario};
        border-radius: 12px; padding: 1rem 1.2rem;
    }}
    .kpi-card h3 {{ font-size: .8rem; color: #888; margin: 0 0 .3rem 0;
                    text-transform: uppercase; letter-spacing: .04em; }}
    .kpi-card .val {{ font-size: 1.8rem; font-weight: 700; line-height: 1.1; }}
    .kpi-card .sub {{ font-size: .8rem; color: #888; }}
    .badge {{ display:inline-block; padding:.15rem .5rem; border-radius:999px;
              font-size:.72rem; font-weight:600; }}
    .badge-ok  {{ background: rgba(24,168,110,.15); color:{TEMA.verde_ok}; }}
    .badge-warn{{ background: rgba(192,137,46,.15); color:{TEMA.ambar_riesgo}; }}
    .badge-off {{ background: rgba(178,64,46,.15);  color:{TEMA.rojo_off}; }}
</style>
"""


def aplicar_tema() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    # Logo de marca de Reversal en la parte superior del sidebar (todas las hojas).
    try:
        st.logo(str(_ASSETS / "reversal-logo.svg"), size="large",
                icon_image=str(_ASSETS / "reversal-icon.png"),
                link="https://reversal.institute")
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
# Formateadores
# --------------------------------------------------------------------------- #
def eur(x: float, dec: int = 0) -> str:
    try:
        return f"{x:,.{dec}f} {SIMBOLO_MONEDA}".replace(",", "·").replace(".", ",").replace("·", ".")
    except Exception:
        return f"0 {SIMBOLO_MONEDA}"


def pct(x: float, dec: int = 1) -> str:
    try:
        return f"{x*100:,.{dec}f}%".replace(".", ",")
    except Exception:
        return "0%"


def num(x: float, dec: int = 0) -> str:
    try:
        return f"{x:,.{dec}f}".replace(",", "·").replace(".", ",").replace("·", ".")
    except Exception:
        return "0"


def badge_origen(origen: str) -> str:
    etiqueta = {"api": "En vivo (API)", "cache": "Caché", "csv": "CSV importado",
                "historico": "Histórico propio", "sample": "Ejemplo"}.get(origen, origen)
    clase = {"api": "badge-ok", "cache": "badge-warn", "csv": "badge-warn",
             "historico": "badge-warn", "sample": "badge-off"}.get(origen, "badge-off")
    return f'<span class="badge {clase}">{etiqueta}</span>'


# --------------------------------------------------------------------------- #
# Formateadores que distinguen NULO de CERO
#
# `num()` y `pct()` devuelven "0" ante un valor inválido o nulo. Para el social
# orgánico eso es inaceptable: un nulo significa «esta red no publica el dato» y
# pintarlo como 0 haría creer que la red rinde cero. Estas variantes muestran "—".
#
# Se añaden en vez de cambiar `num()`/`pct()` para no alterar lo que ya ven las
# páginas de Ads/GA4/HubSpot, donde un dato ausente sí es realmente un cero.
# --------------------------------------------------------------------------- #
def _es_nulo(x) -> bool:
    if x is None:
        return True
    try:
        import pandas as pd
        return bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


def num_o_guion(x, dec: int = 0) -> str:
    """Número formateado, o "—" si el valor es nulo (dato no publicado)."""
    return "—" if _es_nulo(x) else num(x, dec)


def pct_o_guion(x, dec: int = 1) -> str:
    """Porcentaje formateado, o "—" si el valor es nulo."""
    return "—" if _es_nulo(x) else pct(x, dec)
