"""
transform.py
Limpieza, enriquecimiento y deduplicación de anuncios cross-portal.
"""

import re
import unicodedata
import pandas as pd


def normalize_zone(zone: str) -> str:
    """Normaliza el nombre de una zona: minúsculas, sin tildes, sin espacios extra."""
    if not isinstance(zone, str):
        return ""
    # Quitar tildes
    nfkd = unicodedata.normalize("NFKD", zone)
    clean = "".join(c for c in nfkd if not unicodedata.combining(c))
    return clean.lower().strip()


def make_fingerprint(row) -> str | None:
    """
    Genera un identificador único de la vivienda basado en sus características.
    Anuncios del mismo piso en diferentes portales generarán el mismo fingerprint.

    Se usa el DISTRITO y no el barrio: Fotocasa publica el barrio ("Cruz Roja")
    y Habitaclia solo el distrito ("Macarena"), así que el barrio nunca coincide.
    """
    area = row.get("district") if isinstance(row.get("district"), str) else row.get("zone")
    if not all([area, row.get("operation"), row.get("size_m2"), row.get("price")]):
        return None

    zone_norm = re.sub(r"[^a-z0-9]", "", normalize_zone(area))
    # Buckets con tolerancia para absorber variaciones entre portales
    size_bucket = round(row["size_m2"] / 5) * 5
    price_bucket = round(row["price"] / 1000) * 1000
    rooms = row.get("rooms") or 0
    baths = row.get("bathrooms") or 0

    return f"{row['operation']}|{zone_norm}|{rooms}|{baths}|{size_bucket}|{price_bucket}"


def clean_listings(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia el DataFrame de anuncios."""
    df = df.copy()
    before = len(df)
    df = df.dropna(subset=["price", "size_m2"])
    print(f"  🧹 Eliminados {before - len(df)} anuncios sin precio o m².")

    # Filtrar outliers por operación
    for operation in df["operation"].unique():
        mask = df["operation"] == operation
        q_low = df.loc[mask, "price"].quantile(0.01)
        q_high = df.loc[mask, "price"].quantile(0.99)
        df = df[~(mask & ((df["price"] < q_low) | (df["price"] > q_high)))]

    df = df[(df["size_m2"] >= 20) & (df["size_m2"] <= 1000)]
    df["price_per_m2"] = (df["price"] / df["size_m2"]).round(2)

    # Categorización por tamaño
    df["size_category"] = pd.cut(
        df["size_m2"],
        bins=[0, 50, 70, 90, 120, float("inf")],
        labels=["Estudio/1H", "2H pequeño", "2H grande", "3H", "4H+"]
    )

    # Zona normalizada y limpia
    df["zone"] = df["zone"].fillna("Sin zona").str.strip()
    if "district" not in df.columns:
        df["district"] = None

    # Completar el distrito que falte a partir de otros anuncios del mismo barrio
    # (Fotocasa suele publicar "Barrio, Distrito", lo que sirve de tabla de equivalencias)
    known = (
        df.dropna(subset=["district"])
        .groupby("zone")["district"]
        .agg(lambda s: s.mode().iloc[0])
    )
    df["district"] = df["district"].where(df["district"].notna(), df["zone"].map(known))

    # Fingerprint
    df["fingerprint"] = df.apply(make_fingerprint, axis=1) if not df.empty else pd.Series(dtype=object)

    print(f"  ✅ {len(df)} anuncios limpios con fingerprint.")
    return df


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Elimina duplicados cross-portal basándose en el fingerprint.
    Mantiene el anuncio con más datos completos (menos nulos).
    """
    df = df.copy()
    before = len(df)

    # Contar campos no nulos por fila (para priorizar los más completos)
    df["_completeness"] = df.notna().sum(axis=1)

    # Ordenar por completitud descendente y mantener el primero por fingerprint
    df = df.sort_values("_completeness", ascending=False)
    df_dedup = df.drop_duplicates(subset=["fingerprint"], keep="first")
    df_dedup = df_dedup.drop(columns=["_completeness"])

    duplicates = before - len(df_dedup)
    print(f"  🔀 Eliminados {duplicates} duplicados cross-portal ({duplicates/before*100:.1f}%).")
    return df_dedup


def calculate_market_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Resumen agregado por operación y zona."""
    summary = df.groupby(["date", "operation", "zone"]).agg(
        avg_price=("price", "mean"),
        median_price=("price", "median"),
        avg_price_m2=("price_per_m2", "mean"),
        avg_size=("size_m2", "mean"),
        total_listings=("price", "count"),
    ).reset_index()

    for col in ["avg_price", "median_price", "avg_price_m2", "avg_size"]:
        summary[col] = summary[col].round(2)

    print(f"  ✅ Resumen de mercado: {len(summary)} filas.")
    return summary
