"""
fotocasa.py
Scraper de Fotocasa para viviendas en Sevilla usando Playwright.
"""

import os
import re
import time
import random
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class FotocasaScraper(BaseScraper):
    source = "fotocasa"
    site_root = "https://www.fotocasa.es"
    urls = {
        "venta": "https://www.fotocasa.es/es/comprar/viviendas/sevilla-capital/todas-las-zonas/l",
        "alquiler": "https://www.fotocasa.es/es/alquiler/viviendas/sevilla-capital/todas-las-zonas/l",
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

            # Bloquear publicidad que interrumpe navegación
            page.route("**/*doubleclick*", lambda route: route.abort())
            page.route("**/*googleads*", lambda route: route.abort())
            page.route("**/*googlesyndication*", lambda route: route.abort())

            # Aceptar cookies en primera visita
            try:
                page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
                for selector in ["button[data-testid='TcfAccept']", "button:has-text('Aceptar')"]:
                    btn = page.query_selector(selector)
                    if btn:
                        btn.click()
                        time.sleep(2)
                        break
            except Exception:
                pass

            for page_num in range(1, max_pages + 1):
                print(f"     Página {page_num}/{max_pages}...")
                paginated_url = f"{base_url}/{page_num}" if page_num > 1 else base_url
                try:
                    page.goto(paginated_url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(4)
                    try:
                        page.wait_for_selector("article", timeout=20000)
                    except Exception:
                        pass
                    self.scroll_all_cards(page)
                    html = page.content()
                except Exception as e:
                    print(f"     ⚠️  Error: {e}")
                    break

                soup = BeautifulSoup(html, "html.parser")
                articles = soup.find_all("article")
                if not articles:
                    break

                for article in articles:
                    listing = self.parse_card(article, operation)
                    if listing and listing["price"]:
                        all_listings.append(listing)

                time.sleep(random.uniform(2, 3))

            browser.close()

        return all_listings
