from datetime import date

from src.connectors import youtube as yt
from src.data import social_demografia as sd


class _Reports:
    def __init__(self, respuestas):
        self._r = respuestas

    def query(self, **kw):
        clave = kw["dimensions"]
        datos = self._r[clave]

        class _Ej:
            def execute(self_inner):
                return datos
        return _Ej()


class _Analytics:
    def __init__(self, respuestas):
        self._r = respuestas

    def reports(self):
        return _Reports(self._r)


def test_traduce_edad_genero_y_pais(monkeypatch):
    respuestas = {
        "ageGroup,gender": {"rows": [["age45-54", "female", 19.4],
                                     ["age25-34", "male", 5.2]]},
        "country": {"rows": [["ES", 280], ["AR", 137]]},
    }
    monkeypatch.setattr(yt, "_servicios", lambda c: (_Analytics(respuestas), None))
    monkeypatch.setattr(yt, "_canal", lambda c: "UC123")

    d = sd.normalizar(yt._api_demografia({}, date(2026, 7, 1), date(2026, 7, 30)))

    assert {"edad", "genero", "pais"} <= set(d["dimension"])
    edad = d[(d["dimension"] == "edad") & (d["categoria"] == "45-54")]
    assert round(float(edad.iloc[0]["valor"]), 1) == 19.4


def test_la_unidad_de_youtube_no_es_seguidores():
    """Su demografía es % de visualizaciones, no gente que te sigue."""
    assert sd.UNIDAD_POR_RED["YouTube"] == "pct_visualizaciones"


def test_quita_el_prefijo_age_de_los_tramos(monkeypatch):
    """La API devuelve 'age45-54'; el esquema guarda '45-54' para que coincida
    con los tramos de Instagram y se puedan poner en el mismo eje."""
    respuestas = {"ageGroup,gender": {"rows": [["age45-54", "female", 1.0]]},
                  "country": {"rows": []}}
    monkeypatch.setattr(yt, "_servicios", lambda c: (_Analytics(respuestas), None))
    monkeypatch.setattr(yt, "_canal", lambda c: "UC123")
    d = sd.normalizar(yt._api_demografia({}, date(2026, 7, 1), date(2026, 7, 30)))
    assert "45-54" in set(d["categoria"])
    assert not any(str(c).startswith("age") for c in d["categoria"])


def test_normaliza_el_tramo_abierto_65_a_65_mas(monkeypatch):
    """La API devuelve 'age65-' (guion final, sin '+') para el tramo abierto.
    Quitar solo el prefijo dejaría '65-', que NO coincide con el '65+' de
    Instagram: hay que normalizarlo explícitamente."""
    respuestas = {"ageGroup,gender": {"rows": [["age65-", "female", 30.4]]},
                  "country": {"rows": []}}
    monkeypatch.setattr(yt, "_servicios", lambda c: (_Analytics(respuestas), None))
    monkeypatch.setattr(yt, "_canal", lambda c: "UC123")
    d = sd.normalizar(yt._api_demografia({}, date(2026, 7, 1), date(2026, 7, 30)))
    edad = d[d["dimension"] == "edad"]
    assert "65+" in set(edad["categoria"])
    assert not any(str(c).endswith("-") for c in edad["categoria"])


def test_pais_se_expresa_como_porcentaje_del_total_de_vistas(monkeypatch):
    """La unidad de YouTube es pct_visualizaciones para TODAS sus filas.
    País llega de la API como vistas absolutas; deben convertirse a %
    respetando la proporción entre países y sumar 100 en conjunto."""
    respuestas = {"ageGroup,gender": {"rows": []},
                  "country": {"rows": [["ES", 75], ["AR", 25]]}}
    monkeypatch.setattr(yt, "_servicios", lambda c: (_Analytics(respuestas), None))
    monkeypatch.setattr(yt, "_canal", lambda c: "UC123")
    d = sd.normalizar(yt._api_demografia({}, date(2026, 7, 1), date(2026, 7, 30)))
    pais = d[d["dimension"] == "pais"].set_index("categoria")["valor"]
    assert round(pais["ES"], 2) == 75.0
    assert round(pais["AR"], 2) == 25.0
    assert round(pais["ES"] + pais["AR"], 1) == 100.0


def test_pais_no_aparece_si_no_hay_vistas_en_el_periodo(monkeypatch):
    """Sin vistas no hay proporción que calcular: la dimensión no debe
    aparecer con un 0 inventado (nulo != cero)."""
    respuestas = {"ageGroup,gender": {"rows": []},
                  "country": {"rows": [["ES", 0], ["AR", 0]]}}
    monkeypatch.setattr(yt, "_servicios", lambda c: (_Analytics(respuestas), None))
    monkeypatch.setattr(yt, "_canal", lambda c: "UC123")
    d = sd.normalizar(yt._api_demografia({}, date(2026, 7, 1), date(2026, 7, 30)))
    assert "pais" not in set(d["dimension"])
