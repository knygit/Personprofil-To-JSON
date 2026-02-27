# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Converts **e-fivefactor / e-stimate** personality profile PDF files into structured JSON. The PDFs often have an HTML header prepended which must be stripped before parsing. Personality trait scores are extracted via image analysis of embedded 700x90 bar chart images — not from text.

## Language

The project and its users are Danish. All UI text, field names, and comments are in Danish.

## Commands

**Install dependencies:**
```
pip install pdfminer.six pikepdf Pillow
```

**Convert a single PDF:**
```
python pdf_to_json.py "Name.PDF"
python pdf_to_json.py "Name.PDF" --output result.json
```

**Batch convert all PDFs in a directory:**
```
python pdf_to_json.py --dir /path/to/pdfs
python pdf_to_json.py --dir /path/to/pdfs --output-dir /path/to/json
```

**Windows one-click:** `konverter.bat` auto-installs Python and dependencies, then batch-converts all PDFs in its directory.

## Architecture

The entire converter lives in `pdf_to_json.py` with this pipeline:

1. **`clean_pdf`** — Strips any HTML header before the `%PDF-` marker.
2. **`extract_text_data`** — Uses pdfminer to extract metadata (name, project, date, response stats) via regex.
3. **`extract_bar_images`** — Uses pikepdf to find embedded 700x90 bar chart images from specific PDF pages.
4. **`find_ball_center`** — Image analysis (Pillow): locates the grey ball marker in each bar chart using a sliding-window darkness score across the y=25-58 pixel band.
5. **`position_to_score`** — Converts pixel position to a percentage and maps it to one of 6 zones (normal distribution: `<<<` through `>>>`).
6. **`TRAIT_MAP`** — Maps PDF pages 6-9 to the 24 personality traits (4 pages × 6 traits), each with section, trait name, and low/high pole labels.

## Key Constants

- Bar chart image size: **700×90 pixels**
- Scale pixel range: **102–590** (maps to 0–100%)
- Ball detection band: **y=25–58**, sliding window of **20px**, minimum score threshold **500**
- Zone boundaries: 7%, 31%, 50%, 69%, 93% (standard normal distribution)
