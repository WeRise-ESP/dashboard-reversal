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
