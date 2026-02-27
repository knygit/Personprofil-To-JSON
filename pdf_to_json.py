#!/usr/bin/env python3
"""
e-fivefactor PDF Profile to JSON Converter

Converts e-fivefactor/e-stimate personality profile PDF files to structured JSON.
Handles PDFs that may have an HTML header prepended (common from the e-stimate system).

Requirements:
    pip install pdfminer.six pikepdf Pillow

Usage:
    python pdf_to_json.py "Kent Nygreen.PDF"
    python pdf_to_json.py "Kent Nygreen.PDF" --output result.json
    python pdf_to_json.py *.PDF
    python pdf_to_json.py --dir /path/to/pdfs
    python pdf_to_json.py --dir /path/to/pdfs --output-dir /path/to/json
"""

import argparse
import io
import json
import re
import sys
import zlib
from pathlib import Path

import pikepdf
from PIL import Image
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams


def clean_pdf(input_path: str) -> bytes:
    """Strip any HTML header before the %PDF- marker."""
    with open(input_path, "rb") as f:
        data = f.read()
    idx = data.find(b"%PDF-")
    if idx == -1:
        raise ValueError(f"No PDF content found in {input_path}")
    if idx > 0:
        data = data[idx:]
    return data


def extract_text_data(pdf_bytes: bytes) -> dict:
    """Extract text metadata from the PDF (name, project, date, etc.)."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    laparams = LAParams(line_margin=0.3, word_margin=0.1, char_margin=1.0)
    text = extract_text(tmp_path, laparams=laparams)

    Path(tmp_path).unlink()

    metadata = {}

    # Extract focus person name
    m = re.search(r"Fokusperson:\s*(.+)", text)
    if m:
        metadata["navn"] = m.group(1).strip()

    # Extract project
    m = re.search(r"Projekt:\s*(.+)", text)
    if m:
        metadata["projekt"] = m.group(1).strip()

    # Extract date
    m = re.search(r"Dato:\s*([\d.]+\s+[\d:]+)", text)
    if m:
        metadata["dato"] = m.group(1).strip()

    # Extract response time
    m = re.search(r"Svartid\s*:\s*(\d+)\s*Sekunder", text)
    if m:
        metadata["svartid_sekunder"] = int(m.group(1))

    # Extract back button presses
    m = re.search(r"Antal tryk p.+tilbage knap\s*:\s*(\d+)", text)
    if m:
        metadata["antal_tryk_tilbage"] = int(m.group(1))

    # Extract answer changes
    m = re.search(r"Antal .ndringer i svar\s*:\s*(\d+)", text)
    if m:
        metadata["antal_ændringer_i_svar"] = int(m.group(1))

    # Extract marginal answers
    m = re.search(r"Antal marginale svar\s*:\s*(\d+)", text)
    if m:
        metadata["antal_marginale_svar"] = int(m.group(1))

    # Extract country code
    m = re.search(r"Landekode\s*:\s*(\w+)", text)
    if m:
        metadata["landekode"] = m.group(1).strip()

    return metadata


def extract_bar_images(page) -> list:
    """Extract 700x90 bar chart images from a PDF page."""
    resources = page.get("/Resources", {})
    xobjects = resources.get("/XObject", {})
    bars = []
    for name, ref in sorted(xobjects.items()):
        obj = ref
        w = int(str(obj.get("/Width", 0)))
        h = int(str(obj.get("/Height", 0)))
        if w == 700 and h == 90:
            raw = obj.read_raw_bytes()
            filt = str(obj.get("/Filter", ""))
            if "DCTDecode" in filt:
                img = Image.open(io.BytesIO(raw))
            elif "FlateDecode" in filt:
                decompressed = zlib.decompress(raw)
                img = Image.frombytes("RGB", (w, h), decompressed)
            else:
                img = Image.frombytes("RGB", (w, h), raw)
            bars.append((name, img))
    return bars


def find_ball_center(img) -> float | None:
    """Find the center X of the grey ball marker in a bar chart image.

    The ball is a 3D-looking grey sphere ~17px wide. We use a sliding
    window of 20px across the image and find where the total darkness
    score (in the y=25-58 band) is highest. This is robust against
    JPEG artifacts and thin scale-line markers.
    """
    w, h = img.size

    # Calculate a darkness score per column in the bar's vertical band
    col_darkness = [0] * w
    for x in range(w):
        dark_score = 0
        for y in range(25, 58):
            r, g, b = img.getpixel((x, y))
            brightness = (r + g + b) / 3
            if brightness < 200:
                dark_score += 200 - brightness
        col_darkness[x] = dark_score

    # Sliding window of 20px to find the ball center
    window = 20
    best_score = 0
    best_center = None
    for x in range(window // 2, w - window // 2):
        window_score = sum(col_darkness[x - window // 2 : x + window // 2])
        if window_score > best_score:
            best_score = window_score
            best_center = x

    if best_score < 500:
        return None

    return float(best_center)


def position_to_score(center_x: float, scale_start: int = 102, scale_end: int = 590) -> dict:
    """Convert ball X position to a zone classification.

    The e-fivefactor scale has 6 zones based on a normal distribution:
        <<< Markant lav   (7%)   cumulative:  0 -  7%
        <<  Lav          (24%)   cumulative:  7 - 31%
        <   Under Gns.   (19%)   cumulative: 31 - 50%
        >   Over Gns.    (19%)   cumulative: 50 - 69%
        >>  Høj          (24%)   cumulative: 69 - 93%
        >>> Markant høj   (7%)   cumulative: 93 -100%
    """
    scale_width = scale_end - scale_start
    position_pct = ((center_x - scale_start) / scale_width) * 100
    position_pct = max(0.0, min(100.0, position_pct))

    zones = [
        (7, "<<<", "Markant lav"),
        (31, "<<", "Lav"),
        (50, "<", "Under Gns."),
        (69, ">", "Over Gns."),
        (93, ">>", "Høj"),
        (100, ">>>", "Markant høj"),
    ]

    for boundary, symbol, label in zones:
        if position_pct <= boundary:
            return {
                "position_pct": round(position_pct, 1),
                "zone": symbol,
                "zone_label": label,
            }

    return {"position_pct": round(position_pct, 1), "zone": ">>>", "zone_label": "Markant høj"}


# The 24 personality traits, organized by page (0-indexed) and position
TRAIT_MAP = {
    5: [  # PDF page 6
        ("Selvfokus - personlige ambitioner", "Ambitioner", "Uambitiøs", "Ambitiøs"),
        ("Selvfokus - personlige ambitioner", "Selvpromovering", "Beskeden", "Selvpromoverende"),
        ("Selvfokus - personlige ambitioner", "Taktisk tilgang", "Ærlig", "Taktisk"),
        ("Handlekraft - eksekveringsevne", "Konfronterende tilgang", "Samarbejdsvillig", "Konfronterende"),
        ("Handlekraft - eksekveringsevne", "Initiativ", "Lavt initiativ", "Initiativrig"),
        ("Handlekraft - eksekveringsevne", "Selvtillid", "Lav selvtillid", "Høj selvtillid"),
    ],
    6: [  # PDF page 7
        ("Udadvendthed - personlig energi", "Energi", "Passiv", "Energisk"),
        ("Udadvendthed - personlig energi", "Optimisme", "Lav optimisme", "Optimistisk"),
        ("Udadvendthed - personlig energi", "Selskabelighed", "Tilbageholdende", "Selskabelig"),
        ("Nytænkning - udviklingsorientering", "Forandringslyst", "Foretrækker det kendte", "Forandringslysten"),
        ("Nytænkning - udviklingsorientering", "Iderigdom", "Konkret tænkende", "Iderig"),
        ("Nytænkning - udviklingsorientering", "Impulsivitet", "Høj impulskontrol", "Impulsiv"),
    ],
    7: [  # PDF page 8
        ("Fokus på andre - samarbejdsevne", "Hjælpsomhed", "Lav hjælpsomhed", "Hjælpsom"),
        ("Fokus på andre - samarbejdsevne", "Tolerance og rummelighed", "Lav tolerance", "Tolerant"),
        ("Fokus på andre - samarbejdsevne", "Samarbejdsorientering", "Konfronterende", "Samarbejdsvillig"),
        ("Følelsesorientering - hensynsfuldhed", "Emotionalitet", "Lav emotionalitet", "Emotionel"),
        ("Følelsesorientering - hensynsfuldhed", "Empati og indføling", "Lav empati", "Empatisk"),
        ("Følelsesorientering - hensynsfuldhed", "Stressbarhed", "Håndterer stress", "Stressbar"),
    ],
    8: [  # PDF page 9
        ("Reserveret - reflekterende", "Privat tilgang", "Imødekommende", "Privat anlagt"),
        ("Reserveret - reflekterende", "Tilbageholdenhed", "Selskabelig", "Tilbageholdende"),
        ("Reserveret - reflekterende", "Selvværd (omvendt)", "Højt selvværd", "Lavt selvværd"),
        ("Kontrolleret - omhyggelighed", "Struktur", "Ustruktureret", "Struktureret"),
        ("Kontrolleret - omhyggelighed", "Omhyggelighed", "Lav omhyggelighed", "Omhyggelig"),
        ("Kontrolleret - omhyggelighed", "Praktisk orientering", "Teoretisk, abstrakt", "Praksisorienteret"),
    ],
}


def convert_profile(input_path: str, output_path: str | None = None) -> dict:
    """Convert an e-fivefactor PDF profile to JSON."""
    print(f"Reading: {input_path}")

    # Clean PDF (strip HTML header if present)
    pdf_bytes = clean_pdf(input_path)

    # Extract text metadata
    print("Extracting text metadata...")
    text_meta = extract_text_data(pdf_bytes)

    # Open PDF for image analysis
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    pdf = pikepdf.open(tmp_path)

    # Extract personality trait scores from bar chart images
    print("Analyzing bar chart images...")
    trait_scores = []
    for page_idx, page_traits in TRAIT_MAP.items():
        if page_idx >= len(pdf.pages):
            print(f"  Warning: page {page_idx + 1} not found, skipping")
            continue

        bars = extract_bar_images(pdf.pages[page_idx])

        for bar_idx, (name, img) in enumerate(bars):
            if bar_idx >= len(page_traits):
                break

            section, trait, low, high = page_traits[bar_idx]
            center = find_ball_center(img)

            if center is not None:
                score = position_to_score(center)
                entry = {
                    "sektion": section,
                    "træk": trait,
                    "lav_pol": low,
                    "høj_pol": high,
                    "position_pct": score["position_pct"],
                    "zone": score["zone"],
                    "zone_label": score["zone_label"],
                }
                trait_scores.append(entry)
                print(f"  {trait:35s} {score['zone']:4s} {score['zone_label']:12s} ({score['position_pct']:.1f}%)")
            else:
                print(f"  {trait:35s} -- kugle ikke fundet --")

    pdf.close()
    Path(tmp_path).unlink()

    # Build output JSON
    result = {
        "profil": {
            "navn": text_meta.get("navn", "Ukendt"),
            "projekt": text_meta.get("projekt", ""),
            "dato": text_meta.get("dato", ""),
            "type": "e-fivefactor",
        },
        "personlighedstræk": trait_scores,
        "metadata": {
            "svartid_sekunder": text_meta.get("svartid_sekunder"),
            "antal_tryk_tilbage": text_meta.get("antal_tryk_tilbage"),
            "antal_ændringer_i_svar": text_meta.get("antal_ændringer_i_svar"),
            "antal_marginale_svar": text_meta.get("antal_marginale_svar"),
            "landekode": text_meta.get("landekode"),
        },
    }

    # Write output
    if output_path is None:
        output_path = str(Path(input_path).with_suffix(".json"))

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nJSON saved: {output_path}")
    return result


def find_pdf_files(path: str) -> list[Path]:
    """Find all PDF files in a directory (case-insensitive extension)."""
    directory = Path(path)
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {path}")
    files = []
    for ext in ("*.pdf", "*.PDF", "*.Pdf"):
        files.extend(directory.glob(ext))
    # Deduplicate (in case filesystem is case-insensitive)
    seen = set()
    unique = []
    for f in sorted(files):
        key = str(f).lower()
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def convert_batch(pdf_files: list[Path], output_dir: Path | None = None) -> dict:
    """Convert multiple PDF files. Returns summary dict."""
    succeeded = []
    failed = []

    for pdf_path in pdf_files:
        if output_dir:
            out_path = str(output_dir / pdf_path.with_suffix(".json").name)
        else:
            out_path = None

        try:
            convert_profile(str(pdf_path), out_path)
            succeeded.append(str(pdf_path))
        except Exception as e:
            print(f"\nFEJL ved {pdf_path.name}: {e}\n")
            failed.append((str(pdf_path), str(e)))

    print("\n" + "=" * 60)
    print(f"Resultat: {len(succeeded)} OK, {len(failed)} fejlet af {len(pdf_files)} filer")
    if failed:
        print("\nFejlede filer:")
        for path, err in failed:
            print(f"  {Path(path).name}: {err}")
    print("=" * 60)

    return {"succeeded": succeeded, "failed": failed}


def main():
    parser = argparse.ArgumentParser(
        description="Convert e-fivefactor PDF profiles to JSON",
        epilog="Examples:\n"
               "  %(prog)s file.PDF\n"
               "  %(prog)s *.PDF\n"
               "  %(prog)s --dir /path/to/pdfs\n"
               "  %(prog)s --dir /path/to/pdfs --output-dir /path/to/json\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "pdf_files", nargs="*", default=[],
        help="One or more PDF files to convert",
    )
    parser.add_argument(
        "--dir", "-d", metavar="DIR",
        help="Convert all PDF files in this directory",
    )
    parser.add_argument(
        "--output", "-o", metavar="FILE",
        help="Output JSON path (only for single-file mode)",
    )
    parser.add_argument(
        "--output-dir", metavar="DIR",
        help="Directory to write JSON files into (default: same dir as PDF)",
    )
    args = parser.parse_args()

    # Collect PDF files
    pdf_files: list[Path] = []

    if args.dir:
        pdf_files.extend(find_pdf_files(args.dir))

    for f in args.pdf_files:
        p = Path(f)
        if p.is_dir():
            pdf_files.extend(find_pdf_files(str(p)))
        elif p.exists():
            pdf_files.append(p)
        else:
            print(f"Advarsel: fil ikke fundet: {f}")

    if not pdf_files:
        parser.print_help()
        print("\nIngen PDF-filer fundet.")
        sys.exit(1)

    # Prepare output directory
    output_dir = Path(args.output_dir) if args.output_dir else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Single file with explicit --output
    if len(pdf_files) == 1 and args.output:
        convert_profile(str(pdf_files[0]), args.output)
    # Single file without --output
    elif len(pdf_files) == 1:
        out = str(output_dir / pdf_files[0].with_suffix(".json").name) if output_dir else None
        convert_profile(str(pdf_files[0]), out)
    # Multiple files
    else:
        if args.output:
            print("Advarsel: --output ignoreres ved batch-konvertering. Brug --output-dir i stedet.")
        convert_batch(pdf_files, output_dir)


if __name__ == "__main__":
    main()
