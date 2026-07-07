"""
base.py
Clase base común para todos los scrapers de portales inmobiliarios.
Cada portal específico (Fotocasa, Habitaclia, etc.) hereda de aquí.
"""

from abc import ABC, abstractmethod
from datetime import date
import pandas as pd


class BaseScraper(ABC):
    """Interfaz común para todos los scrapers de portales inmobiliarios."""

    # Identificador del portal (fotocasa, habitaclia, etc.)
    source: str = ""

    # URLs base por operación
    urls: dict = {}

    @abstractmethod
    def scrape(self, operation: str, max_pages: int) -> list[dict]:
        """
        Debe implementarse en cada scraper.
        Extrae los anuncios de una operación específica (venta/alquiler).
        """
        pass

    def build_listing(
        self,
        operation: str,
        zone: str | None,
        price: int | None,
        size_m2: int | None,
        rooms: int | None,
        bathrooms: int | None,
        floor: str | None = None,
        extras: list | None = None,
        url: str | None = None,
    ) -> dict:
        """Devuelve un diccionario con la estructura estándar de anuncio."""
        price_per_m2 = round(price / size_m2, 2) if price and size_m2 else None
        return {
            "date": date.today(),
            "source": self.source,
            "operation": operation,
            "zone": zone,
            "price": price,
            "size_m2": size_m2,
            "rooms": rooms,
            "bathrooms": bathrooms,
            "floor": floor,
            "extras": ", ".join(extras) if extras else None,
            "price_per_m2": price_per_m2,
            "url": url,
        }

    def run(self, max_pages: int = 5) -> pd.DataFrame:
        """Ejecuta el scraping de todas las operaciones (venta + alquiler)."""
        all_listings = []
        for operation in self.urls.keys():
            print(f"\n  🏠 [{self.source.upper()}] Scrapeando {operation}...")
            listings = self.scrape(operation, max_pages)
            all_listings.extend(listings)
            print(f"     ✅ {len(listings)} anuncios de {operation}.")

        if not all_listings:
            return pd.DataFrame()

        return pd.DataFrame(all_listings)
