<div align="center">

  # PDF Size Reducer

  **Shrink huge PDFs for everyday users; 50 MB down to ~2 MB with one click, no CLI required.**

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
  [![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
  [![Windows](https://img.shields.io/badge/platform-Windows-0078D4?logo=windows&logoColor=white)](https://github.com/RawPowered/PDF-Size-Reducer/releases)
  [![Author](https://img.shields.io/badge/GitHub-RawPowered-181717?logo=github)](https://github.com/RawPowered)

</div>

---

## Why this exists

Teams needed **50 MB PDFs compressed to ~2 MB** for email, portals, and storage limits. Ghostscript, Adobe, and online shrinkers exist; but they are either **CLI-only**, **paywalled**, or **too conservative** for image-heavy scans.

PDF Size Reducer is a **desktop GUI** that stacks every practical compression path in one place: Ghostscript presets (including a custom **Ultra** max-shrink profile), full-page rasterization, and a **Check Sizes** preview that runs all presets before you commit. Built for people who do day-to-day office work, not terminal power users.

**Created by:** [Joseph Edwards (@RawPowered)](https://github.com/RawPowered) · MIT licensed

---

## Core capabilities

| Capability | What it does |
|---|---|
| **Portable Windows exe** | `dist/PDF_Size_Reducer.exe`; Ghostscript bundled, double-click to run |
| **Ultra (max shrink)** | Custom Ghostscript profile: 72 DPI color/gray, aggressive JPEGQ, duplicate detection, font subsetting |
| **Ghostscript presets** | Screen, eBook, Printer, Prepress, Default; vector-aware compression ladder |
| **Rasterize modes** | Ghostscript `pdfimage24` or PyMuPDF page raster → JPEG PDF for scan-heavy files |
| **Check Sizes preview** | Runs every preset against your file and shows estimated size + % reduction |
| **Only keep if smaller** | Safety gate; never replaces output unless the result is actually smaller |
| **One-click deps** | Python mode can download Ghostscript from Artifex releases or `pip install pymupdf` from the UI |

---

## Quick start

### Windows (recommended)

Download from [`dist/PDF_Size_Reducer.exe`](dist/PDF_Size_Reducer.exe) or [`dist/PDF_Size_Reducer.zip`](dist/PDF_Size_Reducer.zip). No install; run the exe, pick input/output, choose a method, compress.

### Python (dev / Linux)

```powershell
git clone https://github.com/RawPowered/PDF-Size-Reducer.git
cd PDF-Size-Reducer
.\run.ps1
```

Or:

```bash
python app.py
```

On first run without bundled Ghostscript, click **Install Ghostscript** in the app. For PyMuPDF raster mode, click **Install PyMuPDF**.

---

## Compression methods

| Method | Best for | Trade-off |
|---|---|---|
| **Ghostscript Presets** | Mixed vector + image PDFs | Ultra = smallest file, visible quality loss on photos |
| **Ghostscript Rasterize** | Scanned documents, photo PDFs | Image-only output; DPI slider 72-300 |
| **PyMuPDF Rasterize** | Same as above without GS raster device | JPEG quality slider 25-85; requires PyMuPDF |

**Typical workflow**

1. **Browse** to your large PDF
2. Click **Check Sizes**: compare all presets in the preview table
3. Pick the preset/method that hits your size target
4. Leave **Only keep if smaller** checked
5. **Compress**

---

## Ultra preset (max shrink)

Custom Ghostscript args beyond stock `/screen`:

- Color/gray images downsampled to **72 DPI** (bicubic)
- Mono images at **150 DPI**
- **JPEGQ=35**, duplicate image detection, unused object/image discard
- Font compress + subset + embed

Use when file size matters more than print quality (email attachments, upload limits).

---

## Project layout

```
pdf_size_reducer/
├── app.py                 # Tkinter GUI + compression engine
├── run.ps1                # venv launcher (Windows)
├── requirements.txt       # stdlib-only for core; PyMuPDF optional
├── PDF_Size_Reducer.spec  # PyInstaller bundle (includes gs/)
├── dist/                  # Portable exe + zip
├── gs/                    # Bundled Ghostscript (exe build)
└── EnVars/                # SysMap + VarMap
```

---

## Build portable exe

Requires PyInstaller and a populated `gs/` tree:

```powershell
pip install pyinstaller
pyinstaller PDF_Size_Reducer.spec
```

Output: `dist/PDF_Size_Reducer.exe`

---

## License

MIT; see [LICENSE](LICENSE). Ghostscript is bundled under its own license (Artifex); see [ghostscript.com](https://ghostscript.com/).
