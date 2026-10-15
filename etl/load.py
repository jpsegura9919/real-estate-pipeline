"""
load.py
Carga los anuncios y el resumen de mercado en PostgreSQL (Neon).
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise EnvironmentError("❌ Variable DATABASE_URL no encontrada en .env")
    return create_engine(db_url)


def create_tables(engine):
    ddl = """
    CREATE TABLE IF NOT EXISTS listings (
        id              SERIAL PRIMARY KEY,
        date            DATE,
        source          VARCHAR(30),
        operation       VARCHAR(20),
        zone            VARCHAR(100),
        district        VARCHAR(50),
        price           NUMERIC(12,2),
        size_m2         NUMERIC(8,2),
        rooms           INTEGER,
        bathrooms       INTEGER,
        floor           VARCHAR(20),
        extras          TEXT,
        price_per_m2    NUMERIC(10,2),
        size_category   VARCHAR(30),
        fingerprint     VARCHAR(200),
        url             TEXT,
        UNIQUE (url, date)
    );

    CREATE TABLE IF NOT EXISTS listings_deduplicated (
        id              SERIAL PRIMARY KEY,
        date            DATE,
        source          VARCHAR(30),
        operation       VARCHAR(20),
        zone            VARCHAR(100),
        district        VARCHAR(50),
        price           NUMERIC(12,2),
        size_m2         NUMERIC(8,2),
        rooms           INTEGER,
        bathrooms       INTEGER,
        floor           VARCHAR(20),
        extras          TEXT,
        price_per_m2    NUMERIC(10,2),
        size_category   VARCHAR(30),
        fingerprint     VARCHAR(200),
        url             TEXT,
        UNIQUE (fingerprint, date)
    );

    ALTER TABLE listings ADD COLUMN IF NOT EXISTS district VARCHAR(50);
    ALTER TABLE listings_deduplicated ADD COLUMN IF NOT EXISTS district VARCHAR(50);

    CREATE TABLE IF NOT EXISTS market_summary (
        id              SERIAL PRIMARY KEY,
        date            DATE,
        operation       VARCHAR(20),
        zone            VARCHAR(100),
        avg_price       NUMERIC(12,2),
        median_price    NUMERIC(12,2),
        avg_price_m2    NUMERIC(10,2),
        avg_size        NUMERIC(8,2),
        total_listings  INTEGER,
        UNIQUE (date, operation, zone)
    );
    """
    with engine.connect() as conn:
        conn.execute(text(ddl))
        conn.commit()
    print("  ✅ Tablas verificadas / creadas.")


def load_listings(df: pd.DataFrame, engine, table: str = "listings"):
    """Upsert de anuncios en la tabla indicada."""
    records = df.astype(object).where(pd.notnull(df), None).to_dict(orient="records")

    if table == "listings":
        upsert_sql = text("""
            INSERT INTO listings 
                (date, source, operation, zone, district, price, size_m2, rooms, bathrooms, 
                 floor, extras, price_per_m2, size_category, fingerprint, url)
            VALUES 
                (:date, :source, :operation, :zone, :district, :price, :size_m2, :rooms, :bathrooms,
                 :floor, :extras, :price_per_m2, :size_category, :fingerprint, :url)
            ON CONFLICT (url, date) DO UPDATE SET
                price        = EXCLUDED.price,
                price_per_m2 = EXCLUDED.price_per_m2,
                fingerprint  = EXCLUDED.fingerprint
        """)
    else:  # listings_deduplicated
        upsert_sql = text("""
            INSERT INTO listings_deduplicated 
                (date, source, operation, zone, district, price, size_m2, rooms, bathrooms, 
                 floor, extras, price_per_m2, size_category, fingerprint, url)
            VALUES 
                (:date, :source, :operation, :zone, :district, :price, :size_m2, :rooms, :bathrooms,
                 :floor, :extras, :price_per_m2, :size_category, :fingerprint, :url)
            ON CONFLICT (fingerprint, date) DO UPDATE SET
                price        = EXCLUDED.price,
                price_per_m2 = EXCLUDED.price_per_m2
        """)

    with engine.connect() as conn:
        conn.execute(upsert_sql, records)
        conn.commit()
    print(f"  ✅ {table}: {len(records)} filas cargadas.")


def load_market_summary(df: pd.DataFrame, engine):
    records = df.to_dict(orient="records")
    upsert_sql = text("""
        INSERT INTO market_summary
            (date, operation, zone, avg_price, median_price, avg_price_m2, avg_size, total_listings)
        VALUES
            (:date, :operation, :zone, :avg_price, :median_price, :avg_price_m2, :avg_size, :total_listings)
        ON CONFLICT (date, operation, zone) DO UPDATE SET
            avg_price      = EXCLUDED.avg_price,
            median_price   = EXCLUDED.median_price,
            avg_price_m2   = EXCLUDED.avg_price_m2,
            avg_size       = EXCLUDED.avg_size,
            total_listings = EXCLUDED.total_listings
    """)
    with engine.connect() as conn:
        conn.execute(upsert_sql, records)
        conn.commit()
    print(f"  ✅ market_summary: {len(records)} filas cargadas.")
