"""
Análisis por red: comparativa contra el periodo anterior y rendimiento de
publicaciones.

Este módulo NO importa streamlit a propósito: así se puede probar con
DataFrames sueltos, sin levantar una app. Todo lo que devuelve son datos; de
pintarlos se encarga `src/ui/social_red.py`.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src import config


def periodo_anterior(desde: date, hasta: date) -> tuple[date, date]:
    """El intervalo de la MISMA longitud inmediatamente anterior a `desde`.

    Para 1–30 de julio devuelve 1–30 de junio. Se usa para dar contexto a los
    KPIs: un número sin el del periodo anterior no dice si va bien o mal.
    """
    dias = (hasta - desde).days
    fin = desde - timedelta(days=1)
    return fin - timedelta(days=dias), fin


def _total(diario: pd.DataFrame, red: str, metrica: str) -> float | None:
    """Suma de una métrica en un periodo, para una red. None si no hay dato.

    `min_count=1` es lo que mantiene la regla: si todas las casillas son nulas
    el resultado es nulo, no 0.
    """
    if diario is None or diario.empty or metrica not in diario.columns:
        return None
    d = diario[diario["red"] == red]
    if d.empty:
        return None
    total = d[metrica].sum(min_count=1)
    return None if pd.isna(total) else float(total)


def comparar_kpis(actual: pd.DataFrame, anterior: pd.DataFrame,
                  red: str) -> pd.DataFrame:
    """Tabla `metrica · etiqueta · actual · anterior · delta_pct` para una red.

    Solo incluye las métricas que ESA red publica: las demás no aparecen, ni a
    cero ni con guion. Para esa red, sencillamente no existen.

    `delta_pct` es nulo cuando no hay periodo anterior o cuando el anterior es
    cero: dividir por cero daría un crecimiento del infinito por ciento, que es
    peor que no decir nada.
    """
    filas = []
    for metrica, etiqueta in config.METRICAS_SOCIAL.items():
        if not config.soporta_metrica(metrica, red):
            continue
        act = _total(actual, red, metrica)
        ant = _total(anterior, red, metrica)
        delta = None
        if act is not None and ant not in (None, 0):
            delta = round((act - ant) / ant * 100, 1)
        filas.append({"metrica": metrica, "etiqueta": etiqueta,
                      "actual": act, "anterior": ant, "delta_pct": delta})
    return pd.DataFrame(filas)
