"""
Configuración central del Dashboard de Marketing de Reversal Institute.

Todos los identificadores de cuenta, objetivos de negocio y el mapeo de
campañas viven aquí para que las páginas y los conectores lean de una
única fuente de verdad.

⚠️ CUENTAS = PLACEHOLDERS. Sustituye los IDs marcados con «TODO» por los
reales de Reversal cuando estén disponibles. Mientras tanto el dashboard
funciona con datos de ejemplo / caché.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Cuentas de plataforma  (TODO: rellenar con las cuentas reales de Reversal)
# --------------------------------------------------------------------------- #

# Google Ads (EUR). Cuenta "Reversal Institute" = 269-299-6145, que cuelga del
# MCC "MCC - Rise Marketing" (4885772142) — el MCC raíz que gestiona todo
# (UVic, Reversal, hofmann y el sub-MCC Nuclio 3963262878).
GOOGLE_ADS_CUSTOMER_ID = "2692996145"
GOOGLE_ADS_LOGIN_CUSTOMER_ID = "4885772142"  # MCC - Rise Marketing

# Meta Ads. Cuenta publicitaria "Reversal Institute" (business "Reversalinstitute").
META_AD_ACCOUNT_ID = "act_1252583410186224"
META_BUSINESS_ID = "2533051783778843"        # Reversalinstitute
META_PIXEL_DATASET_ID = "000000000000000"    # TODO píxel / dataset

# Google Analytics 4 — property "Web Reversal" del sitio reversal.institute.
GA4_PROPERTY_ID = "properties/542276987"

# HubSpot: portal de Reversal ("reversal institute").
HUBSPOT_PORTAL_ID = "147885062"

# --------------------------------------------------------------------------- #
# Objetivos de negocio  (TODO: ajustar a las proyecciones reales de Reversal)
# --------------------------------------------------------------------------- #

# Inversión mensual objetivo y matrículas (plazas de la certificación) objetivo.
OBJETIVO_INVERSION_MENSUAL = 10000.0   # TODO ajustar
OBJETIVO_MATRICULAS = 30               # TODO ajustar

# Valor económico medio de una matrícula (EUR) — precio de la certificación.
# Input clave del ROAS (ingresos = matrículas × VALOR_MATRICULA).
VALOR_MATRICULA = 2100.0               # ticket medio confirmado (8-jul-2026)

# CPL objetivo (coste por lead) de referencia para el semáforo. Ajustable.
CPL_OBJETIVO = 45.0

# Tasa de conversión lead -> matrícula esperada (para el forecast del embudo).
TASA_LEAD_A_MATRICULA = 0.06  # 6%

MONEDA = "EUR"
SIMBOLO_MONEDA = "€"

# --------------------------------------------------------------------------- #
# Caché (segundos). HubSpot cambia a diario -> refresco corto. Los ads cambian
# despacio y sus APIs tienen cuotas -> refresco más largo.
# --------------------------------------------------------------------------- #
CACHE_TTL_HUBSPOT = 300   # 5 min
CACHE_TTL_ADS = 1800      # 30 min
CACHE_TTL_GA4 = 1800      # 30 min


# --------------------------------------------------------------------------- #
# Segmentos de campaña  ->  la certificación se vende a varios perfiles del
# ecosistema wellness (ICP de Reversal). Aquí se mapea cada campaña de Google/
# Meta a un segmento, y el segmento a su valor en HubSpot.
#
# ⚠️ Los nombres de campaña son PLACEHOLDERS editables: sustitúyelos por los
# nombres reales cuando conectes las cuentas. La coincidencia es laxa (prefijo
# o subcadena), así que basta con que el nombre real contenga estas raíces.
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Segmento:
    """Un segmento de audiencia/campaña, sus campañas en cada plataforma y su
    valor en HubSpot (propiedad de contacto `hs_segmento`)."""
    nombre: str
    slug: str
    campana_google: str
    campana_meta: str
    hs_segmento: str  # valor de la propiedad de contacto en HubSpot


SEGMENTOS: list[Segmento] = [
    Segmento(
        nombre="Coaches & Salud",
        slug="coaches-salud",
        campana_google="Reversal_Search_Coaches",
        campana_meta="Reversal_Coaches",
        hs_segmento="coaches",
    ),
    Segmento(
        nombre="Entrenadores & Fitness",
        slug="entrenadores-fitness",
        campana_google="Reversal_Search_Entrenadores",
        campana_meta="Reversal_Entrenadores",
        hs_segmento="entrenadores",
    ),
    Segmento(
        nombre="Nutrición & Dietética",
        slug="nutricion-dietetica",
        campana_google="Reversal_Search_Nutricion",
        campana_meta="Reversal_Nutricion",
        hs_segmento="nutricion",
    ),
    Segmento(
        nombre="Clínicas & Fisioterapia",
        slug="clinicas-fisioterapia",
        campana_google="Reversal_Search_Clinicas",
        campana_meta="Reversal_Clinicas",
        hs_segmento="clinicas",
    ),
    Segmento(
        nombre="Estética & Wellness",
        slug="estetica-wellness",
        campana_google="Reversal_Search_Estetica",
        campana_meta="Reversal_Estetica",
        hs_segmento="estetica",
    ),
]

# Alias de compatibilidad: gran parte del código y de la UI usa «programa».
# En Reversal un «programa» ES un segmento de audiencia de la certificación.
PROGRAMAS = SEGMENTOS


def programa_por_campana(nombre_campana: str) -> str:
    """Devuelve el nombre del segmento dado el nombre de campaña (Google o Meta).

    Coincidencia laxa por prefijo/subcadena para tolerar sufijos y variaciones.
    """
    if not nombre_campana:
        return "Sin asignar"
    n = nombre_campana.strip().lower()
    for p in SEGMENTOS:
        for c in (p.campana_google, p.campana_meta):
            if n.startswith(c.lower()) or c.lower() in n:
                return p.nombre
    return "Otras / Branding"


def es_campana_werise(nombre_campana: str) -> bool:
    """True si la campaña pertenece a uno de los segmentos de Reversal (para
    acotar los datos en vivo de Google/Meta al scope del dashboard).

    (El nombre de la función se conserva por compatibilidad con los conectores.)
    """
    return programa_por_campana(nombre_campana) not in ("Otras / Branding", "Sin asignar")


def programa_por_curso(hs_segmento: str) -> str:
    """Devuelve el nombre del segmento dado el valor de `hs_segmento` (HubSpot)."""
    if not hs_segmento:
        return "Sin asignar"
    u = hs_segmento.strip().lower()
    for p in SEGMENTOS:
        if p.hs_segmento.lower() == u:
            return p.nombre
    return "Sin asignar"


# El portal 147885062 es EXCLUSIVO de Reversal: TODO contacto es un lead de
# Reversal (único curso = "Certificación en Longevidad y Healthspan"), así que
# no hace falta una propiedad-filtro; se cuentan todos los contactos del periodo.
#
# Dimensión de análisis de los leads = FUENTE/CANAL (`hs_analytics_source`), que
# es la única atribución poblada hoy (los UTM y el perfil profesional están vacíos).
#
# La propiedad de perfil profesional del ICP existe pero está SIN RELLENAR (58/59
# vacía a jul-2026). Cuando el equipo empiece a cualificar leads con ella, cambia
# la dimensión poniendo aquí su nombre y usándola en el conector.
HUBSPOT_PROP_SEGMENTO = "perfil_titulacion"  # (vacía hoy; dimensión activa = fuente)

# hs_analytics_source (crudo) -> nombre amigable de canal.
FUENTE_AMIGABLE = {
    "PAID_SOCIAL": "Paid Social (Meta)",
    "PAID_SEARCH": "Paid Search (Google)",
    "ORGANIC_SEARCH": "Búsqueda orgánica",
    "SOCIAL_MEDIA": "Social orgánico",
    "DIRECT_TRAFFIC": "Directo",
    "REFERRALS": "Referido",
    "EMAIL_MARKETING": "Email",
    "OTHER_CAMPAIGNS": "Otras campañas",
    "OFFLINE": "Offline",
}


def fuente_amigable(hs_analytics_source: str) -> str:
    """Traduce el valor crudo de hs_analytics_source a un nombre de canal legible."""
    if not hs_analytics_source:
        return "Sin atribuir"
    return FUENTE_AMIGABLE.get(hs_analytics_source.strip().upper(),
                               hs_analytics_source.replace("_", " ").title())


# Propiedad de contacto que mejor captura la especialidad del lead (168/172
# rellenos, frente a 4/172 de perfil_titulacion).
HUBSPOT_PROP_PROFESION = "profesion"

# profesion (texto libre en minúsculas) -> etiqueta legible de especialidad.
PROFESION_LABEL = {
    "medico": "Médico",
    "otro": "Otro",
    "coach": "Coach de salud",
    "esteticista": "Esteticista",
    "nutricionista": "Nutricionista",
    "clinica": "Owner clínica",
    "entrenador": "Entrenador",
    "farmacia": "Farmacia",
    "enfermeria": "Enfermería",
    "yoga": "Yoga / Pilates",
    "fisio": "Fisioterapeuta",
    "osteopata": "Osteópata",
}


def especialidad_amigable(valor: str) -> str:
    """profesion cruda -> etiqueta legible (especialidad profesional del lead)."""
    if not valor:
        return "Sin especificar"
    return PROFESION_LABEL.get(valor.strip().lower(),
                               valor.replace("_", " ").capitalize())


# Normaliza variantes de nombre de país (ES/EN) a una etiqueta canónica en español.
PAIS_CANONICO = {
    "spain": "España", "espana": "España", "españa": "España",
    "france": "Francia", "francia": "Francia",
    "united kingdom": "Reino Unido", "uk": "Reino Unido", "reino unido": "Reino Unido",
    "united states": "Estados Unidos", "usa": "Estados Unidos",
    "estados unidos": "Estados Unidos",
    "mexico": "México", "méxico": "México",
    "germany": "Alemania", "alemania": "Alemania",
    "portugal": "Portugal", "italy": "Italia", "italia": "Italia",
    "argentina": "Argentina", "colombia": "Colombia", "chile": "Chile",
}


def pais_amigable(valor: str) -> str:
    """Nombre de país auto-declarado -> etiqueta canónica en español."""
    if not valor:
        return "Sin país"
    v = valor.strip()
    return PAIS_CANONICO.get(v.lower(), v.title())


# Estado de campaña -> etiqueta en español. Cubre el vocabulario de Google Ads
# (campaign.status) y el de Meta (status / effective_status).
ESTADO_CAMPANA = {
    # Google Ads
    "ENABLED": "Activa",
    "PAUSED": "Pausada",
    "REMOVED": "Eliminada",
    # Meta
    "ACTIVE": "Activa",
    "ARCHIVED": "Archivada",
    "DELETED": "Eliminada",
    "CAMPAIGN_PAUSED": "Pausada",
    "ADSET_PAUSED": "Pausada (conjunto)",
    "IN_PROCESS": "En revisión",
    "PENDING_REVIEW": "En revisión",
    "WITH_ISSUES": "Con incidencias",
    "DISAPPROVED": "Rechazada",
    "PREAPPROVED": "Preaprobada",
    "PENDING_BILLING_INFO": "Falta facturación",
}


def estado_campana(valor: str) -> str:
    """Estado crudo de la campaña (Google/Meta) -> etiqueta legible."""
    if not valor:
        return "—"
    return ESTADO_CAMPANA.get(valor.strip().upper(),
                              valor.replace("_", " ").capitalize())


# Nexo ads <-> leads: cada plataforma publicitaria corresponde a un canal de
# hs_analytics_source, de modo que la inversión se cruza con los leads por canal.
PLATAFORMA_CANAL = {
    "Google Ads": "Paid Search (Google)",
    "Meta Ads": "Paid Social (Meta)",
}


def canal_por_plataforma(plataforma: str) -> str:
    """Canal (hs_analytics_source amigable) al que pertenece una plataforma de ads."""
    return PLATAFORMA_CANAL.get(plataforma, plataforma or "Sin atribuir")


# Nombre de campaña del lead. Los UTM están vacíos, pero HubSpot guarda el
# desglose de la fuente en hs_analytics_source_data_1/2. Para tráfico de pago el
# nombre de campaña suele venir en source_data_2 (p.ej. "nac - longevidad y
# healthspan", "test mestral — entrenadores"); source_data_1 es la red
# (Instagram/Facebook) o, en "otras campañas", la propia campaña.
_CAMPANA_REDES = {"facebook", "instagram", "google", "auto-tagged ppc"}
# Solo estas fuentes traen campaña real (pago / campañas rastreadas). El tráfico
# directo/orgánico/referido no tiene campaña (su source_data suele ser una URL).
_CAMPANA_FUENTES = {"PAID_SOCIAL", "PAID_SEARCH", "OTHER_CAMPAIGNS", "EMAIL_MARKETING"}


def _es_ruido_campana(v: str) -> bool:
    vl = v.lower()
    return (not v) or ("instagram_feed" in vl) or ("instagram_reels" in vl) \
        or vl.startswith("userid:") or vl.startswith("ig'") or ("/" in v) \
        or ("reversal.institute" in vl) or ("http" in vl) or ("meetings-" in vl) \
        or vl in {"keyword", "unknown keywords (ssl)", "google"}


# Alias UTM (HubSpot) -> nombre real de la campaña en la plataforma. Úsalo cuando
# el utm_campaign no coincide con el nombre de la campaña de Google/Meta.
# Clave en minúsculas; se compara normalizado.
HUBSPOT_CAMPANA_ALIAS = {
    "trafico_nac_marca": "NAC_Marca-Trafico-Search",
}


def campana_hubspot(source: str, source_data_1: str, source_data_2: str) -> str:
    """Deriva el nombre de campaña desde hs_analytics_source_data_1/2.

    El nombre de campaña vive en un campo distinto según la fuente:
    - **Paid Social** (Meta): en `source_data_2` (data_1 es la red Instagram/Facebook).
    - **Paid Search** (Google) y **Otras campañas / Email**: en `source_data_1`
      (en Paid Search, data_2 es la keyword).

    Solo para fuentes de pago/campaña; el resto devuelve "Sin campaña".
    """
    src = (source or "").strip().upper()
    if src not in _CAMPANA_FUENTES:
        return "Sin campaña"
    d1 = (source_data_1 or "").strip()
    d2 = (source_data_2 or "").strip()
    # Orden de preferencia del campo donde está la campaña, según la fuente.
    candidatos = (d2, d1) if src == "PAID_SOCIAL" else (d1, d2)
    for c in candidatos:
        if c and not _es_ruido_campana(c) and c.lower() not in _CAMPANA_REDES:
            return HUBSPOT_CAMPANA_ALIAS.get(c.strip().lower(), c)
    return "Sin campaña"


# --------------------------------------------------------------------------- #
# GA4 — analítica de TODO el sitio (reversal.institute), no solo landings.
# El tráfico se agrupa por canal (sessionDefaultChannelGroup).
# --------------------------------------------------------------------------- #
CANALES_GA4 = [
    "Organic Search", "Paid Search", "Organic Social", "Paid Social",
    "Direct", "Referral", "Email", "Display",
]


# --------------------------------------------------------------------------- #
# HubSpot — Pipeline "Sales Pipeline" y etapas reales del portal 147885062.
# (Verificado vía API el 8-jul-2026.)
# --------------------------------------------------------------------------- #
HUBSPOT_PIPELINE_UVIC = "default"           # "Sales Pipeline"
HUBSPOT_STAGE_MATRICULA = "closedwon"       # "Closed Won" = matrícula

# Etapas del pipeline en orden (id -> etiqueta). El embudo se dibuja así.
HUBSPOT_ETAPAS_UVIC = [
    ("5004299502", "Oportunidad"),
    ("appointmentscheduled", "Entrevista concertada"),
    ("presentationscheduled", "Entrevista realizada"),
    ("contractsent", "Envío de inscripción"),
    ("closedwon", "Cierre ganado"),
]
HUBSPOT_ETAPA_PERDIDO = ("closedlost", "Cierre perdido")
HUBSPOT_ETAPAS_MAP = dict(HUBSPOT_ETAPAS_UVIC + [HUBSPOT_ETAPA_PERDIDO])
# Orden completo del pipeline (incluye Cierre perdido) para la vista de tablero.
HUBSPOT_ETAPAS_TODAS = [e for _, e in HUBSPOT_ETAPAS_UVIC] + [HUBSPOT_ETAPA_PERDIDO[1]]

# Propiedad de deal con el motivo de pérdida ("Motivo de cierre perdido del
# negocio", select relleno al 100%). `closed_lost_reason` está vacía en el portal.
HUBSPOT_PROP_MOTIVO_PERDIDO = "motivo_de_cierre"


# --------------------------------------------------------------------------- #
# Paleta y colores por plataforma (consistentes en todo el dashboard)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Tema:
    # Colores REALES de Reversal Institute (design tokens de reversal.institute).
    primario: str = "#0E7C52"       # --vital  (verde vital, color de marca)
    secundario: str = "#0A4F36"     # --vital-deep (verde profundo)
    verde_bright: str = "#18A86E"   # --vital-bright (verde brillante/acento)
    verde_tint: str = "#E4F0E8"     # --vital-tint (verde muy claro)
    gris_uvic: str = "#41454C"      # --ink-2 (gris corporativo)
    texto: str = "#0E0F12"          # --ink (texto casi negro)
    papel: str = "#F6F4EF"          # --paper (fondo crema)
    papel_2: str = "#EFEBE3"        # --paper-2 (fondo secundario)
    # Colores de identidad por plataforma (se mantienen para distinguir series).
    color_google: str = "#4285F4"
    color_meta: str = "#0866FF"
    color_ga4: str = "#E8710A"
    color_hubspot: str = "#FF7A59"
    # Semáforo de estado (ok = verde marca, off = terracota de la web).
    verde_ok: str = "#18A86E"       # --vital-bright
    ambar_riesgo: str = "#C0892E"   # ámbar cálido (armoniza con crema/verde)
    rojo_off: str = "#B2402E"       # --danger
    # Paleta de gráficos: lidera el verde Reversal, luego neutros/acentos.
    paleta: tuple = field(default_factory=lambda: (
        "#0E7C52", "#18A86E", "#0A4F36", "#41454C", "#B2402E", "#C0892E",
    ))


TEMA = Tema()

COLOR_PLATAFORMA = {
    "Google Ads": TEMA.color_google,
    "Meta Ads": TEMA.color_meta,
    "Google Analytics": TEMA.color_ga4,
    "HubSpot": TEMA.color_hubspot,
    # Las redes de social orgánico se añaden más abajo (COLOR_RED_SOCIAL), para
    # que los gráficos las pinten con su color de marca sin tocar los componentes.
}


# --------------------------------------------------------------------------- #
# SOCIAL ORGÁNICO — YouTube, Facebook, Instagram y LinkedIn.
#
# ⚠️ LEE ESTO ANTES DE TOCAR LAS MÉTRICAS DE SOCIAL.
#
# Las 4 redes NO dan las mismas métricas, así que el esquema normalizado tiene
# columnas que unas redes rellenan y otras dejan a NULO. Un nulo aquí significa
# «esta red no publica este dato», que NO es lo mismo que un cero.
#
# Poner 0 en lugar de nulo haría que un KPI agregado («impresiones totales»)
# saliera artificialmente bajo y que las comparativas entre redes mintieran sin
# avisar — justo la decisión (¿en qué red invierto?) que este panel debe apoyar.
# Por eso el soporte se declara aquí y `src/data/social.py` lo IMPONE: cualquier
# valor que un conector escriba en una casilla no soportada se convierte a nulo.
# --------------------------------------------------------------------------- #

REDES_SOCIAL: tuple[str, ...] = ("YouTube", "Facebook", "Instagram",
                                 "LinkedIn", "TikTok")

# Colores de identidad de cada red en los gráficos.
#
# ⚠️ NO son los colores de marca, y es a propósito. Los cuatro oficiales chocan
# por parejas: el rojo de YouTube con el rosa de Instagram, y el azul de Facebook
# con el de LinkedIn. Medido sobre el fondo real (#F6F4EF), Instagram y YouTube
# quedaban a ΔE 10,4 en visión normal —por debajo de 15, el umbral a partir del
# cual se distinguen con seguridad— y a ΔE 5,1 en daltonismo tritan: la misma
# línea a efectos prácticos. En una página cuyo trabajo es comparar redes entre
# sí, eso no es un detalle estético.
#
# Esta paleta mantiene los dos colores más icónicos y más separados entre sí
# (rojo de YouTube, azul de Facebook) y lleva las otras dos al espacio de tono
# que queda libre: Instagram al morado —que sí está en su degradado— y LinkedIn
# al verde azulado. Validada con el script del skill `dataviz`: pasa banda de
# luminosidad, croma, contraste y separación en TODAS las parejas, con el peor
# caso en ΔE 9,0 (deutan) y 8,1 (tritan), ambos por encima del mínimo de 8.
#
# Si tocas un color, revalida — no lo juzgues a ojo:
#   node scripts/validate_palette.js "<hex,hex,hex,hex,hex>" \
#        --mode light --surface "#F6F4EF" --pairs all
#
# Con CINCO series el margen es estrecho: el peor par (TikTok↔Instagram) queda en
# ΔE 6,2 bajo protanopia, dentro de la banda 6-8 que el método admite SOLO si
# hay codificación secundaria. La hay —cada red tiene su propio símbolo de
# punto—, así que la identidad nunca depende únicamente del color. Si algún día
# se quitan los símbolos, esta paleta deja de ser válida.
COLOR_RED_SOCIAL = {
    "YouTube": "#E03131",    # rojo
    "Facebook": "#4DABF7",   # azul
    "Instagram": "#AE3EC9",  # morado (presente en su degradado de marca)
    "LinkedIn": "#0CA678",   # verde azulado
    # ⚠️ TikTok NO lleva su color de marca, y es la excepción más forzada de las
    # cinco. Su rojo/rosa (#FE2C55) queda a ΔE 7,0 del rojo de YouTube en visión
    # normal —prácticamente la misma línea— y su cian choca con el verde azulado
    # de LinkedIn. Con el rojo ocupado por YouTube, toda la mitad cálida del
    # círculo de tonos es inviable: en deuteranopia, ámbar y naranja convergen
    # con el rojo. El índigo es el único hueco que pasa las cinco
    # comprobaciones (barrido de ~40 candidatos, 31-jul-2026).
    "TikTok": "#4263EB",     # índigo
}

# Segundo canal de identidad, además del color: cada red lleva su propio símbolo
# de punto. Así la serie se sigue distinguiendo con visión de color reducida, en
# impresión en gris, o cuando dos líneas se cruzan y se solapan.
SIMBOLO_RED_SOCIAL = {
    "YouTube": "circle",
    "Facebook": "square",
    "Instagram": "diamond",
    "LinkedIn": "triangle-up",
    "TikTok": "star",
}

COLOR_PLATAFORMA.update(COLOR_RED_SOCIAL)

# Métricas del esquema diario (nivel cuenta) -> etiqueta legible.
METRICAS_SOCIAL = {
    "impresiones": "Impresiones",
    "visualizaciones": "Visualizaciones",
    "alcance": "Alcance",
    "seguidores_nuevos": "Nuevos seguidores",
    "likes": "Likes",
    "comentarios": "Comentarios",
    "compartidos": "Compartidos",
    "mensajes": "Mensajes",
}

# Métricas del esquema por publicación -> etiqueta legible.
METRICAS_POST = {
    "impresiones": "Impresiones",
    "visualizaciones": "Visualizaciones",
    "likes": "Likes",
    "comentarios": "Comentarios",
    "compartidos": "Compartidos",
    "clics": "Clics",
    "visualizaciones_totales": "Visualiz. totales",
    "guardados": "Guardados",
}

# Qué red publica de verdad cada métrica diaria por API (verificado jul-2026).
#
# - Instagram NO tiene «impresiones»: Meta la retiró el 21-abr-2025 (Graph v22.0)
#   y la sustituyó por `views`, que aquí es `visualizaciones`.
# - «Mensajes» (DMs / conversaciones nuevas) solo existe a nivel de cuenta y solo
#   en Facebook (`page_messages_new_conversations_unique`, requiere el permiso
#   `pages_messaging`). Ninguna red lo atribuye a una publicación concreta.
# - YouTube no tiene concepto de alcance único ni de mensajes.
# ⚠️ Facebook actualizado el 30-jul-2026 con lo que devuelve la Página REAL, no
# con lo que dice la documentación: Meta ha retirado toda la familia
# `page_impressions*` a nivel de Página, así que Facebook se queda SIN
# impresiones y SIN alcance. Lo que sí publica son las impresiones orgánicas de
# sus publicaciones, que es lo que alimenta `visualizaciones` (el mismo concepto
# que el `views` de Instagram). Ver la cabecera de `meta_organico._MAPA_FB_DIA`.
SOPORTE_METRICA_SOCIAL: dict[str, set[str]] = {
    "impresiones": {"LinkedIn"},
    "visualizaciones": {"YouTube", "Facebook", "Instagram", "LinkedIn", "TikTok"},
    "alcance": {"Instagram", "LinkedIn"},
    # TikTok NO: su Display API solo da el `follower_count` actual, nunca las
    # altas del día. Comprobado el 31-jul-2026 contra la cuenta real.
    "seguidores_nuevos": {"YouTube", "Facebook", "Instagram", "LinkedIn"},
    "likes": {"YouTube", "Facebook", "Instagram", "LinkedIn", "TikTok"},
    "comentarios": {"YouTube", "Facebook", "Instagram", "LinkedIn", "TikTok"},
    "compartidos": {"YouTube", "Facebook", "Instagram", "LinkedIn", "TikTok"},
    "mensajes": {"Facebook"},
}

# Ídem por publicación. «Guardados» solo lo da Instagram (`saved`).
#
# ⚠️ Facebook NO está en «impresiones»: aunque a nivel de Página la retirada ya
# estaba documentada arriba, la familia `post_impressions*` a nivel de
# PUBLICACIÓN también está retirada. Sondeado uno a uno contra la Página real
# el 30-jul-2026: `post_impressions`, `post_impressions_organic`,
# `post_impressions_unique` y `post_impressions_organic_unique` responden las
# cuatro «(#100) The value must be a valid insights metric». Declarar aquí
# a Facebook como soportado sin que la API la sirva es la misma mentira que la
# regla de nulo≠cero existe para evitar, solo que al revés: prometer un dato
# que nunca va a llegar. Ver `meta_organico._METRICAS_POST_FB` (no la pide).
SOPORTE_METRICA_POST: dict[str, set[str]] = {
    "impresiones": {"LinkedIn"},
    # TikTok sí, en las cuatro: `video/list/` devuelve view_count, like_count,
    # comment_count y share_count acumulados por vídeo. Sondeado el 31-jul-2026
    # contra @reversal.institute — 10 de 10 vídeos con dato en las cuatro.
    "visualizaciones": {"YouTube", "Facebook", "Instagram", "LinkedIn", "TikTok"},
    "likes": {"YouTube", "Facebook", "Instagram", "LinkedIn", "TikTok"},
    "comentarios": {"YouTube", "Facebook", "Instagram", "LinkedIn", "TikTok"},
    "compartidos": {"YouTube", "Facebook", "Instagram", "LinkedIn", "TikTok"},
    # Clics en la publicación. Los dan Facebook (`post_clicks`) y LinkedIn
    # (`clickCount`); Instagram y YouTube no. Verificado contra las cuentas
    # reales el 30-jul-2026. Es la métrica de orgánico más cercana a intención:
    # mide quién quiso saber más, no quién pasó el dedo.
    "clics": {"Facebook", "LinkedIn"},
    # Contador PÚBLICO acumulado del vídeo, el mismo que se ve en YouTube
    # Studio. Solo YouTube lo da como número aparte: en Instagram y Facebook las
    # métricas por publicación YA son acumuladas desde que se publicó, así que
    # una columna «totales» duplicaría la que ya hay.
    #
    # Existe porque Studio y Analytics no siempre coinciden: verificado el
    # 30-jul-2026, un vídeo con 1.203 visualizaciones en el contador público no
    # aparecía en Analytics en ninguna ventana. Sin esta columna, ese vídeo se
    # ve como «—» y parece que no lo vio nadie.
    "visualizaciones_totales": {"YouTube"},
    "guardados": {"Instagram"},
}

# Pares (métrica, red) sin confirmar contra la cuenta real, que hasta entonces se
# tratan como NO soportados (=> nulo). Es la red de seguridad para no publicar un
# número que nadie ha visto funcionar.
#
# Vacío desde el 30-jul-2026: el único pendiente era ("impresiones", "YouTube") y
# ya está comprobado contra el canal real (UCAsFeXWR-s8Wkj0lmGhtx1A). La YouTube
# Analytics API v2 responde HTTP 400 al pedir `impressions` en un reporte de
# canal: en Studio se ve, por la API no se puede sacar. YouTube se queda fuera de
# SOPORTE_METRICA_SOCIAL["impresiones"] por derecho propio, no por precaución.
# Vacío también para TikTok desde el 31-jul-2026. Sondeado contra la cuenta real
# (@reversal.institute, sandbox de la app) con `verificar_social.py --red
# TikTok`: visualizaciones, likes, comentarios y compartidos responden en 10 de
# 10 vídeos, así que salen de aquí por derecho propio.
#
# `seguidores_nuevos` NO se ha movido aquí: se ha quitado directamente de
# SOPORTE_METRICA_SOCIAL. No es que esté sin verificar, es que la Display API no
# lo publica — solo da el `follower_count` ACTUAL, nunca el alta del día. El
# histórico acumula fotos, y restar dos fotos consecutivas daría un número que
# la API no ha dicho.
SOPORTE_POR_VERIFICAR: set[tuple[str, str]] = set()

# Redes cuya API NO da serie diaria de métricas de flujo. Solo publican el
# acumulado de cada publicación, así que el total del periodo hay que sacarlo
# sumando publicaciones.
#
# Y ese total NO significa lo mismo: es «visualizaciones totales de lo PUBLICADO
# en el periodo», no «visualizaciones ocurridas DURANTE el periodo». Un vídeo de
# hace un año que hoy se vuelve viral no aparece; uno publicado ayer aporta todo
# su acumulado. Por eso el dato se muestra en la pestaña de la red —con la
# advertencia escrita al lado— pero NO entra en las comparativas entre redes del
# Resumen, donde falsearía la única métrica que iguala a las cinco.
REDES_SIN_SERIE_DIARIA: frozenset[str] = frozenset({"TikTok"})

# Métrica que se usa como KPI principal comparable entre las 4 redes. NO se usa
# «impresiones» porque Instagram ya no la publica (ver nota de arriba).
METRICA_COMPARABLE = "visualizaciones"

# Interacciones = suma de las métricas de engagement. Las 4 redes dan las tres,
# así que este agregado SÍ es comparable entre redes.
METRICAS_INTERACCION = ("likes", "comentarios", "compartidos")

# Cuentas de social orgánico. Los IDs NO son secretos (son públicos en la propia
# ficha de cada perfil), así que viven aquí y no en secrets.toml: lo único que
# hace falta poner en secrets es el token de cada red.
YOUTUBE_CHANNEL_ID = "UCAsFeXWR-s8Wkj0lmGhtx1A"  # Canal "Reversal Institute"
SOCIAL_FACEBOOK_PAGE_ID = "1229909610199926"    # Página "Reversal Institute"
SOCIAL_INSTAGRAM_USER_ID = "17841409682113567"  # @reversal_institute
LINKEDIN_ORGANIZATION_ID = "123114024"          # Página "Reversal Institute"

# El social orgánico se mueve despacio y sus APIs tienen cuotas ajustadas.
CACHE_TTL_SOCIAL = 3600  # 1 h

# Umbrales de muestra de los bloques de análisis por red.
#
# Viven aquí y no repartidos por el código porque el volumen de publicaciones
# está creciendo (Facebook subiendo su histórico atrasado): el punto a partir
# del cual estos bloques dicen algo se va a mover, y moverlo debe ser cambiar
# una línea.
MIN_PUBLICACIONES_BOTTOM = 6   # por debajo, «la peor» es casi «la segunda»
MIN_PUBLICACIONES_FORMATO = 3  # una media de 1 publicación no es una media


def soporta_metrica(metrica: str, red: str, ambito: str = "diario") -> bool:
    """True si `red` publica `metrica` por API en el ámbito dado.

    `ambito`: "diario" (nivel cuenta) o "post" (por publicación).
    Los pares pendientes de verificar cuentan como NO soportados.
    """
    if (metrica, red) in SOPORTE_POR_VERIFICAR:
        return False
    tabla = SOPORTE_METRICA_POST if ambito == "post" else SOPORTE_METRICA_SOCIAL
    return red in tabla.get(metrica, set())


def redes_sin_metrica(metrica: str, ambito: str = "diario") -> list[str]:
    """Redes que NO publican la métrica (para avisar al pie de cada agregado)."""
    return [r for r in REDES_SOCIAL if not soporta_metrica(metrica, r, ambito)]


def metricas_comparables(ambito: str = "diario") -> list[str]:
    """Métricas que las 4 redes publican, y que por tanto se pueden sumar y
    comparar entre redes sin nota al pie."""
    metricas = METRICAS_POST if ambito == "post" else METRICAS_SOCIAL
    return [m for m in metricas if not redes_sin_metrica(m, ambito)]
