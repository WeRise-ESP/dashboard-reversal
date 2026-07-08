"""Página: Leads (HubSpot) — leads por canal/campaña, embudo, valor de pipeline."""
from __future__ import annotations

import streamlit as st

from src import config
from src.config import VALOR_MATRICULA
from src.data import loader, metrics
from src.ui import components as ui
from src.ui.theme import aplicar_tema, eur, num, pct

st.set_page_config(page_title="Leads · HubSpot", page_icon="🎯", layout="wide")
aplicar_tema()

desde, hasta, etq = ui.selector_periodo()
datos = loader.cargar_todo(desde, hasta)
ui.aviso_origenes(datos.origenes)

ui.cabecera("Leads · HubSpot", f"Reversal · del lead a la matrícula · {etq}")

leads = datos.leads
deals = datos.deals
if leads.empty and deals.empty:
    st.warning("No hay datos de HubSpot.")
    st.stop()

total = len(leads)
con_programa = int((leads["programa"] != "Sin asignar").sum()) if total else 0
deals_tot = len(deals)
matriculas = int(deals["es_ganado"].sum()) if not deals.empty else 0
pipe = metrics.valor_pipeline(deals)
por_canal = metrics.resumen_leads_por_programa(leads)
tasa_mat = matriculas / total if total else 0

# --------------------------------------------------------------------------- #
# Resumen ejecutivo
# --------------------------------------------------------------------------- #
top_canal = por_canal.iloc[0]["programa"] if not por_canal.empty else "—"
ui.resumen_ejecutivo(
    f"En **{etq}**: **{num(total)} leads** "
    f"({pct(con_programa/total if total else 0)} con canal atribuido) → "
    f"**{num(deals_tot)} oportunidades** (**{eur(pipe['abierto'])}** en pipeline abierto) → "
    f"**{num(matriculas)} matrículas** ({eur(pipe['ganado'])}). "
    f"Canal que más leads trae: **{top_canal}**."
)

# --------------------------------------------------------------------------- #
# KPIs
# --------------------------------------------------------------------------- #
c1, c2, c3, c4 = st.columns(4)
ui.kpi(c1, "Leads", num(total), "Contactos del portal Reversal")
ui.kpi(c2, "Con atribución", num(con_programa),
       f"{pct(con_programa/total if total else 0)} con canal",
       estado="ok" if total and con_programa/total >= 0.9 else "warn")
ui.kpi(c3, "Deals en pipeline", num(deals_tot), "Oportunidades")
ui.kpi(c4, "Matrículas", num(matriculas), f"Lead→matrícula {pct(tasa_mat, 2)}",
       estado="ok" if matriculas > 0 else "off")

st.write("")
c5, c6, c7, c8 = st.columns(4)
ui.kpi(c5, "Pipeline abierto", eur(pipe["abierto"]), "Deals no cerrados (€)")
ui.kpi(c6, "Ingresos ganados", eur(pipe["ganado"]), "Deals 'Cierre ganado' (€)",
       estado="ok" if pipe["ganado"] > 0 else None)
ui.kpi(c7, "Ticket medio", eur(pipe["ticket"]), f"{num(pipe['n_importe'])} deals con importe")
ui.kpi(c8, "Valor total pipeline", eur(pipe["total"]), "Abierto + ganado + perdido")

st.divider()

# --------------------------------------------------------------------------- #
# Leads por canal + estado del lead
# --------------------------------------------------------------------------- #
col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Leads por canal")
    ui.barras(por_canal.sort_values("leads"), x="leads", y="programa",
              color=None, titulo="", orientacion="h")
with col_b:
    st.subheader("Estado del lead (ciclo de vida)")
    estado = metrics.leads_por_estado(leads)
    if not estado.empty:
        ui.donut(estado, nombres="estado", valores="leads", titulo="")

# --------------------------------------------------------------------------- #
# Embudo del pipeline + tendencia de leads
# --------------------------------------------------------------------------- #
col_c, col_d = st.columns(2)
with col_c:
    st.subheader("Embudo del pipeline")
    ui.embudo_chart(metrics.embudo(deals))
with col_d:
    st.subheader("Leads diarios")
    ui.linea_temporal(metrics.serie_diaria_leads(leads),
                      x="fecha", y="leads", color=None, titulo="", y_label="leads/día")

