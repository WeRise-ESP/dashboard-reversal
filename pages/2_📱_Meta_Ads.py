"""Página: Meta Ads — dashboard de paid media (volumen, coste, eficiencia, embudo)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import config
from src.data import loader, metrics
from src.ui import components as ui
from src.ui.theme import aplicar_tema, eur, num, pct

st.set_page_config(page_title="Meta Ads · Reversal", page_icon="📱", layout="wide")
aplicar_tema()

desde, hasta, etq = ui.selector_periodo()
datos = loader.cargar_todo(desde, hasta)
ui.aviso_origenes(datos.origenes)

ui.cabecera("Meta Ads", f"Cuenta {config.META_AD_ACCOUNT_ID} · {etq}")

df = datos.meta
if df.empty:
    st.warning("No hay datos de Meta Ads.")
    st.stop()

r = metrics.resumen_plataforma(df).iloc[0]
canal = config.canal_por_plataforma("Meta Ads")  # "Paid Social (Meta)"
leads_ch = datos.leads[datos.leads["fuente"] == canal]
n_leads = len(leads_ch)
n_mat = int(leads_ch["es_matricula"].sum()) if n_leads else 0
resultados = int(r["conversiones"])  # leads web reportados por Meta
cpl = r["coste"] / n_leads if n_leads else 0
coste_result = r["coste"] / resultados if resultados else 0
conv_rate = resultados / r["clics"] if r["clics"] else 0

# --------------------------------------------------------------------------- #
# Volumen y coste
# --------------------------------------------------------------------------- #
st.subheader("Volumen y coste")
c1, c2, c3, c4 = st.columns(4)
ui.kpi(c1, "Inversión", eur(r["coste"]))
ui.kpi(c2, "Impresiones", num(r["impresiones"]))
ui.kpi(c3, "Clics", num(r["clics"]), f"CTR {pct(r['ctr'],2)}")
ui.kpi(c4, "CPM", eur(r["cpm"], 2))

st.write("")

# --------------------------------------------------------------------------- #
# Eficiencia y resultado
# --------------------------------------------------------------------------- #
st.subheader("Eficiencia y resultado")
c5, c6, c7, c8 = st.columns(4)
ui.kpi(c5, "CPC medio", eur(r["cpc"], 2))
ui.kpi(c6, "Resultados (leads web)", num(resultados),
       f"Tasa {pct(conv_rate,2)} sobre clics", estado="ok" if resultados else "off")
ui.kpi(c7, "Coste/resultado", eur(coste_result, 2), "Inversión / resultados Meta")
ui.kpi(c8, "CPL real", eur(cpl, 2), f"{num(n_leads)} leads HubSpot",
       estado="ok" if 0 < cpl <= config.CPL_OBJETIVO else "warn")

# Contraste plataforma vs HubSpot (atribución).
brecha = abs(resultados - n_leads) / max(n_leads, 1)
st.info(
    f"Meta atribuye **{resultados} resultados** (leads web); HubSpot registra "
    f"**{n_leads} leads** de {canal}. "
    + ("La atribución es coherente entre ambas fuentes ✅."
       if brecha <= 0.3 else
       "Hay brecha: revisa el píxel y la Conversions API (ver *Tracking & Atribución*).")
)

st.divider()

# --------------------------------------------------------------------------- #
# Embudo + evolución
# --------------------------------------------------------------------------- #
col_izq, col_der = st.columns([0.42, 0.58])
with col_izq:
    st.subheader("Embudo de captación")
    emb = pd.DataFrame({
        "etapa": ["Impresiones", "Clics", "Leads", "Matrículas"],
        "leads": [int(r["impresiones"]), int(r["clics"]), n_leads, n_mat],
    })
    ui.embudo_chart(emb)
    st.caption("Leads y matrículas de HubSpot atribuidos al canal Paid Social.")
with col_der:
    st.subheader("Inversión y clics diarios")
    serie = df.groupby("fecha", as_index=False).agg(
        Inversión=("coste", "sum"), Clics=("clics", "sum"))
    ui.linea_temporal(serie.melt("fecha", var_name="métrica", value_name="valor"),
                      x="fecha", y="valor", color="métrica", titulo="", y_label="")

st.divider()

# --------------------------------------------------------------------------- #
# Rendimiento por campaña
# --------------------------------------------------------------------------- #
st.subheader("Rendimiento por campaña")
camp = metrics.enriquecer_campanas_con_hubspot(metrics.resumen_campana(df), datos.leads)
camp = metrics.reconciliar_leads_canal(camp, datos.leads, canal)
ui.barras(camp, x="coste", y="campana", color=None,
          titulo="Inversión por campaña", orientacion="h")

tabla_camp = metrics.con_fila_total(
    camp[["campana", "impresiones", "clics", "ctr", "cpc", "coste", "leads", "matriculas"]].copy(),
    "campana", ratios={
        "ctr": lambda s, _: (s["clics"] / s["impresiones"]) if s["impresiones"] else 0,
        "cpc": lambda s, _: (s["coste"] / s["clics"]) if s["clics"] else 0,
    })
ui.tabla(tabla_camp, [
    {"key": "campana", "label": "Campaña", "align": "l"},
    {"key": "impresiones", "label": "Impr.", "fmt": lambda v: num(v, 0)},
    {"key": "clics", "label": "Clics", "fmt": lambda v: num(v, 0)},
    {"key": "ctr", "label": "CTR", "fmt": lambda v: pct(v, 2)},
    {"key": "cpc", "label": "CPC", "fmt": lambda v: eur(v, 2)},
    {"key": "coste", "label": "Inversión", "fmt": lambda v: eur(v, 0)},
    {"key": "leads", "label": "Leads", "fmt": lambda v: num(v, 0)},
    {"key": "matriculas", "label": "Matrículas", "fmt": lambda v: num(v, 0)},
], etiqueta_col="campana")

st.divider()

# --------------------------------------------------------------------------- #
# Evolución semanal
# --------------------------------------------------------------------------- #
_COLS_SEM = ["semana_label", "impresiones", "clics", "ctr", "cpc", "coste",
             "conversiones", "leads", "matriculas", "cpl"]


def tabla_semanal(sem, conv_label="Result."):
    sem = metrics.con_fila_total(sem[_COLS_SEM].copy(), "semana_label", ratios={
        "ctr": lambda s, _: (s["clics"] / s["impresiones"]) if s["impresiones"] else 0,
        "cpc": lambda s, _: (s["coste"] / s["clics"]) if s["clics"] else 0,
        "cpl": lambda s, _: (s["coste"] / s["leads"]) if s["leads"] else 0,
    })
    ui.tabla(sem, [
        {"key": "semana_label", "label": "Semana", "align": "l"},
        {"key": "impresiones", "label": "Impr.", "fmt": lambda v: num(v, 0)},
        {"key": "clics", "label": "Clics", "fmt": lambda v: num(v, 0)},
        {"key": "ctr", "label": "CTR", "fmt": lambda v: pct(v, 2)},
        {"key": "cpc", "label": "CPC", "fmt": lambda v: eur(v, 2)},
        {"key": "coste", "label": "Inversión", "fmt": lambda v: eur(v, 0)},
        {"key": "conversiones", "label": conv_label, "fmt": lambda v: num(v, 0)},
        {"key": "leads", "label": "Leads", "fmt": lambda v: num(v, 0)},
        {"key": "matriculas", "label": "Matríc.", "fmt": lambda v: num(v, 0)},
        {"key": "cpl", "label": "CPL", "fmt": lambda v: eur(v, 2), "bold": True},
    ], etiqueta_col="semana_label")


st.subheader("Evolución semanal")
sem = metrics.resumen_semanal(df, datos.leads, canal)
if not sem.empty:
    tabla_semanal(sem)
    st.caption(
        "Cada fila es una semana (lun–dom), con datos **diarios reales vía API** "
        "(se refrescan solos). Las semanas se acumulan conforme avanza la campaña."
    )

st.divider()

# --------------------------------------------------------------------------- #
# Evolución semanal por campaña — mismo formato, con filtro de campaña arriba
# --------------------------------------------------------------------------- #
st.subheader("Evolución semanal por campaña")
campanas = (df.groupby("campana")["coste"].sum()
            .sort_values(ascending=False).index.tolist())
sel = st.selectbox("Campaña", campanas, key="evol_camp_meta")
semc = metrics.resumen_semanal(df, datos.leads, canal, campana=sel)
if not semc.empty:
    tabla_semanal(semc)
    st.caption(f"Evolución semanal de **{sel}** (leads casados por nombre en HubSpot).")
else:
    st.info("Sin datos para esa campaña en el periodo.")
