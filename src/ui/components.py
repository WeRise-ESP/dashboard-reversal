"""
Componentes reutilizables de UI: cabecera, selector de periodo, tarjetas KPI,
avisos de origen de datos y helpers de gráficos con Plotly.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import COLOR_PLATAFORMA, TEMA
from src.ui.theme import badge_origen, eur, num, pct


import base64 as _base64
from pathlib import Path as _Path

_LOGO_SVG = _Path(__file__).resolve().parents[2] / "assets" / "reversal-logo.svg"


@st.cache_data(show_spinner=False)
def _logo_datauri() -> str:
    """SVG del logo como data-URI para incrustarlo en un <img> sin que el
    <style> interno del SVG se filtre como texto."""
    try:
        b64 = _base64.b64encode(_LOGO_SVG.read_bytes()).decode()
        return f"data:image/svg+xml;base64,{b64}"
    except Exception:  # noqa: BLE001
        return ""


def cabecera(titulo: str, subtitulo: str = "") -> None:
    col1, col2 = st.columns([0.65, 0.35])
    with col1:
        st.title(titulo)
        if subtitulo:
            st.caption(subtitulo)
    with col2:
        uri = _logo_datauri()
        if uri:
            st.markdown(
                f'<div style="text-align:right;margin-top:.6rem;">'
                f'<img src="{uri}" alt="Reversal" style="width:200px;max-width:100%;height:auto;"></div>'
                '<div style="text-align:right;color:#888;font-size:.72rem;margin-top:.15rem;'
                'text-transform:uppercase;letter-spacing:.04em;">Dashboard de marketing</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("Reversal Institute")
            st.caption("Dashboard de marketing")


def selector_periodo(default: int = 30):
    """Devuelve (desde, hasta, etiqueta).

    Dos modos: **Período predefinido** (Hoy, Ayer, Últimos N días, Este mes,
    Mes pasado) o **Rango personalizado** (fecha de inicio y fin)."""
    from datetime import date, timedelta

    hoy = date.today()
    modo = st.sidebar.radio("Modo de fecha",
                            ["Período predefinido", "Rango personalizado"])

    if modo == "Rango personalizado":
        desde = st.sidebar.date_input("Desde", value=hoy - timedelta(days=7),
                                      max_value=hoy, format="DD/MM/YYYY")
        hasta = st.sidebar.date_input("Hasta", value=hoy, min_value=desde,
                                      max_value=hoy, format="DD/MM/YYYY")
        if hasta < desde:
            desde, hasta = hasta, desde
        return desde, hasta, f"{desde.strftime('%d/%m/%Y')} – {hasta.strftime('%d/%m/%Y')}"

    # --- Período predefinido ---
    primero_mes = hoy.replace(day=1)
    fin_mes_pasado = primero_mes - timedelta(days=1)
    inicio_mes_pasado = fin_mes_pasado.replace(day=1)
    presets = {
        "Hoy": (hoy, hoy),
        "Ayer": (hoy - timedelta(days=1), hoy - timedelta(days=1)),
        "Últimos 7 días": (hoy - timedelta(days=6), hoy),
        "Últimos 14 días": (hoy - timedelta(days=13), hoy),
        "Últimos 30 días": (hoy - timedelta(days=29), hoy),
        "Últimos 90 días": (hoy - timedelta(days=89), hoy),
        "Este mes": (primero_mes, hoy),
        "Mes pasado": (inicio_mes_pasado, fin_mes_pasado),
    }
    nombres = list(presets.keys())
    sel = st.sidebar.selectbox("Período", nombres,
                               index=nombres.index("Últimos 30 días"))
    desde, hasta = presets[sel]
    return desde, hasta, sel


def aviso_origenes(origenes: dict) -> None:
    """Muestra en el sidebar de qué fuente vienen los datos de cada plataforma."""
    from src import config

    st.sidebar.markdown("**Origen de los datos**")
    for plataforma, origen in origenes.items():
        st.sidebar.markdown(
            f"{plataforma}: {badge_origen(origen)}", unsafe_allow_html=True
        )
    if st.sidebar.button("🔄 Actualizar ahora", width='stretch'):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.caption(
        f"HubSpot se refresca cada {config.CACHE_TTL_HUBSPOT // 60} min · "
        f"Ads/GA4 cada {config.CACHE_TTL_ADS // 60} min. "
        "Usa «Actualizar ahora» para forzar."
    )
    if all(o == "sample" for o in origenes.values()):
        st.sidebar.info(
            "Estás viendo **datos de ejemplo**. Configura credenciales en "
            "`.streamlit/secrets.toml` o rellena la caché para ver datos reales."
        )


_CSS_TABLA = f"""
<style>
.rv-tabla-wrap {{ overflow-x:auto; margin-bottom:.5rem; }}
.rv-tabla {{ border-collapse:collapse; width:100%; font-size:.9rem; }}
.rv-tabla th {{ padding:.5rem .7rem; color:#888; font-weight:600; white-space:nowrap;
    text-transform:uppercase; letter-spacing:.03em; font-size:.72rem;
    border-bottom:2px solid {TEMA.primario}33; }}