# Tasas de conversión del embudo
st.subheader("Conversión del pipeline")
et = metrics.embudo_tasas(deals)
if not et.empty:
    ui.tabla(et[["etapa", "leads", "pct", "conv_paso"]], [
        {"key": "etapa", "label": "Etapa", "align": "l"},
        {"key": "leads", "label": "Deals", "fmt": lambda v: num(v, 0)},
        {"key": "pct", "label": "% del total", "fmt": lambda v: pct(v, 1)},
        {"key": "conv_paso", "label": "% de paso", "fmt": lambda v: pct(v, 1), "bold": True},
    ])
    st.caption("**% del total** = deals que llegan a esa etapa vs. el total inicial. "
               "**% de paso** = conversión desde la etapa anterior.")

st.divider()

# --------------------------------------------------------------------------- #
# Inversión ↔ leads por canal
# --------------------------------------------------------------------------- #
st.subheader("Inversión ↔ leads por canal (CPL, coste/matrícula, ROAS)")
cruce = metrics.cruce_inversion_leads(datos.ads, leads, deals)
if not cruce.empty:
    tabla_cruce = cruce[["programa", "coste", "clics", "leads", "matriculas",
                         "ingresos", "cpl", "cp_matricula", "roas"]].copy()
    tabla_cruce = metrics.con_fila_total(tabla_cruce, "programa", ratios={
        "cpl": lambda s, _: (s["coste"] / s["leads"]) if s["leads"] else 0,
        "cp_matricula": lambda s, _: (s["coste"] / s["matriculas"]) if s["matriculas"] else 0,
        "roas": lambda s, _: (s["ingresos"] / s["coste"]) if s["coste"] else 0,
    })
    ui.tabla(tabla_cruce, [
        {"key": "programa", "label": "Canal", "align": "l"},
        {"key": "coste", "label": "Inversión (G+M)", "fmt": lambda v: eur(v, 0)},
        {"key": "clics", "label": "Clics", "fmt": lambda v: num(v, 0)},
        {"key": "leads", "label": "Leads", "fmt": lambda v: num(v, 0)},
        {"key": "matriculas", "label": "Matrículas", "fmt": lambda v: num(v, 0)},
        {"key": "cpl", "label": "CPL", "fmt": lambda v: eur(v, 2), "bold": True},
        {"key": "cp_matricula", "label": "Coste/matrícula", "fmt": lambda v: eur(v, 0)},
        {"key": "roas", "label": "ROAS", "fmt": lambda v: f"{num(v, 2)}×"},
    ], etiqueta_col="programa")

# --------------------------------------------------------------------------- #
# Leads por campaña
# --------------------------------------------------------------------------- #
st.subheader("Leads por campaña")
st.caption("Campaña derivada de `hs_analytics_source_data_1/2` de HubSpot (los UTM están vacíos).")
por_camp = metrics.leads_por_campana(leads)
if not por_camp.empty:
    ui.barras(por_camp.sort_values("leads").tail(12), x="leads", y="campana",
              color=None, titulo="", orientacion="h")
    ui.tabla(metrics.con_fila_total(por_camp, "campana"), [
        {"key": "campana", "label": "Campaña", "align": "l"},
        {"key": "leads", "label": "Leads", "fmt": lambda v: num(v, 0)},
        {"key": "matriculas", "label": "Matrículas", "fmt": lambda v: num(v, 0)},
    ], etiqueta_col="campana")

# --------------------------------------------------------------------------- #
# Leads recientes
# --------------------------------------------------------------------------- #
st.subheader("Leads recientes")
cols = [c for c in ["lead_id", "fecha_creacion", "campana", "programa", "estado", "fuente"]
        if c in leads.columns]
st.dataframe(
    leads.sort_values("fecha_creacion", ascending=False).head(50)[cols],
    width='stretch', hide_index=True,
    column_config={
        "lead_id": "ID", "fecha_creacion": "Creado", "campana": "Campaña",
        "programa": "Canal", "estado": "Estado", "fuente": "Fuente",
    },
)
st.caption(
    "Portal HubSpot **147885062** (exclusivo de Reversal): todo contacto es un lead. "
    "El canal viene de `hs_analytics_source`; el estado, del `lifecyclestage`. Los UTM y "
    "el perfil profesional del ICP (`perfil_titulacion`) están **sin poblar** hoy."
)
