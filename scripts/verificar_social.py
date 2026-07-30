"""
Diagnóstico de las credenciales de social orgánico.

    python scripts/verificar_social.py              # las 3 fuentes
    python scripts/verificar_social.py --red Meta   # solo una

Comprueba, para cada red, que la credencial de `.streamlit/secrets.toml` sirve
DE VERDAD: no solo que exista, sino que el token tenga los permisos que hacen
falta y que la API devuelva las métricas que el dashboard espera. Cada fallo
sale con la corrección concreta al lado.

Es la herramienta de acompañamiento para conectar las redes una a una: se
rellena una sección, se ejecuta esto, y dice si ya está o qué falta.

## Además resuelve dos incógnitas que hay marcadas en el código

- **Nombres de métrica de Facebook.** Meta renombra y deprecia las Page Insights
  a menudo, y `meta_organico._MAPA_FB_DIA` lleva varios candidatos por métrica
  «a ver cuál cuela». Este script prueba cada candidato por separado y dice cuál
  acepta la Página real, para poder dejar el mapa con hechos en vez de apuestas.
- **`impressions` en YouTube.** `config.SOPORTE_POR_VERIFICAR` lo trata como no
  soportado porque no está confirmado que la Analytics API v2 lo dé a nivel de
  canal. Aquí se pide y se ve.

No escribe nada: solo lee y reporta.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src import config  # noqa: E402
from src.connectors import linkedin, meta_organico, youtube  # noqa: E402
from src.connectors.base import _leer_secreto  # noqa: E402

OK, FALLO, AVISO, INFO = "✓", "✗", "!", "·"

# Permisos que el token de [social_meta] necesita. `pages_messaging` es aparte:
# sin él solo se pierde la métrica de mensajes, no el resto.
_SCOPES_META = ("pages_show_list", "pages_read_engagement", "read_insights",
                "instagram_basic", "instagram_manage_insights")
_SCOPE_MENSAJES = "pages_messaging"


class Informe:
    def __init__(self, red: str):
        self.red = red
        self.lineas: list[tuple[str, str, str]] = []

    def add(self, estado: str, texto: str, pista: str = "") -> None:
        self.lineas.append((estado, texto, pista))

    @property
    def hay_fallos(self) -> bool:
        return any(e == FALLO for e, _, _ in self.lineas)

    def imprimir(self) -> None:
        print(f"\n{'─' * 72}\n{self.red}\n{'─' * 72}")
        for estado, texto, pista in self.lineas:
            print(f"  {estado} {texto}")
            if pista:
                for linea in pista.splitlines():
                    print(f"      → {linea}")


def _falta_seccion(inf: Informe, seccion: str, donde: str) -> None:
    inf.add(FALLO, f"No hay sección [{seccion}] en .streamlit/secrets.toml",
            f"Es el primer paso. {donde}")


# --------------------------------------------------------------------------- #
# Meta: Facebook + Instagram
# --------------------------------------------------------------------------- #

def verificar_meta() -> Informe:
    inf = Informe("Facebook + Instagram  ([social_meta])")
    creds = _leer_secreto("social_meta")
    if not creds:
        _falta_seccion(inf, "social_meta",
                       "Genera un token de System User en "
                       "business.facebook.com/settings/system-users")
        return inf

    token = creds.get("access_token", "")
    if not token:
        inf.add(FALLO, "access_token vacío")
        return inf
    inf.add(OK, f"access_token presente ({len(token)} caracteres)")

    version = meta_organico._version(creds)

    # --- Permisos del token ------------------------------------------------ #
    concedidos: set[str] = set()
    try:
        datos = meta_organico._get(version, "debug_token", token,
                                   {"input_token": token}).get("data", {})
        concedidos = set(datos.get("scopes", []))
        tipo = datos.get("type", "?")
        caduca = datos.get("expires_at", 0)
        inf.add(OK, f"Token válido (tipo {tipo}"
                    + (", sin caducidad" if caduca == 0 else f", caduca en {caduca}") + ")")
        if caduca:
            inf.add(AVISO, "El token CADUCA",
                    "Para un job diario usa un token de System User sin "
                    "caducidad, o tendrás que renovarlo a mano.")
    except Exception as e:  # noqa: BLE001
        inf.add(AVISO, f"No se han podido leer los permisos del token: {e}",
                "Seguimos con las comprobaciones reales, que son las que mandan.")

    if concedidos:
        faltan = [s for s in _SCOPES_META if s not in concedidos]
        if faltan:
            inf.add(FALLO, f"Faltan permisos: {', '.join(faltan)}",
                    "Añádelos al System User y vuelve a generar el token. "
                    "OJO: el token de [meta_ads] NO sirve, solo tiene ads_*.")
        else:
            inf.add(OK, "Están los 5 permisos obligatorios")
        if _SCOPE_MENSAJES not in concedidos:
            inf.add(AVISO, f"Sin {_SCOPE_MENSAJES}: la métrica «mensajes» saldrá nula",
                    "Es la única métrica que se pierde; el resto funciona igual.")

    # --- Página ------------------------------------------------------------ #
    page_id = creds.get("page_id") or config.SOCIAL_FACEBOOK_PAGE_ID
    if not page_id:
        inf.add(FALLO, "Falta page_id",
                "Candidato detectado por la cuenta publicitaria: 1229909610199926")
        return inf

    try:
        page_id, page_token = meta_organico._token_pagina(creds)
        propio = page_token != token
        inf.add(OK, f"Página accesible: {page_id}"
                    + (" (token de Página obtenido)" if propio else " (token ya es de Página)"))
    except Exception as e:  # noqa: BLE001
        inf.add(FALLO, f"No se puede acceder a la Página {page_id}: {e}",
                "Asigna la Página al System User en Business Settings → "
                "System Users → Assign Assets.")
        return inf

    try:
        info = meta_organico._get(version, page_id, page_token,
                                  {"fields": "name,followers_count"})
        inf.add(OK, f"Página = «{info.get('name')}» · "
                    f"{info.get('followers_count', '?')} seguidores",
                "Confirma que es la de Reversal Institute.")
    except Exception as e:  # noqa: BLE001
        inf.add(AVISO, f"No se ha podido leer el nombre de la Página: {e}")

    # --- Qué nombres de métrica acepta esta Página ------------------------- #
    inf.add(INFO, "Probando los nombres de métrica de Page Insights…")
    _probar_metricas(inf, version, page_id, page_token,
                     meta_organico._MAPA_FB_DIA, "Facebook")

    # --- Instagram --------------------------------------------------------- #
    try:
        ig = meta_organico._ig_user_id(creds, page_id, page_token)
        datos = meta_organico._get(version, ig, page_token,
                                   {"fields": "username,followers_count"})
        inf.add(OK, f"Instagram vinculado: @{datos.get('username')} · "
                    f"{datos.get('followers_count', '?')} seguidores")
        _probar_metricas(inf, version, ig, page_token,
                         meta_organico._MAPA_IG_DIA, "Instagram")
    except Exception as e:  # noqa: BLE001
        inf.add(FALLO, f"Instagram no disponible: {e}",
                "La cuenta tiene que ser Business/Creator y estar vinculada a "
                "la Página. Facebook seguirá funcionando sin esto.")

    return inf


def _probar_metricas(inf: Informe, version: str, objeto_id: str, token: str,
                     mapa: dict[str, list[str]], red: str) -> None:
    """Pide cada candidato por separado y dice cuál acepta la cuenta real."""
    hasta = date.today() - timedelta(days=1)
    desde = hasta - timedelta(days=6)
    for metrica, candidatos in mapa.items():
        ganador = None
        errores = []
        for cand in candidatos:
            try:
                datos = meta_organico._get(
                    version, f"{objeto_id}/insights", token,
                    {"metric": cand, "period": "day",
                     "since": str(desde), "until": str(hasta)})
                if datos.get("data"):
                    ganador = cand
                    break
                errores.append(f"{cand}: responde vacío")
            except Exception as e:  # noqa: BLE001
                errores.append(f"{cand}: {str(e)[:70]}")
        if ganador:
            marca = OK if ganador == candidatos[0] else AVISO
            extra = ("" if ganador == candidatos[0]
                     else f" (el preferido «{candidatos[0]}» no vale)")
            inf.add(marca, f"{red}/{metrica}: usa «{ganador}»{extra}",
                    "" if ganador == candidatos[0]
                    else f"Pon «{ganador}» el primero en el mapa del conector.")
        else:
            soportada = config.soporta_metrica(metrica, red)
            inf.add(AVISO if not soportada else FALLO,
                    f"{red}/{metrica}: ningún nombre funciona",
                    "\n".join(errores[:3]))


# --------------------------------------------------------------------------- #
# YouTube
# --------------------------------------------------------------------------- #

def verificar_youtube() -> Informe:
    inf = Informe("YouTube  ([youtube])")
    creds = _leer_secreto("youtube")
    if not creds:
        _falta_seccion(inf, "youtube",
                       "Habilita YouTube Data API v3 + YouTube Analytics API y "
                       "crea un OAuth client de tipo Desktop.")
        return inf

    faltan = [k for k in ("client_id", "client_secret", "refresh_token")
              if not creds.get(k)]
    if faltan:
        inf.add(FALLO, f"Faltan claves: {', '.join(faltan)}",
                "Genera el refresh token con scripts/youtube_refresh_token.py, "
                "con la cuenta PROPIETARIA del canal.")
        return inf
    inf.add(OK, "client_id, client_secret y refresh_token presentes")

    try:
        analytics, data = youtube._servicios(creds)
        inf.add(OK, "El refresh token se canjea correctamente")
    except Exception as e:  # noqa: BLE001
        inf.add(FALLO, f"No se puede autenticar: {e}",
                "Si dice invalid_grant, el refresh token está revocado o es de "
                "otra cuenta: vuelve a generarlo.")
        return inf

    canal = youtube._canal(creds)
    try:
        params = {"part": "snippet,statistics"}
        params["id" if canal else "mine"] = canal or True
        items = data.channels().list(**params).execute().get("items", [])
        if not items:
            inf.add(FALLO, "La API no devuelve ningún canal",
                    "Revisa channel_id, o quita el campo para usar «mine».")
            return inf
        c = items[0]
        inf.add(OK, f"Canal = «{c['snippet']['title']}» ({c['id']}) · "
                    f"{c['statistics'].get('subscriberCount', '?')} suscriptores")
        if not canal:
            inf.add(AVISO, "No hay channel_id configurado; se usa «mine»",
                    f"Mejor fíjalo: channel_id = \"{c['id']}\"")
    except Exception as e:  # noqa: BLE001
        inf.add(FALLO, f"Data API v3 falla: {e}",
                "¿Está habilitada YouTube Data API v3 en el proyecto?")
        return inf

    hasta = date.today() - timedelta(days=1)
    desde = hasta - timedelta(days=6)
    ids = f"channel=={canal}" if canal else "channel==MINE"
    try:
        resp = analytics.reports().query(
            ids=ids, startDate=str(desde), endDate=str(hasta),
            metrics=youtube._METRICAS_DIA, dimensions="day", sort="day").execute()
        filas = len(resp.get("rows", []))
        inf.add(OK, f"Analytics API v2 responde: {filas} días en la última semana")
    except Exception as e:  # noqa: BLE001
        inf.add(FALLO, f"Analytics API v2 falla: {e}",
                "¿Está habilitada YouTube Analytics API? ¿El OAuth es de la "
                "cuenta propietaria del canal (no admite service account)?")
        return inf

    # ¿Existe `impressions` a nivel de canal? Es la duda de SOPORTE_POR_VERIFICAR.
    try:
        analytics.reports().query(
            ids=ids, startDate=str(desde), endDate=str(hasta),
            metrics="impressions", dimensions="day").execute()
        inf.add(OK, "«impressions» SÍ está disponible a nivel de canal",
                "Mueve \"YouTube\" a SOPORTE_METRICA_SOCIAL['impresiones'], "
                "quítalo de SOPORTE_POR_VERIFICAR y añade \"impressions\" a "
                "youtube._METRICAS_DIA.")
    except Exception as e:  # noqa: BLE001
        inf.add(INFO, "«impressions» no está disponible a nivel de canal",
                f"Confirmado: se queda como nulo. ({str(e)[:80]})")

    return inf


# --------------------------------------------------------------------------- #
# LinkedIn
# --------------------------------------------------------------------------- #

def verificar_linkedin() -> Informe:
    inf = Informe("LinkedIn  ([linkedin])")
    creds = _leer_secreto("linkedin")
    if not creds:
        _falta_seccion(inf, "linkedin",
                       "Necesita una app NUEVA con Community Management API "
                       "como ÚNICO producto, verificada contra la página.")
        return inf

    faltan = [k for k in ("client_id", "client_secret", "refresh_token")
              if not creds.get(k)]
    if faltan:
        inf.add(FALLO, f"Faltan claves: {', '.join(faltan)}")
        return inf
    inf.add(OK, "client_id, client_secret y refresh_token presentes")

    if not (creds.get("organization_id") or config.LINKEDIN_ORGANIZATION_ID):
        inf.add(FALLO, "Falta organization_id",
                "Es el número de linkedin.com/company/XXXXXXX/admin")
        return inf

    try:
        token = linkedin._token(creds)
        inf.add(OK, "El refresh token se canjea correctamente")
    except Exception as e:  # noqa: BLE001
        inf.add(FALLO, f"No se puede canjear el refresh token: {e}",
                "Los refresh token de LinkedIn duran 12 meses; si ha caducado, "
                "rehaz el flujo OAuth.")
        return inf

    org = linkedin._org_urn(creds)
    try:
        datos = linkedin._get(f"organizations/{org.split(':')[-1]}", creds, token)
        inf.add(OK, f"Organización accesible: «{datos.get('localizedName', org)}»")
    except Exception as e:  # noqa: BLE001
        inf.add(FALLO, f"No se puede leer la organización: {e}",
                "Un 403 aquí suele ser que la Community Management API sigue "
                "sin aprobar, o que la app tiene más productos además de ella.")
        return inf

    try:
        linkedin._get("organizationalEntityFollowerStatistics", creds, token,
                      {"q": "organizationalEntity", "organizationalEntity": org})
        inf.add(OK, "Estadísticas de seguidores accesibles")
    except Exception as e:  # noqa: BLE001
        inf.add(FALLO, f"Sin acceso a las estadísticas: {e}",
                "Falta el permiso r_organization_social o "
                "rw_organization_admin en la app aprobada.")

    return inf


# --------------------------------------------------------------------------- #

FUENTES = {"Meta": verificar_meta, "YouTube": verificar_youtube,
           "LinkedIn": verificar_linkedin}


def main() -> int:
    p = argparse.ArgumentParser(
        description="Comprueba las credenciales de social orgánico.")
    p.add_argument("--red", action="append", choices=list(FUENTES),
                   help="limita a una fuente (repetible)")
    args = p.parse_args()

    elegidas = args.red or list(FUENTES)
    informes = [FUENTES[r]() for r in elegidas]
    for inf in informes:
        inf.imprimir()

    listas = [i.red for i in informes if not i.hay_fallos]
    print(f"\n{'═' * 72}")
    print(f"{len(listas)}/{len(informes)} fuentes listas para conectar.")
    if listas:
        print("Listas: " + ", ".join(listas))
        print("Siguiente paso: python scripts/snapshot_social.py --dias 730")
    return 0 if len(listas) == len(informes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
