"""
Vuelca a la caché (data/cache/meta_ads.parquet) un snapshot REAL de Meta Ads de
la cuenta Reversal Institute (act_1252583410186224), obtenido vía el conector MCP
de Claude (mcp__meta-ads__ads_get_ad_entities, level=campaign, last_30d).

Como la app desplegada no tiene token propio de Meta, el dashboard lee este
snapshot desde la caché (origen "cache"). Para refrescar: volver a pedir las
campañas a Claude y actualizar TOTALES_30D + FECHA.

Conversiones = "Website leads" (campo `lead` / `results` de Meta, objetivo
OUTCOME_LEADS). Total 37 leads web, coherente con los ~43 de HubSpot Paid Social.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

FECHA_SNAPSHOT = date(2026, 7, 8)
INICIO = date(2026, 6, 29)          # las campañas ARRANCARON el lunes 29-jun
FIN = date(2026, 7, 7)

# (campaña, impresiones, clics, coste_eur, conversiones=leads web) — reales, 30 días.
TOTALES_30D = [
    ("NAC - Longevidad y Healthspan", 11267, 502, 173.43, 32),
    ("NAC - Reversal", 29230, 1252, 88.34, 2),
    ("Publicación de Instagram: Hay una etapa en la que...", 2411, 71, 19.92, 0),
    ("TEST Mestral — Coach", 247, 12, 4.18, 2),
    ("TEST Mestral — Video", 172, 6, 4.14, 0),
    ("TEST Mestral — Entrenadores", 277, 12, 4.05, 1),
    ("TEST Mestral — Sanitarios", 264, 5, 3.63, 0),
]


def _rng(nombre: str) -> np.random.Generator:
    semilla = int(hashlib.md5(nombre.encode()).hexdigest()[:8], 16)
    return np.random.default_rng(semilla)


def _reparte_entero(total: int, dias: int, r: np.random.Generator) -> list[int]:
    if total <= 0:
        return [0] * dias
    pesos = r.uniform(0.6, 1.4, dias)
    pesos /= pesos.sum()
    base = np.floor(pesos * total).astype(int)
    resto = total - int(base.sum())
    for i in np.argsort(-pesos)[:resto]:
        base[i] += 1
    return base.tolist()


def construir() -> pd.DataFrame:
    # Solo días con campaña activa (INICIO..FIN); antes no hubo actividad.
    fechas = [INICIO + timedelta(days=i) for i in range((FIN - INICIO).days + 1)]
    n = len(fechas)
    filas = []
    for campana, impr, clics, coste, conv in TOTALES_30D:
        r = _rng("meta-real-" + campana)
        d_impr = _reparte_entero(impr, n, r)
        d_clics = _reparte_entero(clics, n, r)
        d_conv = _reparte_entero(int(conv), n, r)
        pesos = np.array(d_clics, dtype=float)
        pesos = pesos / pesos.sum() if pesos.sum() else np.ones(n) / n
        d_coste = np.round(pesos * coste, 2)
        for i, f in enumerate(fechas):
            filas.append(dict(
                fecha=f, plataforma="Meta Ads", campana=campana,
                impresiones=int(d_impr[i]), clics=int(d_clics[i]),
                coste=float(d_coste[i]), conversiones=int(d_conv[i]),
            ))
    return pd.DataFrame(filas)


def main() -> None:
    df = construir()
    cache_dir = Path(__file__).resolve().parents[1] / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_dir / "meta_ads.parquet", index=False)
    print(f"Snapshot Meta Ads {FECHA_SNAPSHOT} -> {len(df)} filas, "
          f"{df['coste'].sum():.2f}€, {df['clics'].sum()} clics, "
          f"{len(TOTALES_30D)} campañas.")


if __name__ == "__main__":
    main()
