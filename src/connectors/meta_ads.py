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
            filas.append(dict(
                fecha=pd.to_datetime(row["date_start"]).date(),
                plataforma="Meta Ads",
                campana=nombre,
                impresiones=int(row.get("impressions", 0)),
                clics=int(row.get("clicks", 0)),
                coste=round(float(row.get("spend", 0)), 2),
                conversiones=leads,
            ))
        url = data.get("paging", {}).get("next")
        params = None  # la URL 'next' ya trae los parámetros
    return pd.DataFrame(filas)


def _date_preset(dias: int) -> str:
    if dias <= 7:
        return "last_7d"
    if dias <= 14:
        return "last_14d"
    if dias <= 30:
        return "last_30d"
    return "last_90d"
