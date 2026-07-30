from datetime import date

import pandas as pd

from src.data import social, social_analisis as sa


def test_periodo_anterior_es_igual_de_largo_y_contiguo():
    d, h = sa.periodo_anterior(date(2026, 7, 1), date(2026, 7, 30))
    assert (d, h) == (date(2026, 6, 1), date(2026, 6, 30))


def test_periodo_anterior_de_un_solo_dia():
    d, h = sa.periodo_anterior(date(2026, 7, 15), date(2026, 7, 15))
    assert (d, h) == (date(2026, 7, 14), date(2026, 7, 14))


def _diario(red, fecha, **metricas):
    return social.normalizar_diario(pd.DataFrame([{"fecha": fecha, "red": red, **metricas}]))


def test_compara_y_calcula_la_variacion():
    act = _diario("Instagram", date(2026, 7, 1), visualizaciones=120)
    ant = _diario("Instagram", date(2026, 6, 1), visualizaciones=100)
    r = sa.comparar_kpis(act, ant, "Instagram").set_index("metrica")
    assert r.loc["visualizaciones", "actual"] == 120
    assert r.loc["visualizaciones", "anterior"] == 100
    assert r.loc["visualizaciones", "delta_pct"] == 20.0


def test_sin_periodo_anterior_la_variacion_es_nula_no_cero():
    """Un cero produciría un crecimiento del infinito por ciento."""
    act = _diario("Instagram", date(2026, 7, 1), visualizaciones=120)
    r = sa.comparar_kpis(act, social.esquema_diario_vacio(), "Instagram").set_index("metrica")
    assert pd.isna(r.loc["visualizaciones", "anterior"])
    assert pd.isna(r.loc["visualizaciones", "delta_pct"])


def test_omite_las_metricas_que_la_red_no_publica():
    """Facebook no tiene alcance: no debe aparecer en su tabla, ni a cero ni
    con guion. Para esa red esa métrica no existe."""
    act = _diario("Facebook", date(2026, 7, 1), visualizaciones=10)
    r = sa.comparar_kpis(act, social.esquema_diario_vacio(), "Facebook")
    assert "alcance" not in set(r["metrica"])
    assert "visualizaciones" in set(r["metrica"])


def test_solo_mira_la_red_pedida():
    act = pd.concat([
        _diario("Instagram", date(2026, 7, 1), visualizaciones=120),
        _diario("YouTube", date(2026, 7, 1), visualizaciones=999),
    ], ignore_index=True)
    r = sa.comparar_kpis(act, social.esquema_diario_vacio(), "Instagram").set_index("metrica")
    assert r.loc["visualizaciones", "actual"] == 120
