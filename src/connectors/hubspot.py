"""
Conector de HubSpot (CRM API v3/v4) — portal de Reversal.

Modelo de datos:
- **Leads** = contactos con la propiedad de segmento de Reversal
  (`config.HUBSPOT_PROP_SEGMENTO`), que mapea a un segmento de audiencia. Si la
  atribución de campaña llega OFFLINE (se pierde el gclid/fbclid), la asociación
  lead↔campaña se hace POR SEGMENTO, no por nombre de campaña.
- **Matrícula** = Deal en la etapa "Cierre ganado" del pipeline de Reversal.

Expone:
- obtener(dias)        -> ResultadoConector con el DataFrame de leads (contactos).
- obtener_deals(dias)  -> ResultadoConector con el DataFrame de deals (pipeline).

Orden de resolución en ambos: API real -> caché -> datos de ejemplo.

Credenciales en .streamlit/secrets.toml:
    [hubspot]
    access_token = "pat-..."
    portal_id = "000000000"
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pandas as pd

from src import config
from src.connectors.base import (
    ResultadoConector,
    _leer_secreto,
    guardar_cache,
    leer_cache,
)
from src.data import sample_data

API = "https://api.hubapi.com"

# Mapeo de lifecyclestage de contacto -> etiqueta de estado del lead.
MAPA_LIFECYCLE = {
    "subscriber": "Suscriptor", "lead": "Lead", "marketingqualifiedlead": "MQL",
    "salesqualifiedlead": "SQL", "opportunity": "Oportunidad",
    "customer": "Matriculado", "evangelist": "Prescriptor", "other": "Otro",
}


# --------------------------------------------------------------------------- #
# Leads (contactos con uvic_curso)
# --------------------------------------------------------------------------- #
def obtener(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("hubspot")
    if creds and creds.get("access_token"):
        try:
            df = _fetch_leads(creds, desde, hasta)
            if df is not None:
                guardar_cache(df, "hubspot_leads")
                return ResultadoConector(df, "api", "HubSpot (segmento)")
        except Exception as e:  # noqa: BLE001
            cache = leer_cache("hubspot_leads")
            if cache is not None:
                return ResultadoConector(cache, "cache", f"API falló ({e}); caché")

    cache = leer_cache("hubspot_leads")
    if cache is not None and not cache.empty:
        return ResultadoConector(cache, "cache", "Caché local")
    return ResultadoConector(sample_data.hubspot_leads(desde, hasta), "sample", "Datos de ejemplo")


def obtener_deals(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("hubspot")
    if creds and creds.get("access_token"):
        try:
            df = _fetch_deals(creds, desde, hasta)
            if df is not None:
                guardar_cache(df, "hubspot_deals")
                return ResultadoConector(df, "api", "HubSpot pipeline")
        except Exception as e:  # noqa: BLE001
            cache = leer_cache("hubspot_deals")
            if cache is not None:
                return ResultadoConector(cache, "cache", f"API falló ({e}); caché")

    cache = leer_cache("hubspot_deals")
    if cache is not None and not cache.empty:
        return ResultadoConector(cache, "cache", "Caché local")
    return ResultadoConector(sample_data.hubspot_deals(desde, hasta), "sample", "Datos de ejemplo")


# --------------------------------------------------------------------------- #
# Llamadas a la API
# --------------------------------------------------------------------------- #
def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _ms(d) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def _a_fecha(iso: str):
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc).date()


def _opciones_enum(token: str, propiedad: str) -> dict:
    """{valor_interno: etiqueta} de una propiedad de contacto tipo enumeración.
    Se usa para traducir pais_de_residencia ('1' -> 'España'). Devuelve {} si falla."""
    import requests
    try:
        r = requests.get(f"{API}/crm/v3/properties/contacts/{propiedad}",
                         headers=_headers(token), timeout=30)
        r.raise_for_status()
        return {o["value"]: o["label"] for o in r.json().get("options", [])}
    except Exception:  # noqa: BLE001
        return {}


def _fetch_leads(creds: dict, desde, hasta) -> pd.DataFrame:
    import requests

    token = creds["access_token"]
    # El portal es 100% Reversal: todos los contactos del periodo son leads.
    payload = {
        "filterGroups": [{
            "filters": [
                {"propertyName": "createdate", "operator": "GTE", "value": str(_ms(desde))},
                {"propertyName": "createdate", "operator": "LT",
                 "value": str(_ms(hasta + timedelta(days=1)))},
            ]
        }],
        "properties": ["createdate", "lifecyclestage", "hs_lead_status",
                       "hs_analytics_source", "hs_analytics_source_data_1",
                       "hs_analytics_source_data_2", config.HUBSPOT_PROP_SEGMENTO,
                       "pais_de_residencia", "country"],
        "limit": 100,
    }
    # País FIABLE = auto-declarado. pais_de_residencia es un enum (valor->etiqueta);
    # ip_country se descarta porque en leads de Meta refleja la IP del servidor de
    # Meta (Francia), no la del usuario.
    opciones_pais = _opciones_enum(token, "pais_de_residencia")
    filas, after = [], None
    while True:
        if after:
            payload["after"] = after
        r = requests.post(f"{API}/crm/v3/objects/contacts/search",
                          headers=_headers(token), json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        for c in data.get("results", []):
            p = c.get("properties", {})
            canal = config.fuente_amigable(p.get("hs_analytics_source") or "")
            campana = config.campana_hubspot(
                p.get("hs_analytics_source"),
                p.get("hs_analytics_source_data_1"),
                p.get("hs_analytics_source_data_2"),
            )
            estado = MAPA_LIFECYCLE.get((p.get("lifecyclestage") or "").lower(), "Lead")
            # País auto-declarado: pais_de_residencia (enum) y, si falta, country.
            pdr = (p.get("pais_de_residencia") or "").strip()
            pais_raw = opciones_pais.get(pdr, "") if pdr else (p.get("country") or "")
            filas.append(dict(
                lead_id=c.get("id"),
                fecha_creacion=_a_fecha(p.get("createdate")),
                fuente=canal,
                campana=campana,  # derivada de hs_analytics_source_data_1/2
                programa=canal,  # dimensión de análisis = canal/fuente
                nivel="",
                estado=estado,
                es_matricula=(estado == "Matriculado"),
                pais=config.pais_amigable(pais_raw),
                especialidad=config.especialidad_amigable(
                    p.get(config.HUBSPOT_PROP_SEGMENTO)),
            ))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
    return pd.DataFrame(filas)


def _fetch_deals(creds: dict, desde, hasta) -> pd.DataFrame:
    """Deals del pipeline + segmento (vía contacto asociado y su propiedad de segmento)."""
    import requests

    token = creds["access_token"]
    payload = {
        "filterGroups": [{
            "filters": [
                {"propertyName": "pipeline", "operator": "EQ",
                 "value": config.HUBSPOT_PIPELINE_UVIC},
                {"propertyName": "createdate", "operator": "GTE", "value": str(_ms(desde))},
                {"propertyName": "createdate", "operator": "LT",
                 "value": str(_ms(hasta + timedelta(days=1)))},
            ]
        }],
        "properties": ["dealstage", "amount", "createdate", "dealname",
                       "closed_lost_reason"],
        "limit": 100,
    }
    deals, after = [], None
    while True:
        if after:
            payload["after"] = after
        r = requests.post(f"{API}/crm/v3/objects/deals/search",
                          headers=_headers(token), json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        deals.extend(data.get("results", []))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break

    # Cada deal toma CANAL y CAMPAÑA de su contacto asociado (la matrícula se
    # atribuye a la fuente/campaña del contacto que cerró, no del lifecyclestage).
    deal_ids = [d["id"] for d in deals]
    atrib = _atrib_por_deal(token, deal_ids) if deal_ids else {}

    filas = []
    for d in deals:
        p = d.get("properties", {})
        etapa_id = p.get("dealstage") or ""
        canal, campana = atrib.get(d.get("id"), ("Sin asignar", "Sin campaña"))
        motivo = (p.get("closed_lost_reason") or "").strip()
        filas.append(dict(
            deal_id=d.get("id"),
            fecha_creacion=_a_fecha(p.get("createdate")),
            etapa_id=etapa_id,
            etapa=config.HUBSPOT_ETAPAS_MAP.get(etapa_id, etapa_id),
            programa=canal,
            campana=campana,
            amount=float(p.get("amount") or 0),
            es_ganado=(etapa_id == config.HUBSPOT_STAGE_MATRICULA),
            es_perdido=(etapa_id == "closedlost"),
            motivo_perdido=motivo or "Sin motivo indicado",
        ))
    return pd.DataFrame(filas)


def _lotes(seq: list, n: int = 100):
    """Trocea una lista en lotes de tamaño n (la API de HubSpot limita batch a 100)."""
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _atrib_por_deal(token: str, deal_ids: list[str]) -> dict:
    """Devuelve {deal_id: (canal, campana)} leyendo la fuente del contacto asociado
    a cada deal (hs_analytics_source + source_data_1/2).

    HubSpot limita los batch a 100 inputs, así que troceamos deal_ids y contact_ids
    en lotes de 100 (con >100 deals antes se recibía un 400 y se perdía TODO)."""
    import requests

    # 1) deal -> contacto (associations v4 batch, en lotes de 100)
    res = []
    for lote in _lotes(deal_ids):
        try:
            r = requests.post(
                f"{API}/crm/v4/associations/deal/contact/batch/read",
                headers=_headers(token),
                json={"inputs": [{"id": i} for i in lote]}, timeout=60)
            r.raise_for_status()
            res.extend(r.json().get("results", []))
        except Exception:  # noqa: BLE001
            continue

    deal_to_contact, contact_ids = {}, set()
    for item in res:
        frm = str(item.get("from", {}).get("id"))
        tos = item.get("to", [])
        if tos:
            cid = str(tos[0].get("toObjectId"))
            deal_to_contact[frm] = cid
            contact_ids.add(cid)
    if not contact_ids:
        return {}

    # 2) contacto -> fuente + desglose (batch read, en lotes de 100)
    props_por_contacto = {}
    for lote in _lotes(list(contact_ids)):
        try:
            r = requests.post(
                f"{API}/crm/v3/objects/contacts/batch/read",
                headers=_headers(token),
                json={"properties": ["hs_analytics_source", "hs_analytics_source_data_1",
                                     "hs_analytics_source_data_2"],
                      "inputs": [{"id": c} for c in lote]}, timeout=60)
            r.raise_for_status()
            for c in r.json().get("results", []):
                props_por_contacto[str(c["id"])] = c.get("properties", {})
        except Exception:  # noqa: BLE001
            continue

    out = {}
    for did, cid in deal_to_contact.items():
        p = props_por_contacto.get(cid, {})
        src = p.get("hs_analytics_source") or ""
        out[did] = (
            config.fuente_amigable(src),
            config.campana_hubspot(src, p.get("hs_analytics_source_data_1"),
                                   p.get("hs_analytics_source_data_2")),
        )
    return out
