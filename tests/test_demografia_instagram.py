"""La API se simula: estos tests comprueban la TRADUCCIÓN de su respuesta al
esquema, que es la parte con lógica. Contra la cuenta real se comprueba con
`scripts/verificar_social.py`.
"""
from datetime import date

from src.connectors import meta_organico as m
from src.data import social_demografia as sd


def _respuesta(breakdown, resultados):
    return {"data": [{"total_value": {"breakdowns": [{
        "results": [{"dimension_values": [k], "value": v}
                    for k, v in resultados.items()]}]}}]}


def test_traduce_los_desgloses_al_esquema(monkeypatch):
    respuestas = {
        "age": _respuesta("age", {"45-54": 145, "35-44": 107}),
        "gender": _respuesta("gender", {"F": 226, "M": 92}),
        "city": _respuesta("city", {"Barcelona, Cataluña": 42}),
        "country": _respuesta("country", {"ES": 399}),
    }
    monkeypatch.setattr(m, "_contexto_ig", lambda creds: ("IG1", "tok"))
    monkeypatch.setattr(m, "_get",
                        lambda v, ruta, tok, params: respuestas[params["breakdown"]])

    df = m._api_ig_demografia({}, date(2026, 7, 30))
    d = sd.normalizar(df)

    assert set(d["dimension"]) == {"edad", "genero", "ciudad", "pais"}
    edad = d[(d["dimension"] == "edad") & (d["categoria"] == "45-54")]
    assert edad.iloc[0]["valor"] == 145
    assert set(d["unidad"]) == {"seguidores"}
    assert set(d["fecha"]) == {date(2026, 7, 30)}


def test_un_desglose_que_falla_no_tumba_los_demas(monkeypatch):
    """Si Meta retira uno, los otros tres tienen que seguir entrando."""
    def _get(v, ruta, tok, params):
        if params["breakdown"] == "city":
            raise RuntimeError("(#100) not a valid metric")
        return _respuesta(params["breakdown"], {"X": 1})

    monkeypatch.setattr(m, "_contexto_ig", lambda creds: ("IG1", "tok"))
    monkeypatch.setattr(m, "_get", _get)

    d = sd.normalizar(m._api_ig_demografia({}, date(2026, 7, 30)))
    assert "ciudad" not in set(d["dimension"])
    assert {"edad", "genero", "pais"} <= set(d["dimension"])
