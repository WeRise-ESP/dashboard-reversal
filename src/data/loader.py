"""
Orquestador de datos: llama a cada conector con caché de Streamlit y expone
un objeto único `DatosDashboard` que consumen todas las páginas.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from src import config
from src.connectors import ga4, google_ads, hubspot, meta_ads


@dataclass
class DatosDashboard:
    google: pd.DataFrame
    meta: pd.DataFrame
    ga4: pd.DataFrame
    leads: pd.DataFrame
    deals: pd.DataFrame
    origenes: dict  # {"Google Ads": "sample", ...}
    ga4_extra: dict = None  # KPIs del periodo + desgloses (páginas, dispositivo, nuevos)

    @property
    def ads(self) -> pd.DataFrame:
        """Google + Meta unificados (mismo esquema de columnas)."""
        frames = [d for d in (self.google, self.meta) if not d.empty]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def hay_datos_reales(self) -> bool:
        return any(o in ("api", "cache") for o in self.origenes.values())


# Caché por fuente con TTL distinto: HubSpot corto (cambia a diario), ads/GA4 largo.
@st.cache_data(ttl=config.CACHE_TTL_ADS, show_spinner="Cargando Google Ads…")
def _cargar_google(desde, hasta):
    r = google_ads.obtener(desde, hasta)
    return r.df, r.origen


@st.cache_data(ttl=config.CACHE_TTL_ADS, show_spinner="Cargando Meta Ads…")
def _cargar_meta(desde, hasta):
    r = meta_ads.obtener(desde, hasta)
    return r.df, r.origen


@st.cache_data(ttl=config.CACHE_TTL_GA4, show_spinner="Cargando GA4…")
def _cargar_ga4(desde, hasta):
    r = ga4.obtener(desde, hasta)
    return r.df, r.origen


@st.cache_data(ttl=config.CACHE_TTL_GA4, show_spinner="Cargando GA4 (desgloses)…")
def _cargar_ga4_extra(desde, hasta):
    return ga4.obtener_extra(desde, hasta)


@st.cache_data(ttl=config.CACHE_TTL_HUBSPOT, show_spinner="Cargando HubSpot…")
def _cargar_hubspot(desde, hasta):
    leads = hubspot.obtener(desde, hasta)
    deals = hubspot.obtener_deals(desde, hasta)
    return leads.df, leads.origen, deals.df


def cargar_todo(desde, hasta) -> DatosDashboard:
    g_df, g_o = _cargar_google(desde, hasta)
    m_df, m_o = _cargar_meta(desde, hasta)
    a_df, a_o = _cargar_ga4(desde, hasta)
    a_extra = _cargar_ga4_extra(desde, hasta)
    l_df, l_o, d_df = _cargar_hubspot(desde, hasta)
    return DatosDashboard(
        google=g_df, meta=m_df, ga4=a_df, leads=l_df, deals=d_df,
        origenes={
            "Google Ads": g_o,
            "Meta Ads": m_o,
            "Google Analytics": a_o,
            "HubSpot": l_o,
        },
        ga4_extra=a_extra,
    )
