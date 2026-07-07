"""
main.py
Orquesta el pipeline completo de scraping inmobiliario multiportal.
"""

import sys
import traceback
import pandas as pd
from datetime import datetime

from scrapers.fotocasa import FotocasaScraper
from scrapers.habitaclia import HabitacliaScraper
from etl.transform import clean_listings, deduplicate, calculate_market_summary
from etl.load import get_engine, create_tables, load_listings, load_market_summary


# Scrapers registrados en el pipeline
SCRAPERS = [
    FotocasaScraper(),
    HabitacliaScraper(),
]


def run_pipeline():
    start_time = datetime.now()
    print(f"\n{'='*55}")
    print(f"🏠 Real Estate Pipeline iniciada: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}\n")

    try:
        # 1. EXTRACT — todos los scrapers
        print(f"📥 [1/3] Scrapeando {len(SCRAPERS)} portales...")
        all_frames = []
        for scraper in SCRAPERS:
            df = scraper.run(max_pages=5)
            if not df.empty:
                all_frames.append(df)

        if not all_frames:
            raise ValueError("Ningún scraper devolvió datos.")

        raw_df = pd.concat(all_frames, ignore_index=True)
        print(f"\n  ✅ Total combinado: {len(raw_df)} anuncios de {len(all_frames)} portales.")
        print(f"     Desglose: {raw_df['source'].value_counts().to_dict()}")

        # 2. TRANSFORM
        print("\n⚙️  [2/3] Limpiando, calculando fingerprint y deduplicando...")
        clean_df = clean_listings(raw_df)
        dedup_df = deduplicate(clean_df)
        summary_df = calculate_market_summary(dedup_df)

        # 3. LOAD
        print("\n💾 [3/3] Cargando datos en PostgreSQL...")
        engine = get_engine()
        create_tables(engine)
        load_listings(clean_df, engine, table="listings")
        load_listings(dedup_df, engine, table="listings_deduplicated")
        load_market_summary(summary_df, engine)

    except Exception as e:
        print(f"\n❌ Error en la pipeline: {e}")
        traceback.print_exc()
        sys.exit(1)

    elapsed = (datetime.now() - start_time).seconds
    print(f"\n{'='*55}")
    print(f"✅ Pipeline completada en {elapsed}s")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    run_pipeline()
