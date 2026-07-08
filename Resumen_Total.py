"""
Dashboard de Marketing — Reversal Institute
Página principal: Resumen Global (embudo de marketing extremo a extremo).

Ejecutar:  streamlit run Resumen_Total.py
"""
from __future__ import annotations

import streamlit as st

from src import config
from src.data import loader, metrics
from src.ui import components as ui
from src.ui.theme import aplicar_tema, eur, num, pct

st.set_page_config(
    page_title="Reversal · Dashboard Marketing",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)
aplicar_tema()

# --------------------------------------------------------------------------- #
# Datos
# --------------------------------------------------------------------------- #
desde, hasta, etq = ui.selector_periodo()
datos = loader.cargar_todo(desde, hasta)
ui.aviso_origenes(datos.origenes)

k = metrics.kpis_globales(datos.ads, datos.leads, datos.deals)
emb_mkt = metrics.embudo_marketing(datos.ga4_extra, datos.leads, datos.deals)
pipe = metrics.valor_pipeline(datos.deals)
cruce = metrics.cruce_inversion_leads(datos.ads, datos.leads, datos.deals)

ui.cabecera(
    "Resumen Global",
    f"{etq} · del tráfico a la matrícula (Ads · GA4 · HubSpot)",
)

# --------------------------------------------------------------------------- #
# Resumen ejecutivo (auto)
# --------------------------------------------------------------------------- #
paid = cruce[(cruce["coste"] > 0) & (cruce["leads"] > 0)] if not cruce.empty else cruce
if paid is not None and not paid.empty:
    best = paid.loc[paid["cpl"].idxmin()]
    worst = paid.loc[paid["cpl"].idxmax()]
    best_txt = f"**{best['programa']}** (CPL {eur(best['cpl'], 2)})"
    concern = (f"CPL alto en **{worst['programa']}** ({eur(worst['cpl'], 2)})"
               if worst["cpl"] > config.CPL_OBJETIVO else "el CPL está bajo control")
else:
    best_txt, concern = "—", "sin leads de pago atribuidos aún"
if k["matriculas"] == 0:
    concern = f"aún **0 matrículas** cerradas (con {num(k['deals_totales'])} oportunidades en curso)"

ui.resumen_ejecutivo(
    f"En **{etq}**: **{eur(k['inversion'])}** de inversión → "
    f"**{num(k['leads_total'])} leads** (CPL {eur(k['cpl_neto'], 2)}) → "
    f"**{num(k['matriculas'])} matrículas**, ROAS **{num(k['roas'], 2)}×**. "
    f"Canal más eficiente: {best_txt}. A vigilar: {concern}."
)

# --------------------------------------------------------------------------- #
# Fila A — Inversión y eficiencia
# --------------------------------------------------------------------------- #
st.markdown("**Inversión y eficiencia**")
c1, c2, c3, c4 = st.columns(4)
ui.kpi(c1, "Inversión total", eur(k["inversion"]), "Google Ads + Meta")
ui.kpi(c2, "Leads (HubSpot)", num(k["leads_total"]), "Contactos del portal")
ui.kpi(c3, "CPL neto", eur(k["cpl_neto"], 2),
       f"Objetivo ≤ {eur(config.CPL_OBJETIVO, 0)}",
       estado="ok" if 0 < k["cpl_neto"] <= config.CPL_OBJETIVO else "warn")
ui.kpi(c4, "ROAS", f"{num(k['roas'], 2)}×", f"Ingresos reales: {eur(k['ingresos'])}",
       estado="ok" if k["roas"] >= 3 else ("warn" if k["roas"] >= 1 else "off"))

st.write("")

# --------------------------------------------------------------------------- #
# Fila B — Embudo tráfico → matrícula (GA4 → HubSpot)
# --------------------------------------------------------------------------- #
st.markdown("**Embudo: del tráfico a la matrícula**")
c5, c6, c7, c8 = st.columns(4)
ui.kpi(c5, "Sesiones (GA4)", num(emb_mkt["sesiones"]), "Tráfico del sitio")
ui.kpi(c6, "Sesión → Lead", pct(emb_mkt["tasa_lead"], 2),
       f"{num(emb_mkt['leads'])} leads")
