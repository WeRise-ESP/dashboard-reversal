"""
Conector de Meta Ads (Marketing API).

Orden: API real -> caché -> datos de ejemplo.

Credenciales esperadas en .streamlit/secrets.toml:
    [meta_ads]
    access_token = "..."
    ad_account_id = "act_33542477"
    api_version = "v21.0"
"""
from __future__ import annotations

import json

import pandas as pd

from src import config
from src.connectors.base import (
    ResultadoConector,
    _leer_secreto,
    guardar_cache,
    leer_cache,
)
from src.data import sample_data


def obtener(desde, hasta) -> ResultadoConector:
    creds = _leer_secreto("meta_ads")
    if creds:
        try:
            df = _consultar_api(creds, desde, hasta)
            if df is not None and not df.empty:
                guardar_cache(df, "meta_ads")
                return ResultadoConector(df, "api", "Meta Marketing API")
        except Exception as e:  # noqa: BLE001
            cache = leer_cache("meta_ads")
            if cache is not None:
                return ResultadoConector(cache, "cache", f"API falló ({e}); uso caché")

    cache = leer_cache("meta_ads")
    if cache is not None and not cache.empty:
        return ResultadoConector(cache, "cache", "Caché local")

    return ResultadoConector(
        sample_data.meta_ads_diario(desde, hasta), "sample", "Datos de ejemplo"
    )


def _consultar_api(creds: dict, desde, hasta) -> pd.DataFrame:
    """Insights diarios por campaña vía Graph API (con requests, sin SDK)."""
    import requests

    version = creds.get("api_version", "v21.0")
    account = creds.get("ad_account_id", config.META_AD_ACCOUNT_ID)
    token = creds["access_token"]

    # 1) Catálogo de TODAS las campañas de la cuenta (activas y pausadas), aunque
    #    no hayan tenido entrega en el periodo.
    estados = _estados_campanas(version, account, token)

    url = f"https://graph.facebook.com/{version}/{account}/insights"
    params = {
        "level": "campaign",
        "fields": "campaign_name,impressions,clicks,spend,actions",
        "time_increment": 1,
        "time_range": json.dumps({"since": str(desde), "until": str(hasta)}),
        "access_token": token,
        "limit": 500,
    }
    filas = []
    con_datos = set()
    while url:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        for row in data.get("data", []):
            nombre = row.get("campaign_name", "")
            # La cuenta es exclusiva de Reversal -> incluimos todas las campañas.
            # Un mismo lead aparece bajo varios action_type (lead, pixel_lead…);
            # tomamos UNO por prioridad para no duplicar (= "resultados" de Meta).
            acciones = {a.get("action_type"): int(float(a.get("value", 0)))
                        for a in row.get("actions", [])}
            leads = 0
            for tipo in ("offsite_conversion.fb_pixel_lead", "lead",
                         "onsite_conversion.lead_grouped"):
                if tipo in acciones:
                    leads = acciones[tipo]
                    break
            con_datos.add(nombre)
            filas.append(dict(
                fecha=pd.to_datetime(row["date_start"]).date(),
                plataforma="Meta Ads",
                campana=nombre,
                estado=estados.get(nombre, "—"),
                impresiones=int(row.get("impressions", 0)),
                clics=int(row.get("clicks", 0)),
                coste=round(float(row.get("spend", 0)), 2),
                conversiones=leads,
            ))
        url = data.get("paging", {}).get("next")
        params = None  # la URL 'next' ya trae los parámetros

    # Campañas SIN entrega en el periodo -> fila a 0 para que se listen igual.
    filas.extend([dict(
        fecha=desde, plataforma="Meta Ads", campana=nombre, estado=estado,
        impresiones=0, clics=0, coste=0.0, conversiones=0,
    ) for nombre, estado in estados.items() if nombre not in con_datos])
    return pd.DataFrame(filas)


def _estados_campanas(version: str, account: str, token: str) -> dict:
    """{nombre_campaña: estado legible} de TODAS las campañas de la cuenta.

    Usa `effective_status` (estado real de entrega) y cae a `status` si falta.
    Devuelve {} si la llamada falla (el dashboard sigue con las que tengan datos)."""
    import requests
    out, url = {}, f"https://graph.facebook.com/{version}/{account}/campaigns"
    params = {"fields": "name,status,effective_status", "limit": 500,
              "access_token": token}
    try:
        while url:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            for c in data.get("data", []):
                crudo = c.get("effective_status") or c.get("status") or ""
                out[c.get("name", "")] = config.estado_campana(crudo)
            url = data.get("paging", {}).get("next")
            params = None
    except Exception:  # noqa: BLE001
        return out
    return out


def _date_preset(dias: int) -> str:
    if dias <= 7:
        return "last_7d"
    if dias <= 14:
        return "last_14d"
    if dias <= 30:
        return "last_30d"
    return "last_90d"
