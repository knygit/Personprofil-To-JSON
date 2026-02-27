# Personprofil-To-JSON

Konverterer **e-fivefactor / e-stimate** personlighedsprofil-PDF'er til struktureret JSON.

Værktøjet analyserer de indlejrede søjlediagrammer i PDF'en for at aflæse placeringen af kuglemarkøren på hver af de 24 personlighedstræk og mapper dem til en af 6 zoner (Markant lav, Lav, Under Gns., Over Gns., Høj, Markant høj).

## Krav

- Python 3.10+
- pip install pdfminer.six pikepdf Pillow

## Brug

**Enkelt fil:**
```bash
python pdf_to_json.py "Navn.PDF"
python pdf_to_json.py "Navn.PDF" --output resultat.json
```

**Batch-konvertering af en hel mappe:**
```bash
python pdf_to_json.py --dir /sti/til/pdfer
python pdf_to_json.py --dir /sti/til/pdfer --output-dir /sti/til/json
```

**Windows (dobbelt-klik):**

`konverter.bat` installerer automatisk Python og afhængigheder, og konverterer derefter alle PDF'er i mappen.

## Eksempel på output

```json
{
  "profil": {
    "navn": "Kent Nygreen",
    "projekt": "Eksempel",
    "dato": "01.01.2025 12:00",
    "type": "e-fivefactor"
  },
  "personlighedstræk": [
    {
      "sektion": "Selvfokus - personlige ambitioner",
      "træk": "Ambitioner",
      "lav_pol": "Uambitiøs",
      "høj_pol": "Ambitiøs",
      "position_pct": 72.5,
      "zone": ">>",
      "zone_label": "Høj"
    }
  ],
  "metadata": {
    "svartid_sekunder": 420,
    "antal_tryk_tilbage": 3,
    "antal_ændringer_i_svar": 5,
    "antal_marginale_svar": 2,
    "landekode": "DK"
  }
}
```

## Zoneskala

| Zone | Symbol | Percentil |
|------|--------|-----------|
| Markant lav | `<<<` | 0–7% |
| Lav | `<<` | 7–31% |
| Under Gns. | `<` | 31–50% |
| Over Gns. | `>` | 50–69% |
| Høj | `>>` | 69–93% |
| Markant høj | `>>>` | 93–100% |

## Bemærkninger

- PDF'er fra e-stimate-systemet har ofte en HTML-header foran selve PDF-indholdet. Denne strippes automatisk.
- Personlighedstrækkene aflæses fra søjlediagrambilleder på side 6–9 i PDF'en (24 træk i alt).
