"""
Conector de Google Ads.

Estrategia de datos (en orden):
  1. API real (google-ads SDK) si hay credenciales en st.secrets["google_ads"].
  2. Caché local (data/cache/google_ads.parquet), que Claude puede rellenar vía MCP.
  3. Datos de ejemplo (sample_data) para que el dashboard sea navegable siempre.

Credenciales esperadas en .streamlit/secrets.toml:
    [google_ads]
    developer_token = "..."
    client_id = "..."
    client_secret = "..."
    refresh_token = "..."
    login_customer_id = "3963262878"
    customer_id = "2970533333"
"""
from __future__ import annotations

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
    creds = _leer_secreto("google_ads")
    if creds:
        try:
            df = _consultar_api(creds, desde, hasta)
            if df is not None and not df.empty:
                guardar_cache(df, "google_ads")
                return ResultadoConector(df, "api", "Google Ads API")
        except Exception as e:  # noqa: BLE001
            # Caemos a caché/sample pero informamos del error.
            cache = leer_cache("google_ads")
            if cache is not None:
                return ResultadoConector(cache, "cache", f"API falló ({e}); uso caché")

    cache = leer_cache("google_ads")
    if cache is not None and not cache.empty:
        return ResultadoConector(cache, "cache", "Caché local")

    return ResultadoConector(
        sample_data.google_ads_diario(desde, hasta), "sample", "Datos de ejemplo"
    )


def _consultar_api(creds: dict, desde, hasta) -> pd.DataFrame:
    """Consulta real vía google-ads SDK. Se importa dentro de la función para
    no exigir la dependencia si el usuario aún no usa la API."""
    from google.ads.googleads.client import GoogleAdsClient  # type: ignore

    client = GoogleAdsClient.load_from_dict({
        "developer_token": creds["developer_token"],
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "login_customer_id": creds.get("login_customer_id", config.GOOGLE_ADS_LOGIN_CUSTOMER_ID),
        "use_proto_plus": True,
    })
    customer_id = creds.get("customer_id", config.GOOGLE_ADS_CUSTOMER_ID)
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            segments.date,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM campaign
        WHERE segments.date BETWEEN '{desde}' AND '{hasta}'
    """
    filas = []
    for batch in ga_service.search_stream(customer_id=customer_id, query=query):
        for row in batch.results:
            nombre = row.campaign.name
            # La cuenta es exclusiva de Reversal -> incluimos todas las campañas.
            filas.append(dict(
                fecha=pd.to_datetime(row.segments.date).date(),
                plataforma="Google Ads",
                campana=nombre,
                impresiones=int(row.metrics.impressions),
                clics=int(row.metrics.clicks),
                coste=round(row.metrics.cost_micros / 1_000_000, 2),
                conversiones=int(row.metrics.conversions),
            ))
    return pd.DataFrame(filas)
