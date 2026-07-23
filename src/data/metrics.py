"""
Cálculo de métricas de marketing: agregados de plataforma, CPL (plataforma y
neto), ROAS, embudo lead->matrícula y asociación de leads de HubSpot a campañas.

Definiciones (alineadas con la skill de performance-report):
- CPL plataforma  = coste de la plataforma / leads atribuidos EN esa plataforma.
- CPL neto        = inversión total / leads válidos totales (incluye no atribuidos).
- CPA/CP-matrícula= inversión total / nº de matrículas.
- ROAS            = (matrículas * valor_matrícula) / inversión total.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from src import config


def _norm_campana(s: str) -> str:
    """Normaliza un nombre de campaña para casar ads (Google/Meta) con HubSpot."""
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _safe_div(a: float, b: float) -> float:
    return float(a) / float(b) if b else 0.0


def con_fila_total(df: pd.DataFrame, etiqueta_col: str, etiqueta: str = "TOTAL",
                   ratios: dict | None = None) -> pd.DataFrame:
    """Devuelve el df con una fila de totales al final.

    - Columnas numéricas: se suman.
    - Columnas de ratio (CPL, CTR, ROAS…): pasa un dict `ratios` con
      {columna: fn(sumas, df)} para recalcularlas sobre los totales.
    - `etiqueta_col`: columna de texto donde se escribe "TOTAL".
    """
    if df is None or df.empty:
        return df
    ratios = ratios or {}
    num_cols = [c for c in df.columns
                if c != etiqueta_col and pd.api.types.is_numeric_dtype(df[c])]
    sumas = {c: df[c].sum() for c in num_cols}
    fila = {}
    for c in df.columns:
        if c == etiqueta_col:
            fila[c] = etiqueta
        elif c in ratios:
            try:
                fila[c] = ratios[c](sumas, df)
            except Exception:  # noqa: BLE001
                fila[c] = 0
        elif c in num_cols:
            fila[c] = sumas[c]
        else:
            fila[c] = ""
    return pd.concat([df, pd.DataFrame([fila])], ignore_index=True)


# --------------------------------------------------------------------------- #
# Agregados por plataforma
# --------------------------------------------------------------------------- #
def resumen_plataforma(df_ads: pd.DataFrame) -> pd.DataFrame:
    """Agrega gasto/clics/impresiones/conversiones por plataforma."""
    if df_ads.empty:
        return pd.DataFrame()
    g = (
        df_ads.groupby("plataforma", as_index=False)
        .agg(
            impresiones=("impresiones", "sum"),
            clics=("clics", "sum"),
            coste=("coste", "sum"),
            conversiones=("conversiones", "sum"),
        )
    )
    g["ctr"] = g.apply(lambda r: _safe_div(r["clics"], r["impresiones"]), axis=1)
    g["cpc"] = g.apply(lambda r: _safe_div(r["coste"], r["clics"]), axis=1)
    g["cpm"] = g.apply(lambda r: _safe_div(r["coste"] * 1000, r["impresiones"]), axis=1)
    return g


def resumen_campana(df_ads: pd.DataFrame) -> pd.DataFrame:
    """Agrega por campaña y añade el programa académico asociado."""
    if df_ads.empty:
        return pd.DataFrame()
    g = (
        df_ads.groupby(["plataforma", "campana"], as_index=False)
        .agg(
            impresiones=("impresiones", "sum"),
            clics=("clics", "sum"),
            coste=("coste", "sum"),
            conversiones=("conversiones", "sum"),
        )
    )
    # El estado es atributo de la campaña (igual en todas sus filas diarias).
    if "estado" in df_ads:
        est = df_ads.groupby("campana")["estado"].first()
        g["estado"] = g["campana"].map(est).fillna("—")
    g["programa"] = g["campana"].map(config.programa_por_campana)
    g["ctr"] = g.apply(lambda r: _safe_div(r["clics"], r["impresiones"]), axis=1)
    g["cpc"] = g.apply(lambda r: _safe_div(r["coste"], r["clics"]), axis=1)
    return g.sort_values("coste", ascending=False)


# --------------------------------------------------------------------------- #
# Leads (HubSpot) y su cruce con inversión — TODO POR PROGRAMA
# --------------------------------------------------------------------------- #
def resumen_ads_por_programa(df_ads: pd.DataFrame) -> pd.DataFrame:
    """Agrega inversión/clics/impresiones por canal (mapeando plataforma→canal),
    para poder cruzarlo con los leads de HubSpot (atribuidos por canal)."""
    if df_ads.empty:
        return pd.DataFrame()
    df = df_ads.copy()
    df["programa"] = df["plataforma"].apply(config.canal_por_plataforma)
    return df.groupby("programa", as_index=False).agg(
        impresiones=("impresiones", "sum"),
        clics=("clics", "sum"),
        coste=("coste", "sum"),
    )


def resumen_leads_por_programa(df_leads: pd.DataFrame) -> pd.DataFrame:
    """Cuenta leads por programa."""
    if df_leads.empty:
        return pd.DataFrame()
    return (
        df_leads.groupby("programa", as_index=False)
        .agg(leads=("lead_id", "count"))
        .sort_values("leads", ascending=False)
    )


def matriculas_por_programa(df_deals: pd.DataFrame) -> pd.DataFrame:
    """Cuenta matrículas (deals ganados) por programa."""
    if df_deals.empty:
        return pd.DataFrame(columns=["programa", "matriculas"])
    ganados = df_deals[df_deals["es_ganado"] == True]  # noqa: E712
    if ganados.empty:
        return pd.DataFrame(columns=["programa", "matriculas"])
    return ganados.groupby("programa", as_index=False).agg(matriculas=("deal_id", "count"))


def matriculas_por_campana(df_deals: pd.DataFrame) -> pd.DataFrame:
    """Cuenta matrículas (deals ganados) por CAMPAÑA del deal (deal.campana)."""
    if df_deals is None or df_deals.empty or "campana" not in df_deals:
        return pd.DataFrame(columns=["campana", "matriculas"])
    won = df_deals[df_deals["es_ganado"] == True]  # noqa: E712
    if won.empty:
        return pd.DataFrame(columns=["campana", "matriculas"])
    return won.groupby("campana", as_index=False).agg(matriculas=("deal_id", "count"))


def matriculas_canal(df_deals: pd.DataFrame, canal: str) -> int:
    """Nº de matrículas (deals ganados) atribuidas a un canal (deal.programa)."""
    if df_deals is None or df_deals.empty or "programa" not in df_deals:
        return 0
    return int(((df_deals["es_ganado"] == True) &  # noqa: E712
                (df_deals["programa"] == canal)).sum())


def ingresos_por_programa(df_deals: pd.DataFrame) -> pd.DataFrame:
    """Ingresos REALES (amount de deals ganados) por canal/programa."""
    if df_deals is None or df_deals.empty or "amount" not in df_deals:
        return pd.DataFrame(columns=["programa", "ingresos"])
    won = df_deals[df_deals["es_ganado"] == True]  # noqa: E712
    if won.empty:
        return pd.DataFrame(columns=["programa", "ingresos"])
    return won.groupby("programa", as_index=False).agg(ingresos=("amount", "sum"))


def ingresos_por_campana(df_deals: pd.DataFrame) -> pd.DataFrame:
    """Ingresos REALES (amount de deals ganados) por CAMPAÑA del deal."""
    if df_deals is None or df_deals.empty or "amount" not in df_deals or "campana" not in df_deals:
        return pd.DataFrame(columns=["campana", "ingresos"])
    won = df_deals[df_deals["es_ganado"] == True]  # noqa: E712
    if won.empty:
        return pd.DataFrame(columns=["campana", "ingresos"])
    return won.groupby("campana", as_index=False).agg(ingresos=("amount", "sum"))


def cruce_inversion_leads(df_ads: pd.DataFrame, df_leads: pd.DataFrame,
                          df_deals: pd.DataFrame | None = None) -> pd.DataFrame:
    """Une, POR CANAL, inversión (Google+Meta) con leads y matrículas (HubSpot),
    y calcula CPL, coste/matrícula y ROAS.

    Incluye TODOS los canales presentes en leads o en inversión (también los
    no-pago: Directo, Otras campañas, Social orgánico, Offline… con inversión 0).
    """
    ads = resumen_ads_por_programa(df_ads)
    leads = resumen_leads_por_programa(df_leads)
    mats = matriculas_por_programa(df_deals if df_deals is not None else pd.DataFrame())
    if ads.empty and leads.empty:
        return pd.DataFrame()
    if ads.empty:
        ads = pd.DataFrame(columns=["programa", "impresiones", "clics", "coste"])
    if leads.empty:
        leads = pd.DataFrame(columns=["programa", "leads"])

    m = ads.merge(leads, on="programa", how="outer")
    if not mats.empty:
        m = m.merge(mats, on="programa", how="outer")
    else:
        m["matriculas"] = 0
    for col in ("impresiones", "clics", "coste"):
        if col in m:
            m[col] = m[col].fillna(0)
    m["leads"] = m["leads"].fillna(0).astype(int)
    m["matriculas"] = m["matriculas"].fillna(0).astype(int)

    # Ingresos REALES (amount de deals ganados) por canal.
    ing = ingresos_por_programa(df_deals if df_deals is not None else pd.DataFrame())
    if not ing.empty:
        m = m.merge(ing, on="programa", how="left")
    if "ingresos" not in m:
        m["ingresos"] = 0.0
    m["ingresos"] = m["ingresos"].fillna(0.0)

    m["cpl"] = m.apply(lambda r: _safe_div(r["coste"], r["leads"]), axis=1)
    m["cp_matricula"] = m.apply(lambda r: _safe_div(r["coste"], r["matriculas"]), axis=1)
    m["roas"] = m.apply(lambda r: _safe_div(r["ingresos"], r["coste"]), axis=1)
    return m.sort_values(["coste", "leads"], ascending=False)


# --------------------------------------------------------------------------- #
# KPIs globales
# --------------------------------------------------------------------------- #
def kpis_globales(df_ads: pd.DataFrame, df_leads: pd.DataFrame,
                  df_deals: pd.DataFrame | None = None) -> dict:
    """KPIs de cabecera. Leads = contactos del portal de Reversal; matrículas =
    deals ganados (Closed Won) del pipeline. Inversión = total de Google + Meta."""
    inversion = float(df_ads["coste"].sum()) if not df_ads.empty else 0.0

    leads_total = int(len(df_leads)) if not df_leads.empty else 0
    leads_con_programa = (
        int((df_leads["programa"] != "Sin asignar").sum()) if not df_leads.empty else 0
    )
    if df_deals is not None and not df_deals.empty:
        matriculas = int(df_deals["es_ganado"].sum())
        deals_totales = int(len(df_deals))
        # Ingresos REALES = amount de los deals ganados (no la estimación).
        ingresos = (float(df_deals.loc[df_deals["es_ganado"], "amount"].sum())
                    if "amount" in df_deals else matriculas * config.VALOR_MATRICULA)
    else:
        matriculas = 0
        deals_totales = 0
        ingresos = 0.0

    cpl_neto = _safe_div(inversion, leads_total)
    cp_matricula = _safe_div(inversion, matriculas)
    roas = _safe_div(ingresos, inversion)
    pct_programa = _safe_div(leads_con_programa, leads_total)
    matriculas_forecast = leads_total * config.TASA_LEAD_A_MATRICULA

    return dict(
        inversion=inversion,
        leads_total=leads_total,
        leads_con_programa=leads_con_programa,
        pct_programa=pct_programa,
        deals_totales=deals_totales,
        matriculas=matriculas,
        matriculas_forecast=matriculas_forecast,
        ingresos=ingresos,
        cpl_neto=cpl_neto,
        cp_matricula=cp_matricula,
        roas=roas,
        objetivo_matriculas=config.OBJETIVO_MATRICULAS,
        objetivo_inversion=config.OBJETIVO_INVERSION_MENSUAL,
    )


# --------------------------------------------------------------------------- #
# Embudo del Pipeline UVIC (deals)
# --------------------------------------------------------------------------- #
ORDEN_EMBUDO = [lbl for _id, lbl in config.HUBSPOT_ETAPAS_UVIC]


def embudo(df_deals: pd.DataFrame) -> pd.DataFrame:
    """Embudo acumulado por etapa del Pipeline UVIC (un deal en una etapa avanzada
    pasó por las anteriores). Excluye 'Cierre perdido'."""
    if df_deals.empty:
        return pd.DataFrame()
    idx = {etapa: i for i, etapa in enumerate(ORDEN_EMBUDO)}
    df = df_deals.copy()
    df["nivel"] = df["etapa"].map(idx)
    df = df.dropna(subset=["nivel"])  # descarta 'Cierre perdido' u otras
    filas = []
    for i, etapa in enumerate(ORDEN_EMBUDO):
        n = int((df["nivel"] >= i).sum())
        filas.append(dict(etapa=etapa, leads=n))
    out = pd.DataFrame(filas)
    total = out["leads"].iloc[0] if not out.empty else 0
    out["pct"] = out["leads"].apply(lambda x: _safe_div(x, total))
    return out


# --------------------------------------------------------------------------- #
# Series temporales
# --------------------------------------------------------------------------- #
def serie_diaria_inversion(df_ads: pd.DataFrame) -> pd.DataFrame:
    if df_ads.empty:
        return pd.DataFrame()
    return (
        df_ads.groupby(["fecha", "plataforma"], as_index=False)["coste"].sum()
    )


def valor_pipeline(df_deals: pd.DataFrame) -> dict:
    """Valor económico (amount) del pipeline: abierto, ganado, total, ticket medio."""
    if df_deals is None or df_deals.empty or "amount" not in df_deals:
        return dict(abierto=0.0, ganado=0.0, total=0.0, ticket=0.0, n_importe=0)
    d = df_deals
    perdido = d["etapa"] == "Cierre perdido"
    ganado = float(d.loc[d["es_ganado"], "amount"].sum())
    abierto = float(d.loc[~d["es_ganado"] & ~perdido, "amount"].sum())
    con_imp = d[d["amount"] > 0]
    ticket = float(con_imp["amount"].mean()) if not con_imp.empty else 0.0
    return dict(abierto=abierto, ganado=ganado, total=float(d["amount"].sum()),
                ticket=ticket, n_importe=int(len(con_imp)))


def embudo_tasas(df_deals: pd.DataFrame) -> pd.DataFrame:
    """Embudo del pipeline con la tasa de paso entre etapas consecutivas."""
    emb = embudo(df_deals)
    if emb.empty:
        return emb
    emb = emb.copy()
    prev = emb["leads"].shift(1)
    emb["conv_paso"] = (emb["leads"] / prev).where(prev.notna() & (prev > 0), 1.0)
    return emb


def leads_por_estado(df_leads: pd.DataFrame) -> pd.DataFrame:
    """Reparto de leads por estado del ciclo de vida (Lead/MQL/SQL/Oportunidad…)."""
    if df_leads is None or df_leads.empty or "estado" not in df_leads:
        return pd.DataFrame()
    orden = ["Suscriptor", "Lead", "MQL", "SQL", "Oportunidad",
             "Matriculado", "Prescriptor", "Descartado", "Otro"]
    g = (df_leads.groupby("estado", as_index=False)["lead_id"].count()
         .rename(columns={"lead_id": "leads"}))
    g["orden"] = g["estado"].map({e: i for i, e in enumerate(orden)}).fillna(99)
    return g.sort_values("orden").drop(columns="orden").reset_index(drop=True)


def embudo_marketing(ga4_extra: dict | None, df_leads: pd.DataFrame,
                     df_deals: pd.DataFrame | None = None) -> dict:
    """Embudo de marketing extremo a extremo: Sesiones → Leads → Matrículas,
    con las tasas de conversión de cada paso."""
    ses = int((ga4_extra or {}).get("totales", {}).get("sesiones", 0))
    leads = int(len(df_leads)) if df_leads is not None else 0
    mat = int(df_deals["es_ganado"].sum()) if df_deals is not None and not df_deals.empty else 0
    return dict(
        sesiones=ses, leads=leads, matriculas=mat,
        tasa_lead=_safe_div(leads, ses),        # sesión -> lead
        tasa_matricula=_safe_div(mat, leads),   # lead -> matrícula
    )


def serie_diaria_leads(df_leads: pd.DataFrame) -> pd.DataFrame:
    if df_leads.empty:
        return pd.DataFrame()
    g = df_leads.groupby("fecha_creacion", as_index=False)["lead_id"].count()
    return g.rename(columns={"fecha_creacion": "fecha", "lead_id": "leads"})


def serie_diaria_leads_por_canal(df_leads: pd.DataFrame) -> pd.DataFrame:
    """Leads por día y canal (para el área apilada; la suma = total diario)."""
    if df_leads is None or df_leads.empty:
        return pd.DataFrame()
    g = df_leads.groupby(["fecha_creacion", "programa"], as_index=False)["lead_id"].count()
    return g.rename(columns={"fecha_creacion": "fecha", "lead_id": "leads"})


def leads_por_programa_dist(df_leads: pd.DataFrame) -> pd.DataFrame:
    """Reparto de leads por programa (para el donut del resumen)."""
    if df_leads.empty:
        return pd.DataFrame()
    return (
        df_leads.groupby("programa", as_index=False)["lead_id"].count()
        .rename(columns={"lead_id": "leads"})
    )


_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _label_semana(p) -> str:
    a, b = p.start_time, p.end_time
    return f"{a.day} {_MESES[a.month - 1]} – {b.day} {_MESES[b.month - 1]}"


def resumen_semanal(df_plat: pd.DataFrame, df_leads: pd.DataFrame | None = None,
                    canal: str | None = None, campana: str | None = None) -> pd.DataFrame:
    """Agrega las métricas de una plataforma por SEMANA (lun–dom) para ver la
    evolución. Cruza con leads/matrículas de HubSpot. Si se pasa `campana`, filtra
    a esa campaña (y casa los leads por nombre de campaña); si no, usa el `canal`.
    Devuelve filas ordenadas cronológicamente (semana más antigua arriba)."""
    if df_plat is None or df_plat.empty:
        return pd.DataFrame()
    d = df_plat.copy()
    if campana is not None:
        d = d[d["campana"] == campana]
    if d.empty:
        return pd.DataFrame()
    d["fecha"] = pd.to_datetime(d["fecha"])
    d["semana"] = d["fecha"].dt.to_period("W-SUN")
    g = d.groupby("semana", as_index=False).agg(
        impresiones=("impresiones", "sum"),
        clics=("clics", "sum"),
        coste=("coste", "sum"),
        conversiones=("conversiones", "sum"),
    )
    # Selección de leads: por campaña (nombre) o por canal.
    lc = None
    if df_leads is not None and not df_leads.empty:
        if campana is not None:
            lc = df_leads[df_leads["campana"].map(_norm_campana) == _norm_campana(campana)].copy()
        elif canal:
            lc = df_leads[df_leads["fuente"] == canal].copy()
    if lc is not None:
        lc = lc.dropna(subset=["fecha_creacion"])
        if not lc.empty:
            lc["semana"] = pd.to_datetime(lc["fecha_creacion"]).dt.to_period("W-SUN")
            lg = lc.groupby("semana", as_index=False).agg(
                leads=("lead_id", "count"), matriculas=("es_matricula", "sum"))
            g = g.merge(lg, on="semana", how="left")
    for col in ("leads", "matriculas"):
        if col not in g:
            g[col] = 0
        g[col] = g[col].fillna(0).astype(int)

    g["ctr"] = g.apply(lambda r: _safe_div(r["clics"], r["impresiones"]), axis=1)
    g["cpc"] = g.apply(lambda r: _safe_div(r["coste"], r["clics"]), axis=1)
    g["cpl"] = g.apply(lambda r: _safe_div(r["coste"], r["leads"]), axis=1)
    g = g.sort_values("semana").reset_index(drop=True)
    g["semana_label"] = g["semana"].apply(_label_semana)
    return g


# Métricas disponibles para la evolución semanal por campaña.
METRICAS_EVOL = {
    "Inversión (€)": {"tipo": "sum", "col": "coste"},
    "Clics": {"tipo": "sum", "col": "clics"},
    "Impresiones": {"tipo": "sum", "col": "impresiones"},
    "Conversiones / Resultados": {"tipo": "sum", "col": "conversiones"},
    "Leads (HubSpot)": {"tipo": "sum", "col": "leads"},
    "Matrículas": {"tipo": "sum", "col": "matriculas"},
    "CPL (€)": {"tipo": "ratio", "num": "coste", "den": "leads"},
    "CPC (€)": {"tipo": "ratio", "num": "coste", "den": "clics"},
    "CTR (%)": {"tipo": "ratio", "num": "clics", "den": "impresiones"},
}


def _base_campana_semana(df_plat: pd.DataFrame, df_leads: pd.DataFrame | None,
                         canal: str | None) -> pd.DataFrame:
    """Métricas de ads por (campaña, semana) + leads/matrículas de HubSpot
    casados por nombre de campaña."""
    d = df_plat.copy()
    d["fecha"] = pd.to_datetime(d["fecha"])
    d["semana"] = d["fecha"].dt.to_period("W-SUN")
    ad = d.groupby(["campana", "semana"], as_index=False).agg(
        impresiones=("impresiones", "sum"), clics=("clics", "sum"),
        coste=("coste", "sum"), conversiones=("conversiones", "sum"))
    ad["k"] = ad["campana"].map(_norm_campana)
    if df_leads is not None and canal and not df_leads.empty:
        lc = df_leads[df_leads["fuente"] == canal].dropna(subset=["fecha_creacion"]).copy()
        if not lc.empty:
            lc["semana"] = pd.to_datetime(lc["fecha_creacion"]).dt.to_period("W-SUN")
            lc["k"] = lc["campana"].map(_norm_campana)
            lg = lc.groupby(["k", "semana"], as_index=False).agg(
                leads=("lead_id", "count"), matriculas=("es_matricula", "sum"))
            ad = ad.merge(lg, on=["k", "semana"], how="left")
    for c in ("leads", "matriculas"):
        if c not in ad:
            ad[c] = 0
        ad[c] = ad[c].fillna(0).astype(int)
    return ad


def evolucion_campana_semanal(df_plat: pd.DataFrame, df_leads: pd.DataFrame | None,
                              canal: str | None, metrica: str) -> dict | None:
    """Pivote campaña × semana para la métrica elegida, con columna y fila Total.
    Devuelve {"df", "semanas"} o None si no hay datos."""
    if df_plat is None or df_plat.empty:
        return None
    spec = METRICAS_EVOL[metrica]
    base = _base_campana_semana(df_plat, df_leads, canal)
    if base.empty:
        return None
    semanas = sorted(base["semana"].unique())
    labels = [_label_semana(s) for s in semanas]

    def valor(sub, s):
        if spec["tipo"] == "sum":
            v = sub[spec["col"]]
            return float(v.get(s, 0)) if hasattr(v, "get") else 0
        num = float(sub[spec["num"]].get(s, 0))
        den = float(sub[spec["den"]].get(s, 0))
        return num / den if den else 0

    def total(df_sub):
        if spec["tipo"] == "sum":
            return float(df_sub[spec["col"]].sum())
        num, den = df_sub[spec["num"]].sum(), df_sub[spec["den"]].sum()
        return float(num / den) if den else 0

    campanas = (base.groupby("campana")["coste"].sum()
                .sort_values(ascending=False).index.tolist())
    filas = []
    for camp in campanas:
        sub_df = base[base["campana"] == camp]
        sub = sub_df.set_index("semana")
        fila = {"campana": camp}
        for s, lab in zip(semanas, labels):
            fila[lab] = valor(sub, s)
        fila["Total"] = total(sub_df)
        filas.append(fila)
    fila_t = {"campana": "TOTAL"}
    for s, lab in zip(semanas, labels):
        fila_t[lab] = total(base[base["semana"] == s])
    fila_t["Total"] = total(base)
    df = pd.concat([pd.DataFrame(filas), pd.DataFrame([fila_t])], ignore_index=True)
    return {"df": df, "semanas": labels}


def _mapa_matriculas_campana(df_deals: pd.DataFrame | None) -> dict:
    """{campana normalizada: matrículas} desde los deals ganados."""
    mc = matriculas_por_campana(df_deals)
    return {_norm_campana(r["campana"]): int(r["matriculas"]) for _, r in mc.iterrows()} if not mc.empty else {}


def _mapa_ingresos_campana(df_deals: pd.DataFrame | None) -> dict:
    """{campana normalizada: ingresos €} desde los deals ganados."""
    ic = ingresos_por_campana(df_deals)
    return {_norm_campana(r["campana"]): float(r["ingresos"]) for _, r in ic.iterrows()} if not ic.empty else {}


def enriquecer_campanas_con_hubspot(camp: pd.DataFrame, df_leads: pd.DataFrame,
                                    df_deals: pd.DataFrame | None = None) -> pd.DataFrame:
    """Añade `leads` (contactos de HubSpot) y `matriculas` (deals GANADOS) a una
    tabla de campañas de ads, casando por nombre de campaña normalizado.

    Importante: las matrículas se cuentan por **deal ganado** (no por contactos con
    lifecyclestage=cliente), para no duplicar ni atribuir mal la matrícula real."""
    if camp is None or camp.empty:
        return camp
    camp = camp.copy()
    leads_map = {}
    if df_leads is not None and not df_leads.empty and "campana" in df_leads:
        g = df_leads.copy()
        g["k"] = g["campana"].map(_norm_campana)
        leads_map = {k: int(v) for k, v in g.groupby("k")["lead_id"].count().items()}
    mat_map = _mapa_matriculas_campana(df_deals)
    ing_map = _mapa_ingresos_campana(df_deals)
    camp["leads"] = camp["campana"].map(lambda c: leads_map.get(_norm_campana(c), 0))
    camp["matriculas"] = camp["campana"].map(lambda c: mat_map.get(_norm_campana(c), 0))
    camp["ingresos"] = camp["campana"].map(lambda c: ing_map.get(_norm_campana(c), 0.0))
    return camp


def reconciliar_leads_canal(camp: pd.DataFrame, df_leads: pd.DataFrame,
                            df_deals: pd.DataFrame | None, canal: str) -> pd.DataFrame:
    """Añade una fila '(Sin campaña)' con los leads (y matrículas) del CANAL que no
    casaron con ninguna campaña, para que el total cuadre con el total del canal."""
    if camp is None or camp.empty or df_leads is None or df_leads.empty:
        return camp
    n_canal = int((df_leads["fuente"] == canal).sum())
    m_canal = matriculas_canal(df_deals, canal)  # matrículas = deals ganados del canal
    ing_map = ingresos_por_programa(df_deals if df_deals is not None else pd.DataFrame())
    i_canal = float(ing_map.loc[ing_map["programa"] == canal, "ingresos"].sum()) if not ing_map.empty else 0.0
    resto = n_canal - int(camp["leads"].sum())
    resto_m = m_canal - int(camp["matriculas"].sum())
    resto_i = i_canal - float(camp["ingresos"].sum()) if "ingresos" in camp else 0.0
    if resto <= 0 and resto_m <= 0 and resto_i <= 0:
        return camp
    # Columnas de texto (estado, programa…) a "" y numéricas a 0.
    fila = {c: ("" if not pd.api.types.is_numeric_dtype(camp[c]) else 0)
            for c in camp.columns}
    fila["campana"] = "(Sin campaña)"
    fila["leads"] = max(resto, 0)
    fila["matriculas"] = max(resto_m, 0)
    if "ingresos" in camp:
        fila["ingresos"] = max(resto_i, 0.0)
    return pd.concat([camp, pd.DataFrame([fila])], ignore_index=True)


def leads_por_campana(df_leads: pd.DataFrame,
                      df_deals: pd.DataFrame | None = None) -> pd.DataFrame:
    """Leads (contactos) por campaña + matrículas (deals GANADOS) por campaña."""
    if df_leads is None or df_leads.empty or "campana" not in df_leads:
        return pd.DataFrame()
    g = df_leads.groupby("campana", as_index=False).agg(leads=("lead_id", "count"))
    mc = matriculas_por_campana(df_deals)
    if not mc.empty:
        g = g.merge(mc, on="campana", how="outer")
    if "matriculas" not in g:
        g["matriculas"] = 0
    g["leads"] = g["leads"].fillna(0).astype(int)
    g["matriculas"] = g["matriculas"].fillna(0).astype(int)
    return g.sort_values("leads", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# "Quién está entrando" — rankings de país, especialidad y motivo de pérdida
# --------------------------------------------------------------------------- #
def _ranking(serie: pd.Series, etiqueta: str, valor: str, top: int) -> pd.DataFrame:
    """value_counts -> DataFrame [etiqueta, valor] ordenado desc, top N."""
    vc = serie.value_counts()
    if vc.empty:
        return pd.DataFrame(columns=[etiqueta, valor])
    out = vc.head(top).reset_index()
    out.columns = [etiqueta, valor]
    return out


def _visitas_geo(ga4_extra: dict, clave: str, dim: str, top: int) -> pd.DataFrame:
    """Sesiones por dimensión geográfica (país/región/ciudad) desde ga4_extra."""
    if not ga4_extra:
        return pd.DataFrame(columns=[dim, "sesiones"])
    df = ga4_extra.get(clave)
    if df is None or df.empty or dim not in df:
        return pd.DataFrame(columns=[dim, "sesiones"])
    return df.sort_values("sesiones", ascending=False).head(top)[[dim, "sesiones"]]


def visitas_por_pais(ga4_extra: dict, top: int = 15) -> pd.DataFrame:
    """Sesiones por país (GA4). Devuelve [pais, sesiones]."""
    return _visitas_geo(ga4_extra, "paises", "pais", top)


def visitas_por_region(ga4_extra: dict, top: int = 15) -> pd.DataFrame:
    """Sesiones por región/comunidad (GA4). Devuelve [region, sesiones]."""
    return _visitas_geo(ga4_extra, "regiones", "region", top)


def visitas_por_ciudad(ga4_extra: dict, top: int = 15) -> pd.DataFrame:
    """Sesiones por ciudad (GA4). Devuelve [ciudad, sesiones]."""
    return _visitas_geo(ga4_extra, "ciudades", "ciudad", top)


def leads_por_pais(df_leads: pd.DataFrame, top: int = 8) -> pd.DataFrame:
    """Nº de leads (contactos) por país DECLARADO. Devuelve [pais, leads]."""
    if df_leads is None or df_leads.empty or "pais" not in df_leads:
        return pd.DataFrame(columns=["pais", "leads"])
    s = df_leads[df_leads["pais"] != "Sin país"]["pais"]
    return _ranking(s, "pais", "leads", top)


def especialidades_leads(df_leads: pd.DataFrame, top: int = 30) -> pd.DataFrame:
    """Nº de leads por especialidad (profesion). Devuelve [especialidad, leads]."""
    if df_leads is None or df_leads.empty or "especialidad" not in df_leads:
        return pd.DataFrame(columns=["especialidad", "leads"])
    s = df_leads[df_leads["especialidad"] != "Sin especificar"]["especialidad"]
    return _ranking(s, "especialidad", "leads", top)


def motivos_cierre_perdido(df_deals: pd.DataFrame, top: int = 20) -> pd.DataFrame:
    """Nº de deals perdidos por motivo (closed_lost_reason). Devuelve [motivo, deals]."""
    if df_deals is None or df_deals.empty or "es_perdido" not in df_deals:
        return pd.DataFrame(columns=["motivo", "deals"])
    perdidos = df_deals[df_deals["es_perdido"] == True]  # noqa: E712
    if perdidos.empty:
        return pd.DataFrame(columns=["motivo", "deals"])
    col = "motivo_perdido" if "motivo_perdido" in perdidos else None
    if col is None:
        return pd.DataFrame(columns=["motivo", "deals"])
    return _ranking(perdidos[col], "motivo", "deals", top)
