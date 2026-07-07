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
        "venta": "https://www.habitaclia.com/viviendas-sevilla.htm",
        "alquiler": "https://www.habitaclia.com/alquiler-sevilla.htm",
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
                # Habitaclia usa "-N.htm" para paginar (viviendas-sevilla-2.htm)
                if page_num > 1:
                    paginated_url = base_url.replace(".htm", f"-{page_num}.htm")
                else:
                    paginated_url = base_url

                try:
                    page.goto(paginated_url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(3)
                    try:
                        page.wait_for_selector("article.js-list-item", timeout=15000)
                    except Exception:
                        pass
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(random.uniform(2, 3))
                    html = page.content()
                except Exception as e:
                    print(f"     ⚠️  Error: {e}")
                    break

                soup = BeautifulSoup(html, "html.parser")
                articles = soup.find_all("article", class_=lambda c: c and "js-list-item" in c)
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
        try:
            # URL — del enlace dentro de list-item-title
            url = None
            title_a = article.find("h3", class_="list-item-title")
            if title_a:
                link = title_a.find("a")
                if link and link.get("href"):
                    url = link["href"]

            # Zona — <p class="list-item-location"><span>Sevilla - Palmas Altas</span></p>
            zone = None
            zone_p = article.find("p", class_="list-item-location")
            if zone_p:
                zone_text = zone_p.get_text(" ", strip=True)
                # Ejemplo: "Sevilla - Palmas Altas"
                if " - " in zone_text:
                    zone = zone_text.split(" - ", 1)[1].strip()
                elif "-" in zone_text:
                    zone = zone_text.split("-", 1)[1].strip()
                else:
                    zone = zone_text.strip()

            # Características — <p class="list-item-feature">
            # Ejemplo: "246m2 - 4 habitaciones - 2 baños - 2.382€/m2"
            # OJO: los superindices <sup>2</sup> se convierten en "2" al usar get_text
            rooms = baths = size = None
            feature_p = article.find("p", class_="list-item-feature")
            if feature_p:
                text = feature_p.get_text(" ", strip=True)
                # m² puede aparecer como "m²", "m2" o "m 2" según el navegador
                m = re.search(r"(\d+)\s*m\s*[²2]", text)
                if m:
                    size = int(m.group(1))
                m = re.search(r"(\d+)\s*habitacion", text, re.IGNORECASE)
                if m:
                    rooms = int(m.group(1))
                m = re.search(r"(\d+)\s*ba[ñn]", text, re.IGNORECASE)
                if m:
                    baths = int(m.group(1))

            # Precio — <span itemprop="price">586.000 €</span>
            price = None
            price_span = article.find("span", {"itemprop": "price"})
            if price_span:
                price_text = price_span.get_text(strip=True)
                # Puede venir con formato "586.000 €" o "586.000€"
                price_clean = re.sub(r"[^\d]", "", price_text.split("€")[0])
                if price_clean:
                    try:
                        price = int(price_clean)
                    except ValueError:
                        pass

            # Fallback: buscar en atributo data-pvp del botón "Avísame si baja"
            if not price:
                notify_btn = article.find("button", class_=lambda c: c and "js-notify" in c)
                if notify_btn and notify_btn.get("data-pvp"):
                    try:
                        price = int(notify_btn["data-pvp"])
                    except (ValueError, TypeError):
                        pass

            return self.build_listing(
                operation=operation,
                zone=zone,
                price=price,
                size_m2=size,
                rooms=rooms,
                bathrooms=baths,
                url=url,
            )

        except Exception as e:
            print(f"     ⚠️  Error parseando: {e}")
            return None
