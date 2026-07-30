from datetime import date

import pandas as pd

from src.data import social_demografia as sd


def test_normalizar_deja_el_esquema_fijo():
    d = sd.normalizar(pd.DataFrame([
        {"fecha": "2026-07-30", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": "145"},
    ]))
    assert list(d.columns) == sd.COLUMNAS
    assert d.loc[0, "valor"] == 145.0
    assert d.loc[0, "fecha"] == date(2026, 7, 30)


def test_la_unidad_se_deduce_de_la_red():
    """Instagram cuenta personas; YouTube, porcentaje de visualizaciones."""
    d = sd.normalizar(pd.DataFrame([
        {"fecha": "2026-07-30", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 145},
        {"fecha": "2026-07-30", "red": "YouTube", "dimension": "edad",
         "categoria": "45-54", "valor": 19.4},
    ]))
    u = dict(zip(d["red"], d["unidad"]))
    assert u["Instagram"] == "seguidores"
    assert u["YouTube"] == "pct_visualizaciones"


def test_etiqueta_de_unidad_es_legible():
    assert "seguidores" in sd.etiqueta_unidad("seguidores").lower()
    assert "%" in sd.etiqueta_unidad("pct_visualizaciones")


def test_ultima_foto_devuelve_solo_la_captura_mas_reciente():
    """La demografía es una foto, no una serie: mezclar dos capturas sumaría
    la misma persona dos veces."""
    d = sd.normalizar(pd.DataFrame([
        {"fecha": "2026-07-01", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 100},
        {"fecha": "2026-07-30", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 145},
    ]))
    f = sd.ultima_foto(d, "Instagram", date(2026, 7, 30))
    assert len(f) == 1
    assert f.iloc[0]["valor"] == 145


def test_ultima_foto_respeta_el_limite_de_fecha():
    d = sd.normalizar(pd.DataFrame([
        {"fecha": "2026-07-01", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 100},
        {"fecha": "2026-07-30", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 145},
    ]))
    f = sd.ultima_foto(d, "Instagram", date(2026, 7, 15))
    assert f.iloc[0]["valor"] == 100


def test_facebook_no_tiene_unidad_porque_no_tiene_demografia():
    assert "Facebook" not in sd.UNIDAD_POR_RED


def test_ultima_foto_devuelve_vacio_si_todas_las_fechas_son_invalidas():
    """Si todas las fechas no se parsean, normalizar deja la columna en datetime64
    en lugar de date, causando TypeError en la comparación. ultima_foto debe
    devolver esquema_vacio() con gracia."""
    d = sd.normalizar(pd.DataFrame([
        {"fecha": "INVALIDA", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 100},
        {"fecha": "OTRA_INVALIDA", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 145},
    ]))
    f = sd.ultima_foto(d, "Instagram", date(2026, 7, 30))
    assert len(f) == 0
    assert list(f.columns) == sd.COLUMNAS
