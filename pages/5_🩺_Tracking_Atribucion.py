"""Página: salud del tracking y de la atribución (diagnóstico Google/Meta/HubSpot)."""
from __future__ import annotations

import streamlit as st

from src import config
from src.data import loader, metrics
from src.ui.theme import aplicar_tema, num, pct
from src.ui import components as ui

st.set_page_config(page_title="Tracking & Atribución · Reversal", page_icon="🩺", layout="wide")
aplicar_tema()

desde, hasta, etq = ui.selector_periodo()
datos = loader.cargar_todo(desde, hasta)
ui.aviso_origenes(datos.origenes)

ui.cabecera("Tracking & Atribución", "Salud de la medición end-to-end")

leads = datos.leads
ads = datos.ads

# --- Indicadores de salud ---------------------------------------------------
conv_google = int(datos.google["conversiones"].sum()) if not datos.google.empty else 0
conv_meta = int(datos.meta["conversiones"].sum()) if not datos.meta.empty else 0
leads_total = len(leads)
# Cuántos leads llegan CON campaña identificable (click-id preservado).
atribuidos = int((leads["campana"].astype(str).str.len() > 0).sum()) if "campana" in leads else 0
pct_atrib = atribuidos / leads_total if leads_total else 0

st.subheader("Semáforo de medición")
c1, c2, c3, c4 = st.columns(4)
ui.kpi(c1, "Conversiones Google Ads", num(conv_google),
       "Deberían reflejar leads", estado="off" if conv_google == 0 else "ok")
ui.kpi(c2, "Conversiones Meta Ads", num(conv_meta),
       "Deberían reflejar leads", estado="off" if conv_meta == 0 else "ok")
ui.kpi(c3, "Leads (HubSpot)", num(leads_total),
       "La demanda SÍ existe", estado="ok")
ui.kpi(c4, "Leads con campaña (click-id)", num(atribuidos),
       f"{pct(pct_atrib)} con atribución", estado="off" if pct_atrib < 0.3 else "ok")

st.divider()

# --- Diagnóstico narrativo --------------------------------------------------
st.subheader("Diagnóstico")
st.markdown(f"""
Contrasta la demanda real (HubSpot) con lo que atribuyen las plataformas:

- **Demanda**: HubSpot registra **{num(leads_total)} leads** en el periodo.
- **Atribución en plataforma**: Google Ads marca **{conv_google}** conversiones y
  Meta **{conv_meta}**. Si estas cifras están muy por debajo de los leads reales,
  hay una **fuga de atribución** (no falta de leads).
- **Solo {num(atribuidos)} de {num(leads_total)} leads** llegan con campaña
  identificable; el resto entra sin click-id (OFFLINE / integración).

**Causa raíz habitual**: al enviar el formulario se pierden el `gclid`/`fbclid` y
las cookies `_fbc/_fbp`, de modo que el lead no se enlaza con el clic. Agravante
frecuente en Meta: la **Conversions API (CAPI)** no está enviando el evento `Lead`.
""")

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("**Reparto de leads por canal**")
    ui.donut(metrics.leads_por_programa_dist(leads), nombres="programa",
             valores="leads", titulo="")
with col_b:
    st.markdown("**Configuración de referencia**")
    st.markdown(f"""
    | Elemento | Valor |
    |---|---|
    | Píxel Meta (dataset) | `{config.META_PIXEL_DATASET_ID}` |
    | Cuenta Meta | `{config.META_AD_ACCOUNT_ID}` |
    | Cuenta Google Ads | `{config.GOOGLE_ADS_CUSTOMER_ID}` |
    | Property GA4 | `{config.GA4_PROPERTY_ID}` |
    | Evento clave | `Lead` |
    """)

st.divider()

# --- Checklist de acciones --------------------------------------------------
st.subheader("Plan de corrección (checklist)")
acciones = [
    ("Preservar `gclid`/`fbclid` a través del formulario y las redirecciones", "Alta", "Media"),
    ("Capturar UTMs + click IDs en campos ocultos del form de HubSpot", "Alta", "Baja"),
    ("Verificar en Ads Manager que el conjunto usa el píxel + evento Lead", "Alta", "Baja"),
    ("Activar Conversions API (CAPI) en Meta y enviar `fbc` en el evento Lead", "Alta", "Media"),
    ("Enlazar la conversión de Google Ads con el lead de HubSpot (offline conversions)", "Alta", "Media"),
    ("Marcar conversiones/eventos clave en GA4 y enlazar Google Ads ↔ GA4", "Media", "Baja"),
    ("Validar en Test Events que el Lead llega con `fbc`", "Media", "Baja"),
]
st.dataframe(
    {"Acción": [a[0] for a in acciones],
     "Impacto": [a[1] for a in acciones],
     "Esfuerzo": [a[2] for a in acciones]},
    width='stretch', hide_index=True,
)
st.caption(
    "Prioriza el cuadrante Alto impacto / Bajo esfuerzo: capturar UTMs+clickIDs en el "
    "formulario de HubSpot y verificar el píxel del conjunto de anuncios."
)
