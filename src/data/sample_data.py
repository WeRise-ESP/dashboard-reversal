"""
Generador de datos de ejemplo (mock) para el Dashboard de Reversal Institute.
Se usa como *fallback* cuando un conector no tiene credenciales configuradas,
para que el dashboard sea navegable desde el minuto cero. Los datos son
deterministas (semilla fija) para no cambiar en cada carga.

Las campañas de ejemplo usan los nombres de `config.SEGMENTOS`, de modo que el
mapeo campaña -> segmento funcione igual que con datos reales.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.config import CANALES_GA4, SEGMENTOS


def _rng(nombre: str) -> np.random.Generator:
    """RNG determinista derivado de un nombre (evita aleatoriedad por sesión)."""
    semilla = int(hashlib.md5(nombre.encode()).hexdigest()[:8], 16)
    return np.random.default_rng(semilla)


def _rango_fechas(desde: date, hasta: date) -> list[date]:
    n = (hasta - desde).days
    return [desde + timedelta(days=i) for i in range(max(0, n) + 1)]


# --------------------------------------------------------------------------- #
# Google Ads — una campaña de Search por segmento + una de branding.
# --------------------------------------------------------------------------- #
def google_ads_diario(desde, hasta) -> pd.DataFrame:
    fechas = _rango_fechas(desde, hasta)
    filas = []
    perfiles = {
        s.campana_google: dict(
            impr=r_impr, ctr=0.045, cpc=1.1 + i * 0.1, cvr=0.035
        )
        for i, (s, r_impr) in enumerate(
            zip(SEGMENTOS, (120, 90, 80, 60, 70))
        )
    }
    perfiles["Reversal_Branding"] = dict(impr=600, ctr=0.30, cpc=0.28, cvr=0.0)
    for campana, pf in perfiles.items():
        r = _rng("gads" + campana)
        for f in fechas:
            impr = max(0, int(r.normal(pf["impr"], pf["impr"] * 0.25)))
            clics = int(impr * pf["ctr"] * r.uniform(0.8, 1.2))
            coste = round(clics * pf["cpc"] * r.uniform(0.85, 1.15), 2)
            conv = int(clics * pf["cvr"] * r.uniform(0.5, 1.5))
            filas.append(dict(
                fecha=f, plataforma="Google Ads", campana=campana,
                impresiones=impr, clics=clics, coste=coste, conversiones=conv,
            ))
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------- #
# Meta Ads — una campaña por segmento.
# --------------------------------------------------------------------------- #
def meta_ads_diario(desde, hasta) -> pd.DataFrame:
    fechas = _rango_fechas(desde, hasta)
    filas = []
    perfiles = {
        s.campana_meta: dict(impr=impr, ctr=0.009, cpc=0.55 + i * 0.08, cvr=0.05)
        for i, (s, impr) in enumerate(
            zip(SEGMENTOS, (3800, 3200, 2900, 2400, 2600))
        )
    }
    for campana, pf in perfiles.items():
        r = _rng("meta" + campana)
        for f in fechas:
            impr = max(0, int(r.normal(pf["impr"], pf["impr"] * 0.2)))
            clics = int(impr * pf["ctr"] * r.uniform(0.8, 1.2))
            coste = round(clics * pf["cpc"] * r.uniform(0.85, 1.15), 2)
            # El "lead real" se ve en HubSpot; Meta puede atribuir parcialmente.
            conv = int(clics * pf["cvr"] * r.uniform(0.3, 0.9))
            filas.append(dict(
                fecha=f, plataforma="Meta Ads", campana=campana,
                impresiones=impr, clics=clics, coste=coste, conversiones=conv,
            ))
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------- #
# Google Analytics 4 — tráfico de TODO el sitio por canal.
# --------------------------------------------------------------------------- #
def ga4_diario(desde, hasta) -> pd.DataFrame:
    """Tráfico de ejemplo de reversal.institute, desglosado por fecha × canal."""
    fechas = _rango_fechas(desde, hasta)
    bases = {
        "Organic Search": 140, "Paid Search": 90, "Organic Social": 110,
        "Paid Social": 130, "Direct": 100, "Referral": 45, "Email": 35,
        "Display": 60,
    }
    filas = []
    for canal in CANALES_GA4:
        r = _rng("ga4" + canal)
        base = bases.get(canal, 50)
        for f in fechas:
            sesiones = max(0, int(r.normal(base, base * 0.3)))
            usuarios = int(sesiones * r.uniform(0.75, 0.95))
            filas.append(dict(
                fecha=f, canal=canal,
                sesiones=sesiones,
                usuarios=usuarios,
                usuarios_nuevos=int(usuarios * r.uniform(0.6, 0.9)),
                sesiones_activas=int(sesiones * r.uniform(0.3, 0.6)),
                vistas=int(sesiones * r.uniform(1.3, 2.2)),
                tiempo_interaccion=int(sesiones * r.uniform(30, 120)),
                conversiones=int(sesiones * r.uniform(0.0, 0.03)),
            ))
    return pd.DataFrame(filas)


def ga4_extra(desde, hasta) -> dict:
    """KPIs del periodo y desgloses de ejemplo (páginas, dispositivo, nuevos)."""
    df = ga4_diario(desde, hasta)
    ses = int(df["sesiones"].sum()) or 1
    totales = dict(
        sesiones=ses,
        usuarios=int(df["usuarios"].sum()),
        usuarios_nuevos=int(df["usuarios_nuevos"].sum()),
        pct_nuevos=df["usuarios_nuevos"].sum() / (df["usuarios"].sum() or 1),
        engagement_rate=df["sesiones_activas"].sum() / ses,
        duracion_media=df["tiempo_interaccion"].sum() / ses,
        paginas_sesion=df["vistas"].sum() / ses,
        conversiones=int(df["conversiones"].sum()),
        tasa_conversion=df["conversiones"].sum() / ses,
    )
    r = _rng("ga4-extra")
    paginas = pd.DataFrame([
        {"pagina": p, "sesiones": s, "usuarios": int(s * 0.85),
         "engagement_rate": round(r.uniform(0.35, 0.7), 3),
         "conversiones": int(s * r.uniform(0.0, 0.1))}
        for p, s in [("/", 440), ("/programas/certificacion-longevidad-healthspan", 390),
                     ("/perfil", 60), ("/blog", 40), ("/nosotros", 25)]
    ])
    dispositivo = pd.DataFrame([
        {"dispositivo": d, "sesiones": s, "usuarios": int(s * 0.85),
         "conversiones": int(s * 0.05)}
        for d, s in [("Móvil", 620), ("Escritorio", 300), ("Tablet", 30)]
    ])
    nuevos = pd.DataFrame([
        {"tipo": "Nuevos", "sesiones": int(ses * 0.72), "usuarios": int(ses * 0.7)},
        {"tipo": "Recurrentes", "sesiones": int(ses * 0.28), "usuarios": int(ses * 0.12)},
    ])
    return {"origen": "sample", "totales": totales, "paginas": paginas,
            "dispositivo": dispositivo, "nuevos": nuevos}


# --------------------------------------------------------------------------- #
# HubSpot — leads (contactos) con su segmento
# --------------------------------------------------------------------------- #
def hubspot_leads(desde, hasta) -> pd.DataFrame:
    """Leads de ejemplo = contactos con la propiedad de segmento de Reversal."""
    fechas = _rango_fechas(desde, hasta)
    r = _rng("hubspot-leads")
    filas = []
    estados = ["Lead", "MQL", "SQL", "Oportunidad", "Matriculado", "Descartado"]
    prob_estado = [0.34, 0.20, 0.14, 0.20, 0.04, 0.08]
    fuentes = ["Paid Search (Google)", "Paid Social (Meta)", "Búsqueda orgánica",
               "Social orgánico", "Directo", "Referido"]
    prob_fuente = [0.28, 0.30, 0.14, 0.12, 0.10, 0.06]
    campanas = ["nac - longevidad y healthspan", "test mestral — entrenadores",
                "test mestral — coach", "test mestral — video", "Sin campaña"]
    prob_campana = [0.55, 0.15, 0.12, 0.10, 0.08]

    lead_id = 1000
    for f in fechas:
        n_dia = int(r.normal(14, 4))
        for _ in range(max(0, n_dia)):
            estado = estados[r.choice(len(estados), p=prob_estado)]
            fuente = fuentes[r.choice(len(fuentes), p=prob_fuente)]
            campana = campanas[r.choice(len(campanas), p=prob_campana)]
            lead_id += 1
            filas.append(dict(
                lead_id=f"C{lead_id}", fecha_creacion=f,
                fuente=fuente, campana=campana, programa=fuente,
                nivel="Profesional", estado=estado,
                es_matricula=(estado == "Matriculado"),
            ))
    return pd.DataFrame(filas)


def hubspot_deals(desde, hasta) -> pd.DataFrame:
    """Deals de ejemplo del pipeline, con etapa y segmento."""
    from src.config import HUBSPOT_ETAPAS_UVIC

    fechas = _rango_fechas(desde, hasta)
    r = _rng("hubspot-deals")
    etapas = HUBSPOT_ETAPAS_UVIC  # [(id, label), ...] en orden de embudo
    prob = [0.55, 0.18, 0.12, 0.08, 0.07]
    segmentos = [p.nombre for p in SEGMENTOS]
    filas = []
    deal_id = 5000
    for f in fechas:
        n_dia = int(r.normal(2, 1))
        for _ in range(max(0, n_dia)):
            i = r.choice(len(etapas), p=prob)
            etapa_id, etapa = etapas[i]
            deal_id += 1
            filas.append(dict(
                deal_id=f"D{deal_id}", fecha_creacion=f,
                etapa_id=etapa_id, etapa=etapa,
                programa=segmentos[r.choice(len(segmentos))],
                amount=0.0, es_ganado=(etapa == "Cierre ganado"),
            ))
    return pd.DataFrame(filas)