ui.kpi(c7, "Lead → Matrícula", pct(emb_mkt["tasa_matricula"], 2),
       f"{num(emb_mkt['matriculas'])} matrículas",
       estado="ok" if emb_mkt["matriculas"] > 0 else None)
ui.kpi(c8, "Coste / matrícula", eur(k["cp_matricula"]), "Inversión / matrículas")

st.write("")

# --------------------------------------------------------------------------- #
# Fila C — Pipeline (valor económico)
# --------------------------------------------------------------------------- #
st.markdown("**Pipeline comercial (€)**")
c9, c10, c11, c12 = st.columns(4)
ui.kpi(c9, "Deals en pipeline", num(k["deals_totales"]), "Oportunidades en curso")
ui.kpi(c10, "Pipeline abierto", eur(pipe["abierto"]), "Deals no cerrados (€)")
ui.kpi(c11, "Ingresos ganados", eur(pipe["ganado"]), "Deals 'Cierre ganado' (€)",
       estado="ok" if pipe["ganado"] > 0 else None)
ui.kpi(c12, "Ticket medio", eur(pipe["ticket"]), f"{num(pipe['n_importe'])} deals con importe")

st.divider()

# --------------------------------------------------------------------------- #
# Tendencias
# --------------------------------------------------------------------------- #
col_izq, col_der = st.columns(2)
with col_izq:
    st.subheader("Inversión diaria por plataforma")
    ui.linea_temporal(metrics.serie_diaria_inversion(datos.ads),
                      x="fecha", y="coste", color="plataforma", titulo="", y_label="€/día")
with col_der:
    st.subheader("Leads diarios (todos los canales)")
    ui.area_apilada(metrics.serie_diaria_leads_por_canal(datos.leads),
                    x="fecha", y="leads", color="programa", titulo="", y_label="leads/día")

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Embudo de ventas (deals)")
    st.caption("Oportunidad → Entrevista → Envío inscripción → Cierre ganado (= matrícula).")
    ui.embudo_chart(metrics.embudo(datos.deals))
with col_b:
    st.subheader("Leads por canal")
    st.caption("Reparto por canal de adquisición (`hs_analytics_source`).")
    ui.donut(metrics.leads_por_programa_dist(datos.leads),
             nombres="programa", valores="leads", titulo="")

st.divider()

# --------------------------------------------------------------------------- #
# Rendimiento por canal
# --------------------------------------------------------------------------- #
st.subheader("Rendimiento por canal")
if not cruce.empty:
    tabla = cruce[["programa", "coste", "clics", "leads", "matriculas",
                   "ingresos", "cpl", "cp_matricula", "roas"]].copy()
    tabla = metrics.con_fila_total(tabla, "programa", ratios={
        "cpl": lambda s, _: (s["coste"] / s["leads"]) if s["leads"] else 0,
        "cp_matricula": lambda s, _: (s["coste"] / s["matriculas"]) if s["matriculas"] else 0,
        "roas": lambda s, _: (s["ingresos"] / s["coste"]) if s["coste"] else 0,
    })
    ui.tabla(tabla, [
        {"key": "programa", "label": "Canal", "align": "l"},
        {"key": "coste", "label": "Inversión (G+M)", "fmt": lambda v: eur(v, 0)},
        {"key": "clics", "label": "Clics", "fmt": lambda v: num(v, 0)},
        {"key": "leads", "label": "Leads", "fmt": lambda v: num(v, 0)},
        {"key": "matriculas", "label": "Matrículas", "fmt": lambda v: num(v, 0)},
        {"key": "cpl", "label": "CPL", "fmt": lambda v: eur(v, 2), "bold": True},
        {"key": "cp_matricula", "label": "Coste/matrícula", "fmt": lambda v: eur(v, 0)},
        {"key": "roas", "label": "ROAS", "fmt": lambda v: f"{num(v, 2)}×"},
    ], etiqueta_col="programa")
    st.caption(
        "Cruce por **canal** (todos, no solo pago): Google Ads → Paid Search, Meta → "
        "Paid Social; el resto viene de `hs_analytics_source` y no tiene inversión."
    )
