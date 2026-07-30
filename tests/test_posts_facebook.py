"""Traducción de los insights de publicación de Facebook.

Los nombres se sondearon contra la Página real el 30-jul-2026: toda la familia
post_impressions* está retirada; post_clicks, post_video_views y
post_reactions_by_type_total responden.
"""
from src.connectors import meta_organico as m


def _bloques(*pares):
    return {"data": [{"name": n, "values": [{"value": v}]} for n, v in pares]}


def test_captura_clics_y_reproducciones(monkeypatch):
    monkeypatch.setattr(m, "_get", lambda v, ruta, tok, params: _bloques(
        ("post_clicks", 17), ("post_video_views", 240)))
    out = m._insights_post_fb("v21.0", "p1", "tok")
    assert out["clics"] == 17
    assert out["visualizaciones"] == 240


def test_no_pide_metricas_retiradas(monkeypatch):
    """post_impressions* está retirada: pedirla hace que Meta rechace la
    llamada ENTERA y se pierdan también las métricas que sí existen."""
    pedidas = []

    def _get(v, ruta, tok, params):
        pedidas.append(params["metric"])
        return _bloques(("post_clicks", 1))

    monkeypatch.setattr(m, "_get", _get)
    m._insights_post_fb("v21.0", "p1", "tok")
    assert not any("post_impressions" in p for p in pedidas)


def test_una_metrica_que_falla_no_tumba_las_demas(monkeypatch):
    """Se piden de una en una: si Meta retira otra, el resto sigue entrando."""
    def _get(v, ruta, tok, params):
        if params["metric"] == "post_clicks":
            raise RuntimeError("(#100) not valid")
        return _bloques((params["metric"], 5))

    monkeypatch.setattr(m, "_get", _get)
    out = m._insights_post_fb("v21.0", "p1", "tok")
    assert "clics" not in out
    assert out["visualizaciones"] == 5