.rv-tabla td {{ padding:.45rem .7rem; white-space:nowrap;
    border-bottom:1px solid rgba(128,128,128,.12); }}
.rv-tabla tr.rv-total td {{ border-top:2px solid {TEMA.primario};
    border-bottom:none; font-weight:700; }}
.rv-tabla td.rv-bold, .rv-tabla th.rv-bold {{ font-weight:700; }}
@media (max-width: 640px) {{
    .rv-tabla {{ font-size:.78rem; }}
    .rv-tabla th, .rv-tabla td {{ padding:.35rem .45rem; }}
}}
</style>
"""


def resumen_ejecutivo(texto: str) -> None:
    """Caja destacada para el resumen ejecutivo (texto en markdown)."""
    import re
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"`(.+?)`", r"<code>\1</code>", texto)
    st.markdown(
        f"""<div style="background:{TEMA.verde_tint}; border-left:4px solid {TEMA.primario};
            border-radius:10px; padding:.8rem 1.1rem; margin:.2rem 0 1rem 0;
            color:{TEMA.texto}; font-size:.95rem; line-height:1.5;">
            <span style="text-transform:uppercase; letter-spacing:.05em; font-size:.7rem;
            font-weight:700; color:{TEMA.primario};">Resumen ejecutivo</span><br>{texto}
            </div>""",
        unsafe_allow_html=True,
    )


def tabla(df: pd.DataFrame, columnas: list[dict], etiqueta_col: str | None = None,
          total_label: str = "TOTAL") -> None:
    """Renderiza un DataFrame como tabla HTML con formato, negrita en la fila
    TOTAL y en las columnas marcadas con `"bold": True`.

    `columnas`: lista de dicts con:
        key   -> nombre de columna en el df
        label -> encabezado a mostrar
        fmt   -> callable(valor)->str (opcional; si no, se muestra tal cual)
        align -> "l" (izquierda) o "r" (derecha, por defecto)
        bold  -> True para poner toda la columna en negrita (opcional)
    """
    if df is None or df.empty:
        st.info("Sin datos.")
        return

    def _al(c):
        return "left" if c.get("align", "r") == "l" else "right"

    th = "".join(
        f'<th class="{"rv-bold" if c.get("bold") else ""}" '
        f'style="text-align:{_al(c)}">{c["label"]}</th>'
        for c in columnas
    )
    filas = []
    for _, row in df.iterrows():
        es_total = bool(etiqueta_col) and str(row.get(etiqueta_col, "")) == total_label
        celdas = []
        for c in columnas:
            v = row.get(c["key"], "")
            if v == "" or v is None:
                txt = ""
            elif c.get("fmt"):
                try:
                    txt = c["fmt"](v)
                except Exception:  # noqa: BLE001
                    txt = str(v)
            else:
                txt = str(v)
            cls = "rv-bold" if c.get("bold") else ""
            celdas.append(f'<td class="{cls}" style="text-align:{_al(c)}">{txt}</td>')
        filas.append(f'<tr class="{"rv-total" if es_total else ""}">{"".join(celdas)}</tr>')
    html = (f'<div class="rv-tabla-wrap"><table class="rv-tabla">'
            f'<thead><tr>{th}</tr></thead><tbody>{"".join(filas)}</tbody></table></div>')
    st.markdown(_CSS_TABLA + html, unsafe_allow_html=True)


def kpi(col, titulo: str, valor: str, sub: str = "", estado: str | None = None) -> None:
    """Tarjeta KPI con borde de color según estado (ok/warn/off)."""
    borde = {"ok": TEMA.verde_ok, "warn": TEMA.ambar_riesgo,
             "off": TEMA.rojo_off}.get(estado, TEMA.primario)
    col.markdown(
        f"""<div class="kpi-card" style="border-left-color:{borde}">
              <h3>{titulo}</h3>
              <div class="val">{valor}</div>
              <div class="sub">{sub}</div>
            </div>""",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Gráficos
# --------------------------------------------------------------------------- #
# Leyenda horizontal DEBAJO del gráfico (para que en móvil no coma ancho y el
# gráfico salga completo). Se aplica solo cuando hay series (color).
_LEG_ABAJO = dict(orientation="h", yanchor="top", y=-0.28, xanchor="center", x=0.5)


def linea_temporal(df: pd.DataFrame, x: str, y: str, color: str | None,
                   titulo: str, y_label: str = "") -> None:
    if df.empty:
        st.info("Sin datos para el periodo seleccionado.")
        return
    fig = px.line(df, x=x, y=y, color=color, markers=True,
                  color_discrete_map=COLOR_PLATAFORMA,
                  color_discrete_sequence=list(TEMA.paleta))
    fig.update_layout(
        title=titulo, height=400 if color else 340,
        margin=dict(l=10, r=10, t=40, b=90 if color else 10),
        legend=_LEG_ABAJO, legend_title="", yaxis_title=y_label, xaxis_title="",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, width='stretch')


def area_apilada(df: pd.DataFrame, x: str, y: str, color: str,
                 titulo: str, y_label: str = "") -> None:
    """Área apilada: la altura total es la suma de todas las series (canales)."""
    if df.empty:
        st.info("Sin datos para el periodo seleccionado.")
        return
    fig = px.area(df, x=x, y=y, color=color,
                  color_discrete_map=COLOR_PLATAFORMA,
                  color_discrete_sequence=list(TEMA.paleta))
    fig.update_layout(
        title=titulo, height=400, margin=dict(l=10, r=10, t=40, b=90),
        legend=_LEG_ABAJO, legend_title="", yaxis_title=y_label, xaxis_title="",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, width='stretch')


def barras(df: pd.DataFrame, x: str, y: str, color: str | None,
           titulo: str, orientacion: str = "v", texto: str | None = None) -> None:
    if df.empty:
        st.info("Sin datos.")
        return
    fig = px.bar(df, x=x, y=y, color=color, orientation=orientacion,
                 text=texto, color_discrete_map=COLOR_PLATAFORMA,
                 color_discrete_sequence=list(TEMA.paleta))
    fig.update_layout(
        title=titulo, height=400 if color else 360,
        margin=dict(l=10, r=10, t=40, b=80 if color else 10),
        legend=_LEG_ABAJO, legend_title="",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, width='stretch')


def embudo_chart(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Sin datos de embudo.")
        return
    fig = go.Figure(go.Funnel(
        y=df["etapa"], x=df["leads"],
        textposition="inside",
        texttemplate="%{value} (%{percentInitial})",
        marker=dict(color=list(TEMA.paleta)),
    ))
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width='stretch')


def donut(df: pd.DataFrame, nombres: str, valores: str, titulo: str) -> None:
    if df.empty:
        st.info("Sin datos.")
        return
    fig = px.pie(df, names=nombres, values=valores, hole=0.55,
                 color_discrete_sequence=list(TEMA.paleta))
    fig.update_layout(
        title=titulo, height=380, margin=dict(l=10, r=10, t=40, b=70),
        legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, width='stretch')
