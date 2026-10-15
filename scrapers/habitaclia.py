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
    site_root = "https://www.habitaclia.com"
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
                    self.scroll_all_cards(page)
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
                    listing = self.parse_card(article, operation)
                    if listing and listing["price"]:
                        all_listings.append(listing)

                time.sleep(random.uniform(2, 3))

            browser.close()

        return all_listings
