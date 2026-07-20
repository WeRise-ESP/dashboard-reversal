"""Página: Google Ads — dashboard de paid media (volumen, coste, eficiencia, embudo)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import config
from src.data import loader, metrics
from src.ui import components as ui
from src.ui.theme import aplicar_tema, eur, num, pct

st.set_page_config(page_title="Google Ads · Reversal", page_icon="🔍", layout="wide")
aplicar_tema()

desde, hasta, etq = ui.selector_periodo()
datos = loader.cargar_todo(desde, hasta)
ui.aviso_origenes(datos.origenes)

ui.cabecera("Google Ads", f"Cuenta {config.GOOGLE_ADS_CUSTOMER_ID} · {etq}")

df = datos.google
if df.empty:
    st.warning("No hay datos de Google Ads.")
    st.stop()

r = metrics.resumen_plataforma(df).iloc[0]
canal = config.canal_por_plataforma("Google Ads")  # "Paid Search (Google)"
leads_ch = datos.leads[datos.leads["fuente"] == canal]
n_leads = len(leads_ch)
n_mat = metrics.matriculas_canal(datos.deals, canal)  # matrículas = deals ganados del canal
cpl = r["coste"] / n_leads if n_leads else 0
cpa = r["coste"] / r["conversiones"] if r["conversiones"] else 0
conv_rate = r["conversiones"] / r["clics"] if r["clics"] else 0

# --------------------------------------------------------------------------- #
# Volumen y coste
# --------------------------------------------------------------------------- #
st.subheader("Volumen y coste")
c1, c2, c3, c4 = st.columns(4)
ui.kpi(c1, "Inversión", eur(r["coste"]))
ui.kpi(c2, "Impresiones", num(r["impresiones"]))
ui.kpi(c3, "Clics", num(r["clics"]), f"CTR {pct(r['ctr'],2)}")
ui.kpi(c4, "CPC medio", eur(r["cpc"], 2))

st.write("")

# --------------------------------------------------------------------------- #
# Eficiencia y resultado
# --------------------------------------------------------------------------- #
st.subheader("Eficiencia y resultado")
c5, c6, c7, c8 = st.columns(4)
ui.kpi(c5, "Conversiones (Ads)", num(r["conversiones"]),
       f"Tasa {pct(conv_rate,2)} sobre clics",
       estado="off" if r["conversiones"] == 0 else "ok")
ui.kpi(c6, "Coste/conversión (CPA)", eur(cpa, 2), "Inversión / conv. Ads")
ui.kpi(c7, "Leads (HubSpot)", num(n_leads), f"Canal {canal}")
ui.kpi(c8, "CPL real", eur(cpl, 2), "Inversión / leads HubSpot",
       estado="ok" if 0 < cpl <= config.CPL_OBJETIVO else "warn")

if r["conversiones"] == 0:
    st.error(
        "⚠️ **0 conversiones en Google Ads** pese a la inversión. Revisa la etiqueta "
        "de conversión y su enlace (ver *Tracking & Atribución*)."
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
    st.caption("Leads y matrículas de HubSpot atribuidos al canal Paid Search.")
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
camp = metrics.enriquecer_campanas_con_hubspot(metrics.resumen_campana(df), datos.leads, datos.deals)
camp = metrics.reconciliar_leads_canal(camp, datos.leads, datos.deals, canal)
ui.barras(camp.head(10), x="coste", y="campana", color=None,
          titulo="Inversión por campaña", orientacion="h")

tabla_camp = metrics.con_fila_total(
    camp[["campana", "impresiones", "clics", "ctr", "cpc", "coste", "conversiones",
          "leads", "matriculas", "ingresos"]].assign(
        cp_matricula=camp["coste"] / camp["matriculas"].replace(0, pd.NA),
        roas=camp["ingresos"] / camp["coste"].replace(0, pd.NA),
    ).fillna(0).copy(),
    "campana", ratios={
        "ctr": lambda s, _: (s["clics"] / s["impresiones"]) if s["impresiones"] else 0,
        "cpc": lambda s, _: (s["coste"] / s["clics"]) if s["clics"] else 0,
        "cp_matricula": lambda s, _: (s["coste"] / s["matriculas"]) if s["matriculas"] else 0,
        "roas": lambda s, _: (s["ingresos"] / s["coste"]) if s["coste"] else 0,
    })
ui.tabla(tabla_camp, [
    {"key": "campana", "label": "Campaña", "align": "l"},
    {"key": "impresiones", "label": "Impr.", "fmt": lambda v: num(v, 0)},
    {"key": "clics", "label": "Clics", "fmt": lambda v: num(v, 0)},
    {"key": "ctr", "label": "CTR", "fmt": lambda v: pct(v, 2)},
    {"key": "cpc", "label": "CPC", "fmt": lambda v: eur(v, 2)},
    {"key": "coste", "label": "Inversión", "fmt": lambda v: eur(v, 0)},
    {"key": "conversiones", "label": "Conv. (Ads)", "fmt": lambda v: num(v, 0)},
    {"key": "leads", "label": "Leads (HS)", "fmt": lambda v: num(v, 0)},
    {"key": "matriculas", "label": "Matrículas", "fmt": lambda v: num(v, 0)},
    {"key": "cp_matricula", "label": "Coste/matríc.", "fmt": lambda v: eur(v, 0) if v else "—"},
    {"key": "roas", "label": "ROAS", "fmt": lambda v: f"{num(v, 2)}×" if v else "—"},
], etiqueta_col="campana")
st.caption(
    "**Conv. (Ads)** = conversiones que reporta Google Ads. **Leads (HS)**, "
    "**Matrículas** e **ingresos** (para el ROAS) vienen de HubSpot casando por "
    "nombre de campaña. **ROAS** = ingresos reales de matrículas ÷ inversión "
    "(aparece en cuanto entra la primera matrícula atribuida a la campaña)."
)

st.divider()

# --------------------------------------------------------------------------- #
# Evolución semanal
# --------------------------------------------------------------------------- #
_COLS_SEM = ["semana_label", "impresiones", "clics", "ctr", "cpc", "coste",
             "conversiones", "leads", "matriculas", "cpl"]


def tabla_semanal(sem, conv_label="Conv."):
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
sel = st.selectbox("Campaña", campanas, key="evol_camp_google")
semc = metrics.resumen_semanal(df, datos.leads, canal, campana=sel)
if not semc.empty:
    tabla_semanal(semc)
    st.caption(f"Evolución semanal de **{sel}** (leads casados por nombre en HubSpot).")
else:
    st.info("Sin datos para esa campaña en el periodo.")
