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
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    time.sleep(random.uniform(2, 3))
                    html = page.content()
                except Exception as e:
                    print(f"     ⚠️  Error: {e}")
                    break

                soup = BeautifulSoup(html, "html.parser")
                articles = soup.find_all("article")
                if not articles:
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
            # Precio
            price = None
            price_container = article.find("div", class_=lambda c: c and "text-display-3" in c)
            if price_container:
                price_span = price_container.find("span")
                if price_span:
                    price_text = price_span.get_text(strip=True)
                    price_clean = re.sub(r"[^\d]", "", price_text.split("€")[0])
                    price = int(price_clean) if price_clean else None

            # Características
            rooms = baths = size = floor = None
            extras = []
            features_ul = article.find("ul", class_=lambda c: c and "list-none" in c and "line-clamp" in c)
            if features_ul:
                for li in features_ul.find_all("li"):
                    text = li.get_text(strip=True).replace("\xa0", " ")
                    if "hab" in text.lower():
                        m = re.search(r"(\d+)", text)
                        if m: rooms = int(m.group(1))
                    elif "baño" in text.lower():
                        m = re.search(r"(\d+)", text)
                        if m: baths = int(m.group(1))
                    elif "m²" in text:
                        m = re.search(r"(\d+)", text)
                        if m: size = int(m.group(1))
                    elif "planta" in text.lower():
                        floor = text.replace("·", "").strip()
                    else:
                        kw = text.replace("·", "").strip()
                        if kw: extras.append(kw)

            # Zona
            zone = None
            zone_p = article.find("p", class_=lambda c: c and "truncate" in c)
            if zone_p:
                zone_text = zone_p.get_text(strip=True)
                zone = zone_text.split(",")[0].strip()

            # URL
            link_tag = article.find("a", {"data-panot-component": "link-box-link"})
            url = f"https://www.fotocasa.es{link_tag['href']}" if link_tag and link_tag.get("href") else None

            return self.build_listing(
                operation=operation,
                zone=zone,
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
