from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.connectors import base as cbase
from src.connectors import social_base
from src.data import social_demografia as sd


@pytest.fixture
def historico_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(cbase, "HISTORICO_DIR", tmp_path)
    return tmp_path


def test_la_demografia_se_acumula_sin_perder_capturas(historico_temporal):
    """Dos capturas de días distintos deben convivir: es lo que permitirá ver
    la deriva de la audiencia dentro de unos meses."""
    ayer = sd.normalizar(pd.DataFrame([
        {"fecha": date(2026, 7, 29), "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 140}]))
    hoy = sd.normalizar(pd.DataFrame([
        {"fecha": date(2026, 7, 30), "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 145}]))

    claves = ("fecha", "red", "dimension", "categoria")
    fusion = social_base.fusionar(ayer, hoy, claves)
    assert len(fusion) == 2
    assert set(fusion["valor"]) == {140, 145}


def test_una_recaptura_del_mismo_dia_corrige_sin_duplicar(historico_temporal):
    claves = ("fecha", "red", "dimension", "categoria")
    base = sd.normalizar(pd.DataFrame([
        {"fecha": date(2026, 7, 30), "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 140}]))
    nueva = sd.normalizar(pd.DataFrame([
        {"fecha": date(2026, 7, 30), "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 145}]))
    fusion = social_base.fusionar(base, nueva, claves)
    assert len(fusion) == 1
    assert fusion.iloc[0]["valor"] == 145


def test_sin_credenciales_no_escribe_nada(historico_temporal, monkeypatch):
    """La regla de oro del job: nunca datos inventados en el histórico."""
    import scripts.snapshot_social as snap
    monkeypatch.setattr(snap, "_leer_secreto", lambda s: None)
    fuente = snap.FUENTES_DEMOGRAFIA[0]
    df, motivo = snap.capturar_demografia(fuente, date(2026, 7, 1), date(2026, 7, 30))
    assert df is None
    assert "credenciales" in motivo
    assert list(Path(historico_temporal).glob("*.csv")) == []
