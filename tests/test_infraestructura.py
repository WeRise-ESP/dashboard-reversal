"""Comprueba que el arnés de tests puede importar el proyecto."""


def test_se_puede_importar_config():
    from src import config
    assert "Instagram" in config.REDES_SOCIAL
    assert len(config.REDES_SOCIAL) >= 4


def test_cada_red_tiene_color_y_simbolo():
    """El símbolo no es decorativo: con cinco series el peor par de la paleta
    queda en ΔE 6,2 bajo protanopia, que solo es admisible si la identidad no
    depende únicamente del color. Si una red se queda sin símbolo, la paleta
    deja de ser válida."""
    from src import config

    for red in config.REDES_SOCIAL:
        assert red in config.COLOR_RED_SOCIAL, f"{red} sin color"
        assert red in config.SIMBOLO_RED_SOCIAL, f"{red} sin símbolo"
    assert len(set(config.COLOR_RED_SOCIAL.values())) == len(config.REDES_SOCIAL)
    assert len(set(config.SIMBOLO_RED_SOCIAL.values())) == len(config.REDES_SOCIAL)


def test_los_modulos_de_datos_no_importan_streamlit():
    """`social`, `social_analisis` y `social_demografia` deben ser probables sin Streamlit."""
    import subprocess
    import sys

    modulos = ["social", "social_analisis", "social_demografia"]
    for modulo in modulos:
        codigo = (
            "import sys; sys.modules['streamlit'] = None;"
            f"from src.data import {modulo}; print('ok')"
        )
        r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True)
        assert r.returncode == 0, f"Error en {modulo}: {r.stderr}"
