"""Selección de publicaciones de YouTube.

La lista sale de la Data API (qué se publicó) y las métricas de Analytics (qué
rindió). Mezclarlo al revés —usar Analytics como lista— produce dos errores a la
vez, y los dos se vieron contra el canal real el 30-jul-2026.
"""
from datetime import date

from src.connectors import youtube as yt


class _Ej:
    def __init__(self, d): self._d = d
    def execute(self): return self._d


class _Lista:
    """Sirve tanto para `.list(...)` de la Data API como para `.query(...)` de
    Analytics: las dos devuelven un objeto con `.execute()`."""
    def __init__(self, d): self._d = d
    def list(self, **kw): return _Ej(self._d)
    def query(self, **kw): return _Ej(self._d)


class _Data:
    def __init__(self, canales, items, videos=None):
        self._c, self._i, self._v = canales, items, videos or {}
    def channels(self): return _Lista(self._c)
    def playlistItems(self): return _Lista(self._i)
    def videos(self): return _Lista(self._v)


_CANAL = {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}


def _items(*pares):
    return {"items": [{"contentDetails": {"videoId": v, "videoPublishedAt": f"{f}T10:00:00Z"}}
                      if f else {"contentDetails": {"videoId": v}}
                      for v, f in pares]}


def test_solo_los_publicados_dentro_del_periodo():
    """Un vídeo de hace meses no debe colarse por seguir sumando vistas."""
    data = _Data(_CANAL, _items(("dentro", "2026-07-15"), ("fuera", "2026-05-01")))
    ids = yt._videos_publicados(data, "UC1", date(2026, 7, 1), date(2026, 7, 30))
    assert ids == ["dentro"]


def test_incluye_el_video_de_hoy():
    """Recién subido: Analytics no tiene datos aún, pero el vídeo existe."""
    data = _Data(_CANAL, _items(("hoy", "2026-07-30")))
    ids = yt._videos_publicados(data, "UC1", date(2026, 7, 1), date(2026, 7, 30))
    assert ids == ["hoy"]


def test_los_borrados_se_descartan():
    """Una entrada sin fecha de publicación es un vídeo borrado o privado: la
    fila sigue en la lista de subidas pero ya no existe para nadie."""
    data = _Data(_CANAL, _items(("vivo", "2026-07-10"), ("borrado", None)))
    ids = yt._videos_publicados(data, "UC1", date(2026, 7, 1), date(2026, 7, 30))
    assert ids == ["vivo"]


def test_sin_metricas_la_casilla_queda_nula_no_a_cero(monkeypatch):
    """Que Analytics no reporte un vídeo no significa que tenga 0
    visualizaciones: significa que no hay dato."""
    class _An:
        def reports(self):
            return _Lista({"columnHeaders": [{"name": "video"}, {"name": "views"}],
                           "rows": [["con_datos", 100]]})

    data = _Data(_CANAL, _items(("con_datos", "2026-07-10"), ("sin_datos", "2026-07-11")))
    monkeypatch.setattr(yt, "_servicios", lambda c: (_An(), data))
    monkeypatch.setattr(yt, "_canal", lambda c: "UC1")
    monkeypatch.setattr(yt, "_detalles_videos", lambda d, ids: {
        i: {"titulo": i, "fecha": "2026-07-10", "tipo": "Short", "miniatura": ""} for i in ids})

    df = yt._api_posts({}, date(2026, 7, 1), date(2026, 7, 30))
    por_id = df.set_index("post_id")["visualizaciones"]
    assert por_id["con_datos"] == 100
    assert por_id["sin_datos"] is None or str(por_id["sin_datos"]) in ("nan", "<NA>", "None")


def test_las_visualizaciones_totales_solo_las_publica_youtube():
    """El contador público acumulado es una métrica DISTINTA de las del periodo.

    Existe porque Studio y Analytics no siempre coinciden: verificado el
    30-jul-2026, un vídeo con 1.203 visualizaciones en el contador público no
    aparecía en Analytics en ninguna ventana. En Instagram y Facebook las
    métricas por publicación ya son acumuladas, así que allí duplicaría.
    """
    from src import config

    assert config.soporta_metrica("visualizaciones_totales", "YouTube", "post")
    for red in ("Instagram", "Facebook", "LinkedIn"):
        assert not config.soporta_metrica("visualizaciones_totales", red, "post")


def test_las_totales_sobreviven_aunque_analytics_no_reporte(monkeypatch):
    """El caso real: Analytics no devuelve el vídeo, pero el contador público
    sí. Sin esta columna se vería «—» y parecería que no lo vio nadie."""
    from datetime import date as _d

    class _An:
        def reports(self):
            return _Lista({"columnHeaders": [], "rows": []})

    data = _Data(_CANAL, _items(("mudo", "2026-07-23")))
    monkeypatch.setattr(yt, "_servicios", lambda c: (_An(), data))
    monkeypatch.setattr(yt, "_canal", lambda c: "UC1")
    monkeypatch.setattr(yt, "_detalles_videos", lambda d, ids: {
        "mudo": {"titulo": "t", "fecha": "2026-07-23", "tipo": "Short",
                 "miniatura": "", "visualizaciones_totales": 1203}})

    df = yt._api_posts({}, _d(2026, 7, 1), _d(2026, 7, 30))
    fila = df.iloc[0]
    assert fila["visualizaciones_totales"] == 1203
    assert fila["visualizaciones"] is None
