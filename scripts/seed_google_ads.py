"""
Vuelca a la caché (data/cache/google_ads.parquet) un snapshot REAL de Google Ads
de la cuenta Reversal Institute (2692996145), obtenido vía el conector MCP de
Claude (mcp__google-ads__rendimiento_campanas, 30 días).

Como la app desplegada no tiene las credenciales OAuth propias del SDK, el
dashboard lee este snapshot desde la caché (origen "cache"). Para refrescarlo:
volver a pedir `rendimiento_campanas` a Claude y actualizar TOTALES_30D + FECHA.

Los totales de 30 días se reparten uniformemente por día (con variación
determinista) para poder dibujar las series diarias.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

FECHA_SNAPSHOT = date(2026, 7, 8)   # día en que se pidió a la API
INICIO = date(2026, 6, 29)          # las campañas ARRANCARON el lunes 29-jun
FIN = date(2026, 7, 7)              # último día del rango (alinea con el resto)

# (campaña, impresiones, clics, coste_eur, conversiones) — reales, 30 días.
TOTALES_30D = [
    ("NAC_Certificado_Longevidad-Healthspan_Search", 511, 30, 155.38, 2),
    ("NAC_Marca-Trafico-Search", 837, 53, 84.60, 2),
    ("DemandGen_Prospecting_Certificacion-Longevidad_2026", 2544, 42, 3.12, 0),
    # "eeafas" (PAUSED, todo a 0) se omite.
]


def _rng(nombre: str) -> np.random.Generator:
    semilla = int(hashlib.md5(nombre.encode()).hexdigest()[:8], 16)
    return np.random.default_rng(semilla)


def _reparte_entero(total: int, dias: int, r: np.random.Generator) -> list[int]:
    """Reparte un entero en `dias` cubos de forma determinista sumando exacto."""
    if total <= 0:
        return [0] * dias
    pesos = r.uniform(0.6, 1.4, dias)
    pesos /= pesos.sum()
    base = np.floor(pesos * total).astype(int)
    resto = total - int(base.sum())
    # reparte el resto en los días de mayor peso
    for i in np.argsort(-pesos)[:resto]:
        base[i] += 1
    return base.tolist()


def construir() -> pd.DataFrame:
    # Solo días con campaña activa (INICIO..FIN); antes no hubo actividad.
    fechas = [INICIO + timedelta(days=i) for i in range((FIN - INICIO).days + 1)]
    n = len(fechas)
    filas = []
    for campana, impr, clics, coste, conv in TOTALES_30D:
        r = _rng("gads-real-" + campana)
        d_impr = _reparte_entero(impr, n, r)
        d_clics = _reparte_entero(clics, n, r)
        d_conv = _reparte_entero(int(conv), n, r)
        pesos = np.array(d_clics, dtype=float)
        pesos = pesos / pesos.sum() if pesos.sum() else np.ones(n) / n
        d_coste = np.round(pesos * coste, 2)
        for i, f in enumerate(fechas):
            filas.append(dict(
                fecha=f, plataforma="Google Ads", campana=campana,
                impresiones=int(d_impr[i]), clics=int(d_clics[i]),
                coste=float(d_coste[i]), conversiones=int(d_conv[i]),
            ))
    return pd.DataFrame(filas)


def main() -> None:
    df = construir()
    cache_dir = Path(__file__).resolve().parents[1] / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_dir / "google_ads.parquet", index=False)
    print(f"Snapshot Google Ads {FECHA_SNAPSHOT} -> {len(df)} filas, "
          f"{df['coste'].sum():.2f}€, {df['clics'].sum()} clics, "
          f"{df['conversiones'].sum()} conv, {len(TOTALES_30D)} campañas.")


if __name__ == "__main__":
    main()
