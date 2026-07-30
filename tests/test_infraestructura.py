"""Comprueba que el arnés de tests puede importar el proyecto."""


def test_se_puede_importar_config():
    from src import config
    assert config.REDES_SOCIAL == ("YouTube", "Facebook", "Instagram", "LinkedIn")


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
