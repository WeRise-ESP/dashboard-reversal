"""Página: Google Analytics 4 — dashboard de marketing (adquisición, engagement, conversión)."""
from __future__ import annotations

import streamlit as st

from src.data import loader, metrics
from src.ui import components as ui
from src.ui.theme import aplicar_tema, num, pct

st.set_page_config(page_title="Google Analytics · Reversal", page_icon="📈", layout="wide")
aplicar_tema()

desde, hasta, etq = ui.selector_periodo()
datos = loader.cargar_todo(desde, hasta)
ui.aviso_origenes(datos.origenes)

ui.cabecera("Google Analytics 4",
            f"Analítica de todo el sitio reversal.institute · {etq}")

df = datos.ga4
ex = datos.ga4_extra or {}
tot = ex.get("totales", {})
if df.empty or not tot:
    st.warning("No hay datos de GA4.")
    st.stop()


def dur(seg: float) -> str:
    seg = int(seg or 0)
    return f"{seg // 60}m {seg % 60:02d}s"


# --------------------------------------------------------------------------- #
# Bloque 1 — Adquisición
# --------------------------------------------------------------------------- #
st.subheader("Adquisición")
c1, c2, c3, c4 = st.columns(4)
ui.kpi(c1, "Sesiones", num(tot["sesiones"]))
ui.kpi(c2, "Usuarios", num(tot["usuarios"]), f"{num(tot['usuarios_nuevos'])} nuevos")
ui.kpi(c3, "% Usuarios nuevos", pct(tot["pct_nuevos"]), "Nuevos / totales")
ui.kpi(c4, "Páginas / sesión", num(tot["paginas_sesion"], 2))

st.write("")

# --------------------------------------------------------------------------- #
# Bloque 2 — Engagement y conversión
# --------------------------------------------------------------------------- #
st.subheader("Engagement y conversión")
c5, c6, c7, c8 = st.columns(4)
ui.kpi(c5, "Tasa de engagement", pct(tot["engagement_rate"]),
       "Sesiones con interacción",
       estado="ok" if tot["engagement_rate"] >= 0.5 else "warn")
ui.kpi(c6, "Duración media sesión", dur(tot["duracion_media"]))
ui.kpi(c7, "Conversiones", num(tot["conversiones"]), "Eventos clave (key events)")
ui.kpi(c8, "Tasa de conversión", pct(tot["tasa_conversion"], 2),
       "Conversiones / sesiones",
       estado="ok" if tot["tasa_conversion"] >= 0.02 else "warn")

st.divider()

# --------------------------------------------------------------------------- #
# Evolución diaria + reparto
# --------------------------------------------------------------------------- #
col_izq, col_der = st.columns([0.62, 0.38])
with col_izq:
    st.subheader("Evolución diaria")
    serie = df.groupby("fecha", as_index=False).agg(
        Sesiones=("sesiones", "sum"), Usuarios=("usuarios", "sum"))
    serie_m = serie.melt("fecha", var_name="métrica", value_name="valor")
    ui.linea_temporal(serie_m, x="fecha", y="valor", color="métrica",
                      titulo="", y_label="")
with col_der:
    st.subheader("Nuevos vs recurrentes")
    nuevos = ex.get("nuevos")
    if nuevos is not None and not nuevos.empty:
        ui.donut(nuevos, nombres="tipo", valores="sesiones", titulo="")

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Sesiones por canal")
    por_canal = (df.groupby("canal", as_index=False)["sesiones"].sum()
                   .sort_values("sesiones"))
    ui.barras(por_canal, x="sesiones", y="canal", color=None, titulo="", orientacion="h")
with col_b:
    st.subheader("Dispositivos")
    disp = ex.get("dispositivo")
    if disp is not None and not disp.empty:
        ui.donut(disp, nombres="dispositivo", valores="sesiones", titulo="")

st.divider()

# --------------------------------------------------------------------------- #
# Rendimiento por canal (tabla con engagement y conversión)
# --------------------------------------------------------------------------- #
st.subheader("Rendimiento por canal")
canal = df.groupby("canal", as_index=False).agg(
    sesiones=("sesiones", "sum"),
    usuarios=("usuarios", "sum"),
    usuarios_nuevos=("usuarios_nuevos", "sum"),
    sesiones_activas=("sesiones_activas", "sum"),
    conversiones=("conversiones", "sum"),
).sort_values("sesiones", ascending=False)
canal["engagement_rate"] = canal["sesiones_activas"] / canal["sesiones"].where(canal["sesiones"] > 0, 1)
canal["tasa_conv"] = canal["conversiones"] / canal["sesiones"].where(canal["sesiones"] > 0, 1)
canal = metrics.con_fila_total(canal, "canal", ratios={
    "engagement_rate": lambda s, _: (s["sesiones_activas"] / s["sesiones"]) if s["sesiones"] else 0,
    "tasa_conv": lambda s, _: (s["conversiones"] / s["sesiones"]) if s["sesiones"] else 0,
})
ui.tabla(canal, [
    {"key": "canal", "label": "Canal", "align": "l"},
    {"key": "sesiones", "label": "Sesiones", "fmt": lambda v: num(v, 0)},
    {"key": "usuarios", "label": "Usuarios", "fmt": lambda v: num(v, 0)},
    {"key": "usuarios_nuevos", "label": "Nuevos", "fmt": lambda v: num(v, 0)},
    {"key": "engagement_rate", "label": "Engagement", "fmt": lambda v: pct(v, 1)},
    {"key": "conversiones", "label": "Conversiones", "fmt": lambda v: num(v, 0)},
    {"key": "tasa_conv", "label": "Tasa conv.", "fmt": lambda v: pct(v, 2), "bold": True},
], etiqueta_col="canal")

# --------------------------------------------------------------------------- #
# Top landing pages
# --------------------------------------------------------------------------- #
st.subheader("Top landing pages")
paginas = ex.get("paginas")
if paginas is not None and not paginas.empty:
    pg = metrics.con_fila_total(paginas.copy(), "pagina", ratios={
        "engagement_rate": lambda s, df_: (df_["engagement_rate"] * df_["sesiones"]).sum()
        / df_["sesiones"].sum() if df_["sesiones"].sum() else 0,
    })
    ui.tabla(pg, [
        {"key": "pagina", "label": "Landing page", "align": "l"},
        {"key": "sesiones", "label": "Sesiones", "fmt": lambda v: num(v, 0)},
        {"key": "usuarios", "label": "Usuarios", "fmt": lambda v: num(v, 0)},
        {"key": "engagement_rate", "label": "Engagement", "fmt": lambda v: pct(v, 1)},
        {"key": "conversiones", "label": "Conversiones", "fmt": lambda v: num(v, 0), "bold": True},
    ], etiqueta_col="pagina")

st.caption(
    "Tráfico de todo el sitio `reversal.institute` (property 542276987). Adquisición "
    "→ engagement → conversión. Las conversiones son los eventos clave marcados en GA4. "
    "Los leads/matrículas del embudo comercial se miden en HubSpot (ver página *Leads*)."
)
