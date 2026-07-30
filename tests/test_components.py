import math

import pandas as pd

from src.ui import components as ui


def _capturar_markdown(monkeypatch):
    """Sustituye `st.markdown` para capturar el HTML que genera `ui.tabla`."""
    capturado = {}

    def _fake_markdown(html, *a, **k):
        capturado["html"] = html

    monkeypatch.setattr(ui.st, "markdown", _fake_markdown)
    return capturado


def test_tabla_no_revienta_con_pd_na(monkeypatch):
    """`pd.NA` llega desde columnas `Int64` (nulable) y `bool(pd.NA)` revienta
    con TypeError si se evalúa directamente en un `or`. Reproducido en Social
    Orgánico con el preset «Mes pasado». `_es_nulo` (de `theme.py`) ya resuelve
    esto bien; `ui.tabla` tiene que usarlo en vez de su propio `v is None`."""
    capturado = _capturar_markdown(monkeypatch)
    df = pd.DataFrame({
        "metrica": ["a", "b", "c"],
        "valor": pd.array([1, pd.NA, 3], dtype="Int64"),
    })
    # No debe lanzar TypeError: boolean value of NA is ambiguous.
    ui.tabla(df, [
        {"key": "metrica", "label": "Métrica", "align": "l"},
        {"key": "valor", "label": "Valor", "align": "r"},
    ])
    assert "<NA>" not in capturado["html"]


def test_tabla_trata_igual_na_none_nan_y_cadena_vacia(monkeypatch):
    """Las cuatro formas de "sin dato" deben producir la misma celda vacía."""
    capturado = _capturar_markdown(monkeypatch)
    df = pd.DataFrame({
        "metrica": ["a", "b", "c", "d"],
        "valor": [pd.NA, None, math.nan, ""],
    })
    ui.tabla(df, [
        {"key": "metrica", "label": "Métrica", "align": "l"},
        {"key": "valor", "label": "Valor", "align": "r"},
    ])
    html = capturado["html"]
    # Las cuatro celdas de "valor" deben salir vacías: ni "<NA>", ni "None",
    # ni "nan" como texto literal.
    for feo in ("<NA>", "None", "nan"):
        assert feo not in html
