"""
overlap_check.py  (temporal, se puede borrar al terminar)
Mide cuántos anuncios comparten Fotocasa y Habitaclia. No escribe en la base de datos.
"""
import pandas as pd
from scrapers.fotocasa import FotocasaScraper
from scrapers.habitaclia import HabitacliaScraper
from etl.transform import make_fingerprint

PAGES = 3

def ad_id(url):
    if not isinstance(url, str):
        return None
    segs = [s for s in url.split("/") if s]
    return segs[-2] if len(segs) >= 2 and segs[-1] == "d" else segs[-1]

frames = []
for scraper in (FotocasaScraper(), HabitacliaScraper()):
    for op in ("venta", "alquiler"):
        print(f"[{scraper.source}] {op}...")
        rows = scraper.scrape(op, PAGES)
        frames.append(pd.DataFrame(rows))

df = pd.concat(frames, ignore_index=True)
df = df.dropna(subset=["price", "size_m2"])
df["ad_id"] = df["url"].map(ad_id)
df["loose_key"] = df.apply(lambda r: f"{r.operation}|{int(r.price)}|{int(r.size_m2)}|{r.rooms}|{r.bathrooms}", axis=1)
df["fingerprint"] = df.apply(make_fingerprint, axis=1)
df.to_csv("overlap_check.csv", index=False, encoding="utf-8")

fc = df[df.source == "fotocasa"]
hb = df[df.source == "habitaclia"]

def report(col, label):
    a, b = set(fc[col].dropna()), set(hb[col].dropna())
    inter = a & b
    print(f"\n{label}")
    print(f"  Fotocasa: {len(a)} | Habitaclia: {len(b)} | En ambos: {len(inter)}")
    if a: print(f"  % de Fotocasa que también está en Habitaclia: {len(inter)/len(a)*100:.0f}%")
    if b: print(f"  % de Habitaclia que también está en Fotocasa: {len(inter)/len(b)*100:.0f}%")

print("\n================ RESULTADOS ================")
print(df.groupby(["source", "operation"]).size().to_string())
report("ad_id", "1) Mismo identificador de anuncio")
report("loose_key", "2) Mismas características (sin barrio)")
report("fingerprint", "3) Fingerprint actual de la pipeline")
print("\nDetalle guardado en overlap_check.csv")
