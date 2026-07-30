from datetime import date

from src.connectors import linkedin as li
from src.data import social_demografia as sd


def test_traduce_los_desgloses_de_seguidores(monkeypatch):
    respuesta = {"elements": [{
        "followerCountsByStaffCountRange": [
            {"staffCountRange": "SIZE_11_TO_50", "followerCounts": {"organicFollowerCount": 12}}],
        "followerCountsByIndustry": [
            {"industry": "urn:li:industry:14", "followerCounts": {"organicFollowerCount": 30}}],
        "followerCountsByFunction": [
            {"function": "urn:li:function:14", "followerCounts": {"organicFollowerCount": 8}}],
        "followerCountsBySeniority": [
            {"seniority": "urn:li:seniority:6", "followerCounts": {"organicFollowerCount": 5}}],
        "followerCountsByGeoCountry": [
            {"geo": "urn:li:geo:105646813", "followerCounts": {"organicFollowerCount": 40}}],
    }]}
    monkeypatch.setattr(li, "_token", lambda creds: "tok")
    monkeypatch.setattr(li, "_org_urn", lambda creds: "urn:li:organization:123114024")
    monkeypatch.setattr(li, "_get", lambda ruta, creds, token, params=None: respuesta)

    d = sd.normalizar(li._api_demografia({}))

    assert {"tamano_empresa", "sector", "funcion", "cargo", "pais"} <= set(d["dimension"])
    assert d[d["dimension"] == "pais"].iloc[0]["valor"] == 40
    assert set(d["unidad"]) == {"seguidores"}


def test_linkedin_no_aporta_edad_ni_genero(monkeypatch):
    """Su API no los publica en ninguna versión. Si algún día aparecieran,
    este test falla y obliga a revisar el diseño en vez de colarlos.

    La respuesta simulada se construye A PARTIR de `_DESGLOSES_LI` (el mapa
    real), no de una lista fija de campos: así, si alguien añade una entrada
    para edad o género al mapa, la respuesta simulada trae ese campo con
    datos y la fila aparece — el test la detecta de verdad. Con `elements`
    vacío (como antes) el test pasaría siempre, mapee lo que mapee el
    diccionario, porque `_api_demografia` sale antes de leerlo.
    """
    elemento = {
        campo: [{clave: f"urn:li:test:{i}", "followerCounts": {"organicFollowerCount": 1}}]
        for i, (campo, (clave, _dimension)) in enumerate(li._DESGLOSES_LI.items())
    }
    monkeypatch.setattr(li, "_token", lambda creds: "tok")
    monkeypatch.setattr(li, "_org_urn", lambda creds: "urn:li:organization:1")
    monkeypatch.setattr(li, "_get",
                        lambda ruta, creds, token, params=None: {"elements": [elemento]})

    d = sd.normalizar(li._api_demografia({}))

    assert "edad" not in set(d["dimension"])
    assert "genero" not in set(d["dimension"])


def test_un_item_sin_clave_de_categoria_se_salta(monkeypatch):
    """Nulo != cero también aplica a la categoría, no solo al valor.

    Un item sin la clave de categoría (p. ej. sin `industry`) no debe colarse
    como una fila con `categoria=None`: no aporta nada legible en la UI. Igual
    que `_api_ig_demografia` en meta_organico.py.
    """
    respuesta = {"elements": [{
        "followerCountsByIndustry": [
            {"followerCounts": {"organicFollowerCount": 30}},  # sin "industry"
            {"industry": "urn:li:industry:14", "followerCounts": {"organicFollowerCount": 7}},
        ],
    }]}
    monkeypatch.setattr(li, "_token", lambda creds: "tok")
    monkeypatch.setattr(li, "_org_urn", lambda creds: "urn:li:organization:1")
    monkeypatch.setattr(li, "_get", lambda ruta, creds, token, params=None: respuesta)

    d = sd.normalizar(li._api_demografia({}))
    sector = d[d["dimension"] == "sector"]

    assert len(sector) == 1
    assert sector.iloc[0]["valor"] == 7
    assert sector.iloc[0]["categoria"] == "urn:li:industry:14"
