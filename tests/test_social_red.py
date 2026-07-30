import pandas as pd

from src import config
from src.ui import social_red as sr


def _kpis(filas):
    return pd.DataFrame(filas)


def test_el_selector_de_metricas_solo_ofrece_lo_que_la_red_publica():
    """Ofrecer una métrica que siempre saldrá vacía es prometer algo que no se
    va a cumplir. Facebook no tiene alcance ni impresiones."""
    fb = sr.metricas_de_la_red("Facebook")
    assert "alcance" not in fb
    assert "impresiones" not in fb
    assert "visualizaciones" in fb

    ig = sr.metricas_de_la_red("Instagram")
    assert "alcance" in ig
    assert "impresiones" not in ig


def test_el_titular_nombra_la_metrica_y_su_variacion():
    frases = sr.frases_titular(_kpis([
        {"metrica": "visualizaciones", "etiqueta": "Visualizaciones",
         "actual": 151551.0, "anterior": 135200.0, "delta_pct": 12.1},
    ]), "Instagram")
    texto = " ".join(frases)
    assert "Visualizaciones" in texto
    assert "12,1" in texto or "12.1" in texto


def test_el_titular_omite_las_frases_sin_dato():
    """Si falta el dato, la frase no aparece; no se rellena con texto vago."""
    frases = sr.frases_titular(_kpis([
        {"metrica": "visualizaciones", "etiqueta": "Visualizaciones",
         "actual": None, "anterior": None, "delta_pct": None},
    ]), "Instagram")
    assert frases == []


def test_el_titular_no_inventa_variacion_sin_periodo_anterior():
    frases = sr.frases_titular(_kpis([
        {"metrica": "visualizaciones", "etiqueta": "Visualizaciones",
         "actual": 100.0, "anterior": None, "delta_pct": None},
    ]), "Instagram")
    texto = " ".join(frases)
    assert "Visualizaciones" in texto
    assert "%" not in texto
