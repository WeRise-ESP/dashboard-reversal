"""
Dibuja UNA pestaña de red de la página de Social Orgánico.

Las cuatro redes comparten los mismos bloques y en el mismo orden, para que se
puedan comparar de memoria; lo que cambia es el contenido, porque cada API
ofrece cosas distintas. Donde una red no da algo, el bloque lo DICE en vez de
desaparecer o salir vacío: esa asimetría es información.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import config
from src.ui import components as ui
from src.ui.theme import num_o_guion


def metricas_de_la_red(red: str) -> dict[str, str]:
    """{metrica: etiqueta} de lo que ESA red publica.

    Filtra el selector para no ofrecer métricas que siempre saldrían vacías:
    Facebook no tiene alcance ni impresiones desde que Meta las retiró.
    """
    return {m: e for m, e in config.METRICAS_SOCIAL.items()
            if config.soporta_metrica(m, red)}


def _pct(x: float) -> str:
    """Porcentaje con coma decimal, punto de miles y signo explícito.

    El intercambio se hace en tres pasos con un carácter puente para que el
    punto acabe de separador de miles y la coma de decimal (convención
    española), sin que un paso pise al otro. A partir de ±1000% hacen falta
    los dos separadores: sin punto de miles, "+2.400,0%" saldría "+2,400,0%",
    con dos comas e ilegible.
    """
    txt = f"{x:,.1f}".replace(",", "·").replace(".", ",").replace("·", ".")
    return f"{'+' if x > 0 else ''}{txt}%"


def frases_titular(kpis: pd.DataFrame, red: str) -> list[str]:
    """Frases del titular, construidas con datos y plantillas.

    Nunca texto libre: si falta el dato de una frase, esa frase no aparece. Un
    titular que rellena huecos con vaguedades es peor que no tener titular.
    """
    if kpis is None or kpis.empty:
        return []

    frases = []
    principal = kpis[kpis["metrica"] == "visualizaciones"]
    if not principal.empty and pd.notna(principal.iloc[0]["actual"]):
        fila = principal.iloc[0]
        txt = f"{fila['etiqueta']}: {num_o_guion(fila['actual'])}"
        if pd.notna(fila["delta_pct"]):
            txt += f" ({_pct(float(fila['delta_pct']))} vs. periodo anterior)"
        frases.append(txt + ".")

    seguidores = kpis[kpis["metrica"] == "seguidores_nuevos"]
    if not seguidores.empty and pd.notna(seguidores.iloc[0]["actual"]):
        fila = seguidores.iloc[0]
        txt = f"{num_o_guion(fila['actual'])} seguidores nuevos"
        if pd.notna(fila["delta_pct"]):
            txt += f" ({_pct(float(fila['delta_pct']))})"
        frases.append(txt + ".")

    caidas = kpis[kpis["delta_pct"].notna() & (kpis["delta_pct"] < -20)]
    if not caidas.empty:
        peor = caidas.sort_values("delta_pct").iloc[0]
        frases.append(f"Atención: {peor['etiqueta'].lower()} cae "
                      f"{_pct(float(peor['delta_pct']))}.")
    return frases


def bloque_titular(kpis: pd.DataFrame, red: str) -> None:
    frases = frases_titular(kpis, red)
    if frases:
        ui.resumen_ejecutivo(" ".join(frases))


def bloque_kpis(kpis: pd.DataFrame) -> None:
    """Tabla `Métrica · Periodo · Anterior · Δ`.

    Usa `num_o_guion`, nunca `num()`: un nulo aquí significa «no hay dato del
    periodo anterior», y pintarlo como 0 diría que cayó a cero.
    """
    if kpis is None or kpis.empty:
        st.info("Sin métricas para esta red en el periodo.")
        return

    filas = [{
        "metrica": k["etiqueta"],
        "actual": num_o_guion(k["actual"]),
        "anterior": num_o_guion(k["anterior"]),
        "delta": "—" if pd.isna(k["delta_pct"]) else _pct(float(k["delta_pct"])),
    } for _, k in kpis.iterrows()]

    ui.tabla(pd.DataFrame(filas), [
        {"key": "metrica", "label": "Métrica", "align": "l"},
        {"key": "actual", "label": "Periodo", "align": "r"},
        {"key": "anterior", "label": "Anterior", "align": "r"},
        {"key": "delta", "label": "Δ", "align": "r"},
    ])

    if kpis["anterior"].isna().all():
        st.caption("No hay histórico del periodo anterior para comparar. "
                   "Se irá llenando conforme el job diario acumule días.")


def bloque_evolucion(diario: pd.DataFrame, red: str, key: str) -> None:
    from src.data import social

    metricas = metricas_de_la_red(red)
    if not metricas:
        st.info("Esta red no publica métricas diarias.")
        return

    etiquetas = {e: m for m, e in metricas.items()}
    elegida = st.selectbox("Métrica", list(etiquetas), key=key)
    serie = social.serie_diaria(diario[diario["red"] == red], etiquetas[elegida])
    if serie.empty:
        st.info(f"Sin datos de «{elegida}» en el periodo.")
        return
    ui.linea_temporal(serie, x="fecha", y="valor", color="red",
                      titulo=f"{elegida} por día", y_label=elegida,
                      simbolos=config.SIMBOLO_RED_SOCIAL)
