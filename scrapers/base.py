"""
base.py
Clase base común para todos los scrapers de portales inmobiliarios.
Cada portal específico (Fotocasa, Habitaclia, etc.) hereda de aquí.

Desde septiembre de 2026 Fotocasa y Habitaclia usan la misma plataforma web,
así que el parseo de las tarjetas de anuncio es común y vive aquí.
"""

import re
import time
import unicodedata
from abc import ABC, abstractmethod
from datetime import date
import pandas as pd


# Los 11 distritos oficiales de Sevilla capital
SEVILLA_DISTRICTS = [
    "Casco Antiguo", "Macarena", "Nervión", "Cerro-Amate", "Sur", "Triana",
    "Norte", "San Pablo-Santa Justa", "Este-Alcosa-Torreblanca",
    "Bellavista-La Palmera", "Los Remedios",
]


def _key(text: str) -> str:
    """Clave de comparación: minúsculas, sin tildes ni signos ni espacios."""
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", no_accents.lower())


_DISTRICT_BY_KEY = {_key(d): d for d in SEVILLA_DISTRICTS}


def canonical_district(name: str | None) -> str | None:
    """Devuelve el nombre oficial del distrito, o None si no es un distrito conocido."""
    if not name:
        return None
    return _DISTRICT_BY_KEY.get(_key(name))


EXTRA_KEYWORDS = [
    "Ascensor", "Parking", "Garaje", "Terraza", "Balcón", "Piscina",
    "Jardín", "Trastero", "Aire acondicionado",
]


class BaseScraper(ABC):
    """Interfaz común para todos los scrapers de portales inmobiliarios."""

    # Identificador del portal (fotocasa, habitaclia, etc.)
    source: str = ""

    # Dominio del portal, para construir URLs absolutas
    site_root: str = ""

    # URLs base por operación
    urls: dict = {}

    @abstractmethod
    def scrape(self, operation: str, max_pages: int) -> list[dict]:
        """
        Debe implementarse en cada scraper.
        Extrae los anuncios de una operación específica (venta/alquiler).
        """
        pass

    @staticmethod
    def scroll_all_cards(page) -> None:
        """
        Las tarjetas de anuncio solo cargan sus datos cuando pasan por pantalla.
        Recorremos cada tarjeta para que todas se rendericen antes de leer el HTML.
        """
        cards = page.locator("article")
        for i in range(cards.count()):
            try:
                cards.nth(i).scroll_into_view_if_needed(timeout=2000)
                time.sleep(0.25)
            except Exception:
                pass
        time.sleep(1.5)

    def parse_card(self, article, operation: str) -> dict | None:
        """
        Extrae los datos de una tarjeta de anuncio leyendo su texto por bloques.
        Ejemplos de bloques:
          Fotocasa:   "360.000 €" | "Cruz Roja, Macarena" | "3 habs" | "2 baños" | "83 m²" | "1ª Planta"
          Habitaclia: "950 €/mes" | "Triana, Sevilla Capital" | "75 m²" | "2 hab." | "1 baño" | "3º"
        """
        try:
            parts = [t.replace("\xa0", " ").strip()
                     for t in article.get_text("|", strip=True).split("|")]
            parts = [t for t in parts if t]
            if not parts:
                return None

            price = size = rooms = baths = floor = None
            barrio = district = None

            for t in parts:
                low = t.lower()
                if (price is None and "€" in t and "/m²" not in t and "/m2" not in t
                        and "bajado" not in low and "subido" not in low):
                    digits = re.sub(r"[^\d]", "", t.split("€")[0])
                    if digits and int(digits) >= 100:
                        price = int(digits)
                elif size is None and re.fullmatch(r"\d+\s*m²", t):
                    size = int(re.match(r"\d+", t).group())
                elif rooms is None and re.fullmatch(r"\d+\s*habs?\.?", t, re.IGNORECASE):
                    rooms = int(re.match(r"\d+", t).group())
                elif baths is None and re.fullmatch(r"\d+\s*baños?", t, re.IGNORECASE):
                    baths = int(re.match(r"\d+", t).group())
                elif floor is None and re.fullmatch(
                        r"(\d+\s*[ºª](\s*planta)?|bajo|entreplanta|sótano)", t, re.IGNORECASE):
                    floor = t
                elif (district is None and "," in t and not low.startswith("en ")
                        and " en " not in low and len(t) < 80):
                    a, b = [x.strip() for x in t.split(",", 1)]
                    if _key(b) in ("sevillacapital", "sevilla"):
                        # Habitaclia: "Distrito, Sevilla Capital"
                        # Fotocasa a veces: "Barrio, Sevilla Capital" (sin distrito)
                        if _key(a) not in ("sevillacapital", "sevilla"):
                            if canonical_district(a):
                                district = canonical_district(a)
                            else:
                                barrio = a
                    elif canonical_district(b):
                        # Fotocasa: "Barrio, Distrito"
                        barrio, district = a, canonical_district(b)

            extras = [k for k in EXTRA_KEYWORDS if any(k.lower() == p.lower() for p in parts)]

            # URL del anuncio y, si falta, distrito a partir de ella
            url = None
            link = article.find("a", {"data-panot-component": "link-box-link"})
            href = link.get("href") if link else None
            if href:
                url = href if href.startswith("http") else f"{self.site_root}{href}"
                if district is None:
                    segs = [x for x in href.split("/") if x]
                    if "sevilla-capital" in segs:
                        i = segs.index("sevilla-capital")
                        if i > 0:
                            district = canonical_district(segs[i - 1].replace("-", " "))

            return self.build_listing(
                operation=operation,
                zone=barrio or district,
                district=canonical_district(district) or district,
                price=price,
                size_m2=size,
                rooms=rooms,
                bathrooms=baths,
                floor=floor,
                extras=extras,
                url=url,
            )

        except Exception as e:
            print(f"     ⚠️  Error parseando: {e}")
            return None

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
        district: str | None = None,
    ) -> dict:
        """Devuelve un diccionario con la estructura estándar de anuncio."""
        price_per_m2 = round(price / size_m2, 2) if price and size_m2 else None
        return {
            "date": date.today(),
            "source": self.source,
            "operation": operation,
            "zone": zone,
            "district": district,
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
