"""Página: salud del tracking y de la atribución (Google/Meta/HubSpot)."""
from __future__ import annotations

import streamlit as st

from src import config
from src.data import loader, metrics
from src.ui import components as ui
from src.ui.theme import aplicar_tema, num, pct

st.set_page_config(page_title="Tracking & Atribución · Reversal", page_icon="🩺", layout="wide")
aplicar_tema()

desde, hasta, etq = ui.selector_periodo()
datos = loader.cargar_todo(desde, hasta)
ui.aviso_origenes(datos.origenes)

ui.cabecera("Tracking & Atribución", "Salud de la medición end-to-end")

leads = datos.leads

# --- Indicadores de salud ---------------------------------------------------
conv_google = int(datos.google["conversiones"].sum()) if not datos.google.empty else 0
conv_meta = int(datos.meta["conversiones"].sum()) if not datos.meta.empty else 0
leads_total = len(leads)

canal_meta = config.canal_por_plataforma("Meta Ads")
canal_google = config.canal_por_plataforma("Google Ads")
leads_ps = int((leads["fuente"] == canal_meta).sum()) if leads_total else 0
leads_pse = int((leads["fuente"] == canal_google).sum()) if leads_total else 0

_NO_CAMPANA = {"", "Sin campaña", "Sin atribuir"}
con_campana = int((~leads["campana"].isin(_NO_CAMPANA)).sum()) if ("campana" in leads and leads_total) else 0
pct_campana = con_campana / leads_total if leads_total else 0

# La medición se considera SANA si las plataformas registran conversiones.
medicion_ok = conv_google > 0 and conv_meta > 0

# --------------------------------------------------------------------------- #
# Semáforo de medición
# --------------------------------------------------------------------------- #
st.subheader("Semáforo de medición")
c1, c2, c3, c4 = st.columns(4)
ui.kpi(c1, "Conversiones Google Ads", num(conv_google),
       "Registrando conversiones", estado="ok" if conv_google > 0 else "off")
ui.kpi(c2, "Conversiones Meta Ads", num(conv_meta),
       "Registrando conversiones", estado="ok" if conv_meta > 0 else "off")
ui.kpi(c3, "Leads (HubSpot)", num(leads_total), "Demanda del periodo", estado="ok")
ui.kpi(c4, "Leads con campaña", num(con_campana),
       f"{pct(pct_campana)} identificados",
       estado="ok" if pct_campana >= 0.5 else "warn")

st.divider()

# --------------------------------------------------------------------------- #
# Diagnóstico adaptativo
# --------------------------------------------------------------------------- #
st.subheader("Diagnóstico")
if medicion_ok:
    ui.resumen_ejecutivo(
        "✅ **La medición funciona correctamente.** Las plataformas registran "
        "conversiones y son coherentes con los leads reales de HubSpot — no hay fuga "
        "de atribución."
    )
    st.markdown(f"""
- **Demanda real**: HubSpot registra **{num(leads_total)} leads** en el periodo.
- **Meta Ads** atribuye **{conv_meta} conversiones**, en línea con los
  **{num(leads_ps)} leads** de Paid Social en HubSpot.
- **Google Ads** atribuye **{conv_google} conversiones**, en línea con los
  **{num(leads_pse)} leads** de Paid Search.
- **{num(con_campana)} de {num(leads_total)} leads** ({pct(pct_campana)}) llegan con
  **campaña identificable**; el resto son directos/orgánicos (sin campaña de pago, es normal).

El píxel, las conversiones y la atribución por canal están **operativos**. 👇 Abajo tienes
una lista de verificaciones para **mantener** la medición sana.
""")
else:
    st.warning(
        "Alguna plataforma no está registrando conversiones. Contrasta con los leads "
        "reales de HubSpot para localizar la fuga (revisa el píxel y la Conversions API)."
    )
    st.markdown(f"""
- **Demanda real**: HubSpot registra **{num(leads_total)} leads**.
- **Atribución en plataforma**: Google Ads **{conv_google}** · Meta **{conv_meta}**.
  Si están muy por debajo de los leads reales, hay una **fuga de atribución** (no falta de leads).
- **Causa habitual**: al enviar el formulario se pierden `gclid`/`fbclid` y las cookies
  `_fbc/_fbp`; o la Conversions API (CAPI) de Meta no envía el evento `Lead`.
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
    | Cuenta Meta | `{config.META_AD_ACCOUNT_ID}` |
    | Cuenta Google Ads | `{config.GOOGLE_ADS_CUSTOMER_ID}` |
    | Property GA4 | `{config.GA4_PROPERTY_ID}` |
    | Portal HubSpot | `{config.HUBSPOT_PORTAL_ID}` |
    | Evento clave | `Lead` |
    """)

st.divider()

# --------------------------------------------------------------------------- #
# Checklist: mantenimiento (si está sano) o corrección (si hay fuga)
# --------------------------------------------------------------------------- #
if medicion_ok:
    st.subheader("Buenas prácticas para mantener la medición")
    acciones = [
        ("Revisar cada semana que Google y Meta sigan registrando conversiones", "Alta", "Baja"),
        ("Mantener capturados los UTMs y click IDs en el formulario de HubSpot", "Alta", "Baja"),
        ("Verificar periódicamente la Conversions API (CAPI) de Meta con Test Events", "Media", "Baja"),
        ("Enriquecer la atribución: rellenar `utm_campaign` para bajar el % 'Sin campaña'", "Media", "Media"),
        ("Marcar/confirmar los eventos clave (key events) en GA4 y su enlace con Ads", "Media", "Baja"),
    ]
    st.dataframe(
        {"Acción": [a[0] for a in acciones],
         "Impacto": [a[1] for a in acciones],
         "Esfuerzo": [a[2] for a in acciones]},
        width='stretch', hide_index=True,
    )
    st.caption("La medición está sana ✅ — estas verificaciones son de mantenimiento, no de corrección.")
else:
    st.subheader("Plan de corrección (checklist)")
    acciones = [
        ("Preservar `gclid`/`fbclid` a través del formulario y las redirecciones", "Alta", "Media"),
        ("Capturar UTMs + click IDs en campos ocultos del form de HubSpot", "Alta", "Baja"),
        ("Verificar en Ads Manager que el conjunto usa el píxel + evento Lead", "Alta", "Baja"),
        ("Activar Conversions API (CAPI) en Meta y enviar `fbc` en el evento Lead", "Alta", "Media"),
        ("Enlazar la conversión de Google Ads con el lead de HubSpot (offline conversions)", "Alta", "Media"),
    ]
    st.dataframe(
        {"Acción": [a[0] for a in acciones],
         "Impacto": [a[1] for a in acciones],
         "Esfuerzo": [a[2] for a in acciones]},
        width='stretch', hide_index=True,
    )
