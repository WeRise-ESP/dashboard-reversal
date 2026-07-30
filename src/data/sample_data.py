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
                estado="Pausada" if campana.endswith("_Branding") else "Activa",
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
    for i, (campana, pf) in enumerate(perfiles.items()):
        r = _rng("meta" + campana)
        for f in fechas:
            impr = max(0, int(r.normal(pf["impr"], pf["impr"] * 0.2)))
            clics = int(impr * pf["ctr"] * r.uniform(0.8, 1.2))
            coste = round(clics * pf["cpc"] * r.uniform(0.85, 1.15), 2)
            # El "lead real" se ve en HubSpot; Meta puede atribuir parcialmente.
            conv = int(clics * pf["cvr"] * r.uniform(0.3, 0.9))
            filas.append(dict(
                fecha=f, plataforma="Meta Ads", campana=campana,
                estado="Activa" if i % 2 == 0 else "Pausada",
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
    paises = pd.DataFrame([
        {"pais": p, "sesiones": s, "usuarios": int(s * 0.82)}
        for p, s in [("Spain", 1363), ("United States", 213), ("Sweden", 56),
                     ("Ireland", 31), ("(no definido)", 22),
                     ("United Arab Emirates", 8), ("India", 6), ("Argentina", 5)]
    ])
    regiones = pd.DataFrame([
        {"region": r_, "sesiones": s, "usuarios": int(s * 0.82)}
        for r_, s in [("Catalonia", 407), ("Madrid", 272), ("Andalusia", 172),
                      ("Valencian Community", 162), ("Castile and Leon", 61),
                      ("Basque Country", 44), ("Galicia", 38), ("Canary Islands", 30)]
    ])
    ciudades = pd.DataFrame([
        {"ciudad": c, "sesiones": s, "usuarios": int(s * 0.82)}
        for c, s in [("Barcelona", 260), ("Madrid", 218), ("Valencia", 77),
                     ("Malaga", 40), ("Seville", 34), ("Zaragoza", 25),
                     ("Bilbao", 22), ("(no definido)", 179)]
    ])
    return {"origen": "sample", "totales": totales, "paginas": paginas,
            "dispositivo": dispositivo, "nuevos": nuevos, "paises": paises,
            "regiones": regiones, "ciudades": ciudades}


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
    paises = ["España", "México", "Argentina", "Estados Unidos", "Reino Unido", "Sin país"]
    prob_pais = [0.72, 0.08, 0.06, 0.05, 0.04, 0.05]
    especialidades = ["Médico", "Otro", "Coach de salud", "Esteticista",
                       "Nutricionista", "Owner clínica", "Entrenador", "Sin especificar"]
    prob_esp = [0.26, 0.22, 0.11, 0.10, 0.07, 0.07, 0.05, 0.12]

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
                pais=paises[r.choice(len(paises), p=prob_pais)],
                especialidad=especialidades[r.choice(len(especialidades), p=prob_esp)],
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
    motivos = ["Motivos económicos", "Pierde interés", "Teléfono/email erróneo",
               "Imposible contactar", "Titulación Oficial", "Próxima convocatoria"]
    prob_mot = [0.25, 0.20, 0.20, 0.15, 0.10, 0.10]
    filas = []
    deal_id = 5000
    for f in fechas:
        n_dia = int(r.normal(2, 1))
        for _ in range(max(0, n_dia)):
            i = r.choice(len(etapas), p=prob)
            etapa_id, etapa = etapas[i]
            perdido = (etapa == "Cierre perdido")
            deal_id += 1
            filas.append(dict(
                deal_id=f"D{deal_id}", fecha_creacion=f,
                etapa_id=etapa_id, etapa=etapa,
                programa=segmentos[r.choice(len(segmentos))],
                campana="Sin campaña",
                amount=0.0, es_ganado=(etapa == "Cierre ganado"),
                es_perdido=perdido,
                motivo_perdido=(motivos[r.choice(len(motivos), p=prob_mot)]
                                if perdido else "Sin motivo indicado"),
            ))
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------- #
# Social orgánico — YouTube, Facebook, Instagram, LinkedIn.
#
# NOTA: se generan TODAS las métricas para las 4 redes a propósito, incluidas las
# que la red no publica en realidad (p.ej. impresiones de Instagram). Es
# deliberado: `src/data/social.py` debe anularlas al normalizar, así que el
# ejemplo sirve además de prueba de que la regla de los nulos se está aplicando.
# Si en el dashboard vieras un número en una casilla que debería estar a «—», la
# regla se ha roto.
#
# ⚠️ LOS VOLÚMENES SE CALIBRARON CONTRA LAS CUENTAS REALES el 30-jul-2026, y no
# es un detalle cosmético.
#
# Antes asumían que LinkedIn era la red fuerte (4.200 seguidores, 2.400
# visualizaciones al día). Los datos reales dijeron lo contrario: la grande es
# Instagram, y las cuentas son jóvenes y pequeñas. Como LinkedIn es la única red
# que sigue en ejemplo mientras se aprueba su API, esas cifras infladas
# aplastaban a las tres reales en la tabla comparativa, en el gráfico de
# evolución y en el ranking de publicaciones: 6.689 likes inventados frente a
# los 138 reales de Instagram.
#
# Un dato de ejemplo desproporcionado no es un error inocuo en esta página: la
# comparación entre redes ES el producto. Si vuelves a tocar estos números,
# míralos primero contra `data/historico_social/` y mantenlos en el mismo orden
# de magnitud.
#
# Referencia real (últimos 30 días, 30-jul-2026):
#   Instagram  419 seguidores · 153.322 visualizaciones · 138 likes
#   YouTube      3 seguidores ·   5.274 visualizaciones ·  38 likes
#   Facebook    14 seguidores ·     193 visualizaciones ·   0 likes
# --------------------------------------------------------------------------- #

# Base diaria por red: visualizaciones, seguidores acumulados, seguidores nuevos
# al día, tasa de engagement, mensajes y publicaciones al mes.
_PERFIL_SOCIAL = {
    # LinkedIn: página joven de público profesional. Poco volumen pero
    # engagement alto, que es el patrón real de B2B.
    "LinkedIn":  dict(views=95,   followers=140, seg=2,  eng=0.030, msg=0, posts_mes=10),
    "Instagram": dict(views=5100, followers=420, seg=13, eng=0.002, msg=0, posts_mes=10),
    "YouTube":   dict(views=180,  followers=5,   seg=1,  eng=0.008, msg=0, posts_mes=7),
    "Facebook":  dict(views=7,    followers=14,  seg=1,  eng=0.010, msg=0, posts_mes=8),
}


def social_diario(desde, hasta) -> pd.DataFrame:
    """Métricas diarias de cuenta de ejemplo, una fila por (fecha, red)."""
    fechas = _rango_fechas(desde, hasta)
    filas = []
    for red, pf in _PERFIL_SOCIAL.items():
        r = _rng("social-" + red)
        acumulado = pf["followers"]
        for i, f in enumerate(fechas):
            # Fin de semana rinde menos, sobre todo en LinkedIn (público laboral).
            factor_fds = 0.55 if (red == "LinkedIn" and f.weekday() >= 5) else 1.0
            views = max(0, int(r.normal(pf["views"], pf["views"] * 0.3) * factor_fds))
            alcance = int(views * r.uniform(0.62, 0.82))       # < views por definición
            impresiones = int(views * r.uniform(1.05, 1.35))   # > views por definición
            inter = int(views * pf["eng"] * r.uniform(0.7, 1.3))
            likes = int(inter * 0.78)
            comentarios = int(inter * 0.14)
            compartidos = max(0, inter - likes - comentarios)
            nuevos = max(0, int(r.normal(pf["seg"], pf["seg"] * 0.5) * factor_fds))
            acumulado += nuevos
            filas.append(dict(
                fecha=f, red=red,
                impresiones=impresiones, visualizaciones=views, alcance=alcance,
                seguidores_nuevos=nuevos, seguidores_total=acumulado,
                likes=likes, comentarios=comentarios, compartidos=compartidos,
                mensajes=max(0, int(r.normal(pf["msg"], 1.5))) if pf["msg"] else 0,
            ))
    return pd.DataFrame(filas)


# Publicaciones verosímiles del contenido de Reversal (longevidad / healthspan).
_TITULOS_SOCIAL = {
    "YouTube": [
        ("¿Qué es realmente el healthspan?", "Vídeo"),
        ("3 marcadores de longevidad que puedes medir hoy", "Vídeo"),
        ("Entrevista: longevidad en la práctica clínica", "Vídeo"),
        ("Mitos sobre suplementación antiedad", "Short"),
        ("Cómo interpretar la edad biológica", "Short"),
        ("Ejercicio de fuerza después de los 50", "Vídeo"),
        ("¿Sirven los test de edad epigenética?", "Short"),
        ("Longevidad: qué dice la evidencia en 2026", "Vídeo"),
        ("Errores al medir composición corporal", "Short"),
    ],
    "Facebook": [
        ("Abrimos plazas de la nueva convocatoria", "Publicación"),
        ("Caso real: 12 semanas de intervención", "Publicación"),
        ("Webinar gratuito: metabolismo y edad", "Enlace"),
        ("El equipo docente de la certificación", "Vídeo"),
        ("Testimonio de una alumna fisioterapeuta", "Vídeo"),
        ("Preguntas frecuentes sobre la matrícula", "Publicación"),
        ("Nueva sesión práctica en Barcelona", "Publicación"),
        ("Descarga el programa completo", "Enlace"),
        ("Qué aprenderás en el módulo 3", "Publicación"),
    ],
    "Instagram": [
        ("5 señales de inflamación crónica", "Carrusel"),
        ("Rutina de fuerza para pacientes +50", "Reel"),
        ("Lo que tu analítica no te está diciendo", "Carrusel"),
        ("Un día en la certificación", "Reel"),
        ("Sueño y longevidad: la evidencia", "Imagen"),
        ("Responde el Dr.: ¿sirven los suplementos?", "Reel"),
        ("Antes y después: 16 semanas", "Carrusel"),
        ("3 hábitos que envejecen tu piel", "Reel"),
        ("Tu consulta también puede hacer esto", "Imagen"),
        ("Desayuno para estabilizar la glucosa", "Reel"),
    ],
    "LinkedIn": [
        ("La longevidad como nueva especialidad clínica", "Artículo"),
        ("Por qué tu consulta necesita healthspan", "Publicación"),
        ("Resultados del primer grupo certificado", "Publicación"),
        ("Oportunidad de negocio en medicina preventiva", "Artículo"),
        ("Nuestro claustro, en 90 segundos", "Vídeo"),
        ("Qué piden hoy los pacientes de 45-60", "Publicación"),
        ("Cómo integrar healthspan en tu clínica", "Artículo"),
        ("El mercado de la longevidad en España", "Publicación"),
        ("Entrevista con nuestra directora médica", "Vídeo"),
        ("De fisioterapeuta a especialista en longevidad", "Publicación"),
    ],
}


def social_posts(desde, hasta) -> pd.DataFrame:
    """Publicaciones de ejemplo con sus métricas, una fila por post."""
    fechas = _rango_fechas(desde, hasta)
    if not fechas:
        return pd.DataFrame()

    filas = []
    for red, pf in _PERFIL_SOCIAL.items():
        r = _rng("social-posts-" + red)
        catalogo = _TITULOS_SOCIAL[red]
        # Ritmo de publicación real de cada red, escalado al periodo. Antes eran
        # 2 por semana para todas, lo que en 90 días generaba 25 publicaciones
        # inventadas de LinkedIn compitiendo en el ranking con las 10 reales de
        # Instagram. Nunca más publicaciones que títulos del catálogo.
        n_posts = max(1, round(pf["posts_mes"] * len(fechas) / 30))
        n_posts = min(n_posts, len(catalogo))
        for i in range(n_posts):
            titulo, tipo = catalogo[i % len(catalogo)]
            f = fechas[int(r.integers(0, len(fechas)))]
            # Distribución de alcance con cola larga: unos pocos posts se salen.
            multiplicador = float(r.pareto(1.6) + 0.4)
            views = max(12, int(pf["views"] * 0.45 * multiplicador))
            inter = int(views * pf["eng"] * r.uniform(0.6, 1.6))
            likes = int(inter * 0.78)
            comentarios = int(inter * 0.14)
            compartidos = max(0, inter - likes - comentarios)
            slug = f"{red[:2].lower()}{i:03d}"
            filas.append(dict(
                red=red, post_id=slug, fecha=f, tipo=tipo, titulo=titulo,
                url=f"https://example.invalid/{red.lower()}/{slug}",
                miniatura="",
                impresiones=int(views * r.uniform(1.05, 1.35)),
                visualizaciones=views,
                # Contador público acumulado: siempre >= las del periodo, porque
                # cuenta desde que se publicó. Solo YouTube lo publica aparte;
                # en las demás la regla de nulos lo anula al normalizar.
                visualizaciones_totales=int(views * r.uniform(1.0, 1.6)),
                likes=likes, comentarios=comentarios, compartidos=compartidos,
                clics=int(inter * r.uniform(0.1, 0.5)),
                guardados=int(inter * r.uniform(0.05, 0.25)),
            ))
    return pd.DataFrame(filas)
