"""Conector de TikTok.

⚠️ SIN VERIFICAR contra ninguna cuenta: la app estaba sin crear el 31-jul-2026.
Estos tests fijan la TRADUCCIÓN de la respuesta al esquema, que es la parte con
lógica; lo que la API devuelve de verdad se comprueba con
`scripts/verificar_social.py --red TikTok` cuando llegue la credencial.
"""
from datetime import date, timedelta

import pandas as pd

from src.connectors import tiktok as tt


def _video(vid, dias_atras, **extra):
    ts = int(pd.Timestamp(date.today() - timedelta(days=dias_atras)).timestamp())
    return {"id": vid, "create_time": ts, "title": f"t{vid}",
            "share_url": f"https://tiktok.com/@x/video/{vid}", **extra}


def test_el_diario_devuelve_una_sola_foto_no_una_serie(monkeypatch):
    """La Display API no publica series diarias: devuelve el estado ACTUAL.
    Por eso el diario es UNA fila, y la serie se construye acumulando fotos en
    el histórico con el job. Si esto devolviera varias filas, alguien habría
    inventado datos que la API no da."""
    monkeypatch.setattr(tt, "_token", lambda c: "tok")
    monkeypatch.setattr(tt, "_post",
                        lambda ruta, token, campos, cuerpo=None:
                        {"user": {"follower_count": 412, "likes_count": 9000}})

    df = tt._api_diario({}, date(2026, 7, 1), date(2026, 7, 31))
    assert len(df) == 1
    assert df.iloc[0]["seguidores_total"] == 412
    assert df.iloc[0]["fecha"] == date(2026, 7, 31)


def test_el_diario_no_mete_totales_de_cuenta_en_columnas_de_flujo(monkeypatch):
    """`likes_count` es el total histórico de la cuenta, no los likes del día.
    Ponerlo en la columna `likes` dispararía cualquier suma del periodo."""
    monkeypatch.setattr(tt, "_token", lambda c: "tok")
    monkeypatch.setattr(tt, "_post",
                        lambda ruta, token, campos, cuerpo=None:
                        {"user": {"follower_count": 412, "likes_count": 9000}})

    df = tt._api_diario({}, date(2026, 7, 1), date(2026, 7, 31))
    assert "likes" not in df.columns or pd.isna(df.iloc[0].get("likes"))


def test_los_videos_se_filtran_por_fecha_y_se_corta_al_salir_del_rango(monkeypatch):
    """Vienen del más nuevo al más viejo, así que en cuanto aparece uno anterior
    a `desde` se deja de paginar en vez de recorrer el canal entero."""
    paginas = [
        {"videos": [_video("a", 1, view_count=100), _video("b", 5, view_count=50)],
         "cursor": 1, "has_more": True},
        {"videos": [_video("c", 400, view_count=10)], "cursor": 2, "has_more": True},
        {"videos": [_video("d", 500)], "cursor": 3, "has_more": True},
    ]
    pedidas = []

    def _post(ruta, token, campos, cuerpo=None):
        pedidas.append(cuerpo)
        return paginas[len(pedidas) - 1]

    monkeypatch.setattr(tt, "_token", lambda c: "tok")
    monkeypatch.setattr(tt, "_post", _post)

    hasta = date.today()
    df = tt._api_posts({}, hasta - timedelta(days=30), hasta)
    assert list(df["post_id"]) == ["a", "b"]
    assert len(pedidas) == 2, "debería cortar al ver el vídeo antiguo, no seguir"


def test_un_error_dentro_del_cuerpo_se_detecta(monkeypatch):
    """TikTok devuelve HTTP 200 con el error DENTRO del JSON, así que
    `raise_for_status` no basta."""
    class _R:
        status_code = 200
        content = b"x"

        def json(self):
            return {"error": {"code": "access_token_invalid",
                              "message": "token caducado"}}

        def raise_for_status(self):
            pass

    monkeypatch.setattr("requests.post", lambda *a, **k: _R())
    try:
        tt._post("user/info/", "tok", "campos")
    except RuntimeError as e:
        assert "access_token_invalid" in str(e)
    else:
        raise AssertionError("un error con HTTP 200 debe lanzar excepción")


def test_tiktok_esta_marcado_sin_verificar():
    """Mientras la app no exista, ninguna métrica declarada debe darse por buena:
    la página las muestra como «—» en vez de números que nadie ha visto."""
    from src import config

    for m in ("visualizaciones", "likes", "comentarios", "compartidos"):
        assert not config.soporta_metrica(m, "TikTok"), (
            f"{m} de TikTok se da por soportada sin haberla sondeado nunca"
        )
