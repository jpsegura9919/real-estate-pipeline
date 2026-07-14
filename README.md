# 🏠 Real Estate Multi-Portal Pipeline

Pipeline de datos inmobiliarios multiportal con **deduplicación cross-portal** para el mercado de Sevilla. Integra Fotocasa y Habitaclia mediante scraping automatizado y detecta anuncios duplicados entre portales.

## 🎯 Objetivo

Ofrecer una visión completa y limpia del mercado inmobiliario sevillano combinando varios portales, evitando el sesgo que supone consultar uno solo. Demuestra un caso de uso realista de ingeniería de datos: extracción, transformación, deduplicación y visualización.

## 🏗️ Arquitectura

```
Fotocasa                 Habitaclia
    ↓                        ↓
Playwright + BeautifulSoup (scraping)
    ↓
Normalización + Fingerprint (deduplicación)
    ↓
PostgreSQL (Neon Cloud)
    ↓
Programador de tareas Windows (ejecución semanal)
    ↓
Power BI Service (dashboard con refresco automático)
```

## 🛠️ Stack tecnológico

| Capa | Tecnología |
|---|---|
| Scraping | Python · Playwright · BeautifulSoup |
| Transformación | pandas · deduplicación por fingerprint |
| Almacenamiento | PostgreSQL · Neon |
| Orquestación | Programador de tareas de Windows |
| Visualización | Power BI Service |

## 🧬 Deduplicación por fingerprint

Un mismo piso puede publicarse en varios portales con pequeñas variaciones. El sistema genera un identificador único combinando características normalizadas:

```python
fingerprint = f"{operation}|{zone_norm}|{rooms}|{bathrooms}|{size_bucket}|{price_bucket}"
```

Aplica tolerancias para absorber variaciones:
- **Zona:** normalizada (sin tildes, minúsculas)
- **Superficie:** buckets de ±5 m²
- **Precio:** buckets de ±1.000 €

**Resultado observado en producción:** ~12% de duplicados detectados entre Fotocasa y Habitaclia.

## 📁 Estructura del proyecto

```
📁 real-estate-pipeline/
├── 📁 scrapers/
│   ├── base.py             # Clase base abstracta común
│   ├── fotocasa.py         # Scraper Fotocasa
│   └── habitaclia.py       # Scraper Habitaclia
├── 📁 etl/
│   ├── transform.py        # Limpieza + fingerprint + deduplicación
│   └── load.py             # Carga en PostgreSQL
├── main.py                 # Orquestador ETL completo
└── requirements.txt
```

La arquitectura permite añadir nuevos portales creando una clase que herede de `BaseScraper`.

## 📊 Modelo de datos

Tres tablas en PostgreSQL:

- **`listings`** — todos los anuncios extraídos con su origen (`source`)
- **`listings_deduplicated`** — anuncios únicos tras deduplicación cross-portal
- **`market_summary`** — agregado por zona, operación y fecha

## 🚀 Ejecutar en local

```bash
# 1. Clonar
git clone https://github.com/jpsegura9919/real-estate-pipeline.git
cd real-estate-pipeline

# 2. Instalar dependencias
pip install -r requirements.txt
python -m playwright install chromium

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con tu DATABASE_URL de PostgreSQL

# 4. Ejecutar la pipeline
python main.py
```

## 📊 Dashboard

[🔗 Ver dashboard en Power BI →](https://app.powerbi.com/view?r=eyJrIjoiMTYwNGQ2NjUtODBlOS00N2JjLWJhMzctMmZiOWFhNjI0YWU1IiwidCI6IjQ3ZTNjY2NhLTFkZTgtNDJlNi1hOTI3LTU5N2UyNTI0YThmZSJ9)

El dashboard incluye:

- **Resumen** — KPIs del mercado, rentabilidad bruta, distribución por tamaño
- **Comparativa venta vs alquiler** — precio por m² separado por operación y rentabilidad por barrio
- **Comparativa entre portales** — análisis del sesgo entre Fotocasa y Habitaclia

## 🧭 Cobertura

- **Ciudad:** Sevilla (viviendas de venta y alquiler)
- **Portales:** Fotocasa · Habitaclia
- **Frecuencia:** semanal (todos los lunes)

---

*Proyecto desarrollado como parte de un portfolio de Data Engineering & Analytics.*
