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
                       "hs_analytics_source_data_2", config.HUBSPOT_PROP_SEGMENTO],
        "limit": 100,
    }
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
            filas.append(dict(
                lead_id=c.get("id"),
                fecha_creacion=_a_fecha(p.get("createdate")),
                fuente=canal,
                campana=campana,  # derivada de hs_analytics_source_data_1/2
                programa=canal,  # dimensión de análisis = canal/fuente
                nivel="",
                estado=estado,
                es_matricula=(estado == "Matriculado"),
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
        "properties": ["dealstage", "amount", "createdate", "dealname"],
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

    # Mapa deal -> programa vía contacto asociado (best-effort).
    deal_ids = [d["id"] for d in deals]
    prog_por_deal = _programa_por_deal(token, deal_ids) if deal_ids else {}

    filas = []
    for d in deals:
        p = d.get("properties", {})
        etapa_id = p.get("dealstage") or ""
        filas.append(dict(
            deal_id=d.get("id"),
            fecha_creacion=_a_fecha(p.get("createdate")),
            etapa_id=etapa_id,
            etapa=config.HUBSPOT_ETAPAS_MAP.get(etapa_id, etapa_id),
            programa=prog_por_deal.get(d.get("id"), "Sin asignar"),
            amount=float(p.get("amount") or 0),
            es_ganado=(etapa_id == config.HUBSPOT_STAGE_MATRICULA),
        ))
    return pd.DataFrame(filas)


def _programa_por_deal(token: str, deal_ids: list[str]) -> dict:
    """Asocia cada deal a un segmento leyendo la propiedad de segmento del contacto."""
    import requests

    # 1) deal -> contacto (associations v4 batch)
    try:
        r = requests.post(
            f"{API}/crm/v4/associations/deal/contact/batch/read",
            headers=_headers(token),
            json={"inputs": [{"id": i} for i in deal_ids]}, timeout=60)
        r.raise_for_status()
        res = r.json().get("results", [])
    except Exception:  # noqa: BLE001
        return {}

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

    # 2) contacto -> canal/fuente (batch read de hs_analytics_source)
    try:
        r = requests.post(
            f"{API}/crm/v3/objects/contacts/batch/read",
            headers=_headers(token),
            json={"properties": ["hs_analytics_source"],
                  "inputs": [{"id": c} for c in contact_ids]}, timeout=60)
        r.raise_for_status()
        fuente_por_contacto = {
            str(c["id"]): (c.get("properties", {}).get("hs_analytics_source") or "")
            for c in r.json().get("results", [])
        }
    except Exception:  # noqa: BLE001
        return {}

    return {
        did: config.fuente_amigable(fuente_por_contacto.get(cid, ""))
        for did, cid in deal_to_contact.items()
    }
