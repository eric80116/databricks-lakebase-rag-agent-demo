# Sentiva Knowledge-Base Data Generation

This directory contains scripts to generate synthetic multilingual knowledge-base content for a RAG demo.

## Overview

Two generators produce realistic content for the fictional **Sentiva** brand (consumer digital safety company):
- **generate_docs.py** — Generates 84+ JSON knowledge-base documents in 4 languages (en, ja, fr, de)
- **generate_pdfs.py** — Generates 3 sample PDFs with tables for OCR extraction

## Setup

Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Generate JSON Documents

```bash
python generate_docs.py --out output/raw_json
```

Output: 84 JSON files (5 products × 4 languages × categories)
- Default output: `output/raw_json/`
- Each file named `{doc_id}.json` (e.g., `sentiva-shield-pricing-ja.json`)

**Coverage:**
- **Sentiva Shield**: overview, pricing, features, setup, privacy, troubleshooting (4 langs each = 24 docs)
- **Sentiva Alert**: overview, pricing, features (4 langs each = 12 docs)
- **Sentiva Family**: overview (4 langs = 4 docs)
- **Sentiva ID**: overview (4 langs = 4 docs)
- **Sentiva Scan**: overview (4 langs = 4 docs)

Plus additional setup/privacy/troubleshooting for Shield and Family in all 4 languages.

### Generate PDFs

```bash
python generate_pdfs.py --out output/raw_pdf
```

Output: 3 PDF files with embedded tables
- Default output: `output/raw_pdf/`
- Files:
  - `sentiva-shield-datasheet-en.pdf` — Product datasheet with specifications TABLE
  - `sentiva-plans-comparison-en.pdf` — Pricing/feature matrix TABLE across all 5 products
  - `sentiva-family-guide-ja.pdf` — Japanese setup guide with settings TABLE

## JSON Document Schema

Each JSON file follows this schema:

```json
{
  "doc_id": "sentiva-shield-pricing-ja",
  "product": "Sentiva Shield",
  "lang": "ja",
  "category": "pricing",
  "title": "…(in target language)…",
  "source_uri": "sentiva-kb://shield/pricing",
  "body": "…long-form content in target language (markdown ok)…",
  "faqs": [{"q": "…", "a": "…"}],
  "metadata": {
    "plan_tiers": ["Basic", "Plus", "Premium"],
    "supported_platforms": ["Windows", "macOS", "iOS", "Android"],
    "last_updated": "2026-08-15"
  }
}
```

## Products Covered

1. **Sentiva Shield** — Antivirus & multi-device security
2. **Sentiva Alert** — Scam & fraud detection
3. **Sentiva Family** — Family AI safety assistant
4. **Sentiva ID** — Identity & data protection
5. **Sentiva Scan** — Free online security check

## Languages

- **en** — English
- **ja** — Japanese
- **fr** — French
- **de** — German

## Content Quality

All content is authored inline in the generation scripts:
- Real, natural-sounding text (not machine translations)
- Realistic pricing (invented but plausible for consumer security)
- Concrete features and technical specs
- Practical setup/troubleshooting guidance
- Privacy & data-handling descriptions

## PDF Tables

PDFs include tables for downstream OCR/extraction:
- **Shield datasheet**: Feature matrix (plans × features)
- **Plans comparison**: Cross-product pricing & availability table
- **Family guide**: Configuration settings table

## Brand Compliance

All content uses only the **Sentiva** brand. No references to any other brand names or products.
