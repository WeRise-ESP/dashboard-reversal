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


def test_pct_no_confunde_miles_con_decimales():
    """A partir de +1000% el separador de miles y el decimal son distintos
    caracteres (punto y coma); si no, `2.400,0%` sale como `2,400,0%`, con dos
    comas, y es ilegible. Una variación de cuatro cifras es normal cuando el
    «anterior» es pequeño (mensajes, seguidores nuevos de una cuenta joven)."""
    assert sr._pct(2400.0) == "+2.400,0%"
    assert sr._pct(-1234.5) == "-1.234,5%"
    assert sr._pct(12.1) == "+12,1%"


from datetime import date

from src.data import social, social_demografia as sd


def test_el_texto_de_las_publicaciones_va_escapado():
    """`ui.tabla` inyecta HTML sin escapar y los títulos vienen de una API."""
    p = social.normalizar_posts(pd.DataFrame([{
        "red": "Instagram", "post_id": "1", "tipo": "Reel",
        "titulo": "<script>alert(1)</script>", "url": "https://x.test",
        "visualizaciones": 10, "likes": 1}]))
    filas = sr.filas_publicaciones(p, "Instagram")
    assert "<script>" not in filas.iloc[0]["titulo"]
    assert "&lt;script&gt;" in filas.iloc[0]["titulo"]


def test_el_tipo_va_escapado():
    """`tipo` llega sin pasar por un mapa cerrado cuando viene de
    `data/import_social/*.csv` (un nivel documentado de la cascada) y `ui.tabla`
    inyecta HTML sin escapar: un `tipo` hostil no debe ejecutarse."""
    p = social.normalizar_posts(pd.DataFrame([{
        "red": "Instagram", "post_id": "1",
        "tipo": '<img src=x onerror="alert(1)">',
        "titulo": "hola", "url": "https://x.test",
        "visualizaciones": 10, "likes": 1}]))
    filas = sr.filas_publicaciones(p, "Instagram")
    assert "<img" not in filas.iloc[0]["tipo"]
    assert "&lt;img" in filas.iloc[0]["tipo"]


def test_la_url_no_http_no_se_convierte_en_enlace():
    p = social.normalizar_posts(pd.DataFrame([{
        "red": "Instagram", "post_id": "1", "tipo": "Reel",
        "titulo": "hola", "url": "javascript:alert(1)",
        "visualizaciones": 10, "likes": 1}]))
    filas = sr.filas_publicaciones(p, "Instagram")
    assert "javascript:" not in filas.iloc[0]["titulo"]


def test_el_aviso_de_criterio_dice_como_se_ordena_facebook():
    assert "interacciones" in sr.nota_criterio("Facebook").lower()
    assert "engagement" in sr.nota_criterio("Instagram").lower()


def test_la_audiencia_declara_su_unidad():
    """Instagram cuenta personas; YouTube, % de visualizaciones."""
    assert "sigue" in sr.nota_unidad("Instagram").lower()
    assert "%" in sr.nota_unidad("YouTube")
    assert sr.nota_unidad("Facebook") == ""
