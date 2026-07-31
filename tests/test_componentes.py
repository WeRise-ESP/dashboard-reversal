

def test_una_columna_numerica_toda_nula_no_escribe_None(monkeypatch):
    """Con todos los valores a None pandas deja el dtype en `object`, y
    `NumberColumn` lo renderiza como el texto «None» en vez de dejar la celda
    vacía. Pasó en la pestaña de TikTok, cuya serie diaria solo tiene
    seguidores."""
    import pandas as pd

    from src.ui import components as ui

    capturado = {}
    monkeypatch.setattr(ui.st, "dataframe",
                        lambda d, **k: capturado.update(df=d))

    df = pd.DataFrame({"etiqueta": ["Visualizaciones"], "actual": [None],
                       "delta_pct": [None]})
    ui.tabla_ordenable(df, [
        {"key": "etiqueta", "label": "Métrica"},
        {"key": "actual", "label": "Periodo", "tipo": "numero"},
        {"key": "delta_pct", "label": "Δ %", "tipo": "decimal"},
    ])

    salida = capturado["df"]
    for col in ("actual", "delta_pct"):
        assert pd.api.types.is_numeric_dtype(salida[col]), (
            f"{col} llega como {salida[col].dtype}: se vería «None» en pantalla"
        )
        assert salida[col].isna().all()
