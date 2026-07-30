"""
Orquestador de datos: llama a cada conector con caché de Streamlit y expone
un objeto único `DatosDashboard` que consumen todas las páginas.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from src import config
from src.connectors import ga4, google_ads, hubspot, linkedin, meta_ads, meta_organico
from src.connectors import youtube as youtube_conn
from src.connectors.base import leer_historico
from src.data import social as social_schema
from src.data import social_demografia


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


# --------------------------------------------------------------------------- #
# Social orgánico
#
# Va en su propia función, NO dentro de `cargar_todo`, para que las 5 páginas de
# Ads/GA4/HubSpot no paguen el coste de 8 llamadas a APIs de social que no usan.
# --------------------------------------------------------------------------- #

@dataclass
class DatosSocial:
    diario: pd.DataFrame        # una fila por (fecha, red)
    posts: pd.DataFrame         # una fila por publicación
    origenes: dict              # {"YouTube": "api", "LinkedIn": "sample", ...}
    demografia: pd.DataFrame = None  # una fila por (fecha, red, dimension, categoria)

    def hay_datos_reales(self) -> bool:
        return any(o in ("api", "cache", "csv", "historico")
                   for o in self.origenes.values())


# Una entrada por red: (nombre, fn_diario, fn_posts).
_FUENTES_SOCIAL = (
    ("YouTube", lambda d, h: youtube_conn.obtener(d, h),
     lambda d, h: youtube_conn.obtener_posts(d, h)),
    ("Facebook", lambda d, h: meta_organico.obtener_facebook(d, h),
     lambda d, h: meta_organico.obtener_posts_facebook(d, h)),
    ("Instagram", lambda d, h: meta_organico.obtener_instagram(d, h),
     lambda d, h: meta_organico.obtener_posts_instagram(d, h)),
    ("LinkedIn", lambda d, h: linkedin.obtener(d, h),
     lambda d, h: linkedin.obtener_posts(d, h)),
)


@st.cache_data(ttl=config.CACHE_TTL_SOCIAL, show_spinner="Cargando social orgánico…")
def _cargar_social(desde, hasta):
    diarios, posts, origenes = [], [], {}
    for red, fn_diario, fn_posts in _FUENTES_SOCIAL:
        # Cada red se resuelve aislada: si una revienta de forma inesperada, las
        # otras tres se siguen viendo. El conector ya cae a ejemplo por su cuenta;
        # esto cubre además fallos de importación de sus dependencias.
        try:
            r_diario = fn_diario(desde, hasta)
            diarios.append(r_diario.df)
            origenes[red] = r_diario.origen
        except Exception:  # noqa: BLE001
            origenes[red] = "sample"
        try:
            posts.append(fn_posts(desde, hasta).df)
        except Exception:  # noqa: BLE001
            pass

    diario = (pd.concat([d for d in diarios if d is not None and not d.empty],
                        ignore_index=True)
              if any(d is not None and not d.empty for d in diarios)
              else social_schema.esquema_diario_vacio())
    df_posts = (pd.concat([p for p in posts if p is not None and not p.empty],
                          ignore_index=True)
                if any(p is not None and not p.empty for p in posts)
                else social_schema.esquema_posts_vacio())

    # La demografía sale SOLO del histórico que acumula el job: son fotos
    # «lifetime» que no dependen del periodo elegido y no tiene sentido pedirlas
    # a la API en cada carga de página.
    demos = []
    for red in config.REDES_SOCIAL:
        bruto = leer_historico(f"social_{red.lower()}_demografia")
        if bruto is not None and not bruto.empty:
            demos.append(social_demografia.normalizar(bruto))
    demografia = (pd.concat(demos, ignore_index=True) if demos
                  else social_demografia.esquema_vacio())

    return diario, df_posts, origenes, demografia


def cargar_social(desde, hasta) -> DatosSocial:
    diario, posts, origenes, demografia = _cargar_social(desde, hasta)
    return DatosSocial(diario=diario, posts=posts, origenes=origenes,
                        demografia=demografia)


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
