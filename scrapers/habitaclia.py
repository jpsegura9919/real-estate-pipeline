"""
habitaclia.py
Scraper de Habitaclia para viviendas en Sevilla usando Playwright.
"""

import os
import re
import time
import random
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class HabitacliaScraper(BaseScraper):
    source = "habitaclia"
    urls = {
        # Desde sept. 2026 Habitaclia usa la misma plataforma web que Fotocasa
        "venta": "https://www.habitaclia.com/comprar/viviendas/sevilla-provincia/sevilla-capital/s",
        "alquiler": "https://www.habitaclia.com/alquiler/viviendas/sevilla-provincia/sevilla-capital/s",
    }

    def scrape(self, operation: str, max_pages: int) -> list[dict]:
        base_url = self.urls[operation]
        all_listings = []
        headless = os.getenv("HEADLESS", "false").lower() == "true"

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                locale="es-ES",
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            # Aceptar cookies en primera visita
            try:
                page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
                for selector in ["button:has-text('Aceptar')", "button:has-text('ACEPTO')", "#didomi-notice-agree-button"]:
                    btn = page.query_selector(selector)
                    if btn:
                        btn.click()
                        time.sleep(2)
                        break
            except Exception:
                pass

            for page_num in range(1, max_pages + 1):
                print(f"     Página {page_num}/{max_pages}...")
                # Paginación: .../sevilla-capital/s/2, /s/3...
                paginated_url = f"{base_url}/{page_num}" if page_num > 1 else base_url

                try:
                    page.goto(paginated_url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(3)
                    try:
                        page.wait_for_selector("article", timeout=15000)
                    except Exception:
                        pass
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(random.uniform(2, 3))
                    html = page.content()
                except Exception as e:
                    print(f"     ⚠️  Error: {e}")
                    break

                soup = BeautifulSoup(html, "html.parser")
                articles = soup.find_all("article", {"data-panot-component": "link-box"})
                if not articles:
                    print(f"     ⚠️  Sin artículos en página {page_num}, parando.")
                    break

                for article in articles:
                    listing = self._parse_article(article, operation)
                    if listing and listing["price"]:
                        all_listings.append(listing)

                time.sleep(random.uniform(2, 3))

            browser.close()

        return all_listings

    def _parse_article(self, article, operation: str) -> dict | None:
        """
        Extrae los datos de un anuncio con el formato nuevo de Habitaclia.
        El texto del anuncio llega como bloques separados, por ejemplo:
        "360.000 € | Piso ... en venta en Macarena | Sevilla Capital, Sevilla | 83 m² | 3 hab. | 2 baños | 1º"
        """
        try:
            parts = [t.strip() for t in article.get_text("|", strip=True).split("|") if t.strip()]

            price = size = rooms = baths = floor = zone = None
            for t in parts:
                t_clean = t.replace("\xa0", " ")
                if price is None and "€" in t_clean and "/m²" not in t_clean and "/m2" not in t_clean:
                    digits = re.sub(r"[^\d]", "", t_clean.split("€")[0])
                    if digits and int(digits) >= 100:
                        price = int(digits)
                elif size is None and re.fullmatch(r"\d+\s*m²", t_clean):
                    size = int(re.match(r"\d+", t_clean).group())
                elif rooms is None and re.fullmatch(r"\d+\s*hab\.?", t_clean, re.IGNORECASE):
                    rooms = int(re.match(r"\d+", t_clean).group())
                elif baths is None and re.fullmatch(r"\d+\s*baños?", t_clean, re.IGNORECASE):
                    baths = int(re.match(r"\d+", t_clean).group())
                elif floor is None and re.fullmatch(r"(\d+º|Bajo|Entreplanta|Sótano)", t_clean, re.IGNORECASE):
                    floor = t_clean
                elif zone is None and "," in t_clean and "Sevilla" in t_clean and " en " not in t_clean:
                    first = t_clean.split(",")[0].strip()
                    if first.lower() != "sevilla capital":
                        zone = first

            # URL y, si hace falta, barrio a partir de ella:
            # /comprar/<tipo>/.../<barrio>/sevilla-capital/<id>/d
            url = None
            link = article.find("a", {"data-panot-component": "link-box-link"})
            href = link.get("href") if link else None
            if href:
                url = href if href.startswith("http") else f"https://www.habitaclia.com{href}"
                if zone is None:
                    segs = [x for x in href.split("/") if x]
                    if "sevilla-capital" in segs:
                        i = segs.index("sevilla-capital")
                        if i > 0:
                            zone = segs[i - 1].replace("-", " ").title()

            return self.build_listing(
                operation=operation,
                zone=zone,
                price=price,
                size_m2=size,
                rooms=rooms,
                bathrooms=baths,
                floor=floor,
                url=url,
            )

        except Exception as e:
            print(f"     ⚠️  Error parseando: {e}")
            return None
