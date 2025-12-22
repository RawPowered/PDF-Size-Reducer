import glob
import json
import os
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
import urllib.request
import zipfile
import sys
import importlib
from tkinter import ttk, filedialog, messagebox

BUNDLED = hasattr(sys, "_MEIPASS")
APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(APP_DIR, "tools")
GS_DIR = os.path.join(APP_DIR, "gs") if BUNDLED else os.path.join(TOOLS_DIR, "ghostscript")

PRESETS = [
    {
        "label": "Ultra (max shrink)",
        "gs": None,
        "loss": "Extreme",
        "desc": "Very aggressive downsampling and JPEG compression. Expect heavy quality loss.",
        "args": [
            "-dDownsampleColorImages=true",
            "-dDownsampleGrayImages=true",
            "-dDownsampleMonoImages=true",
            "-dColorImageDownsampleType=/Bicubic",
            "-dGrayImageDownsampleType=/Bicubic",
            "-dMonoImageDownsampleType=/Subsample",
            "-dColorImageResolution=72",
            "-dGrayImageResolution=72",
            "-dMonoImageResolution=150",
            "-dJPEGQ=35",
            "-dDetectDuplicateImages=true",
            "-dDiscardUnusedObjects=true",
            "-dDiscardUnusedImages=true",
            "-dCompressFonts=true",
            "-dSubsetFonts=true",
            "-dEmbedAllFonts=true",
        ],
    },
    {
        "label": "Screen (smallest)",
        "gs": "/screen",
        "loss": "High",
        "desc": "Strong downsampling and compression. Best for on-screen only.",
    },
    {
        "label": "eBook (small)",
        "gs": "/ebook",
        "loss": "Medium",
        "desc": "Balanced downsampling. Good for reading on devices.",
    },
    {
        "label": "Printer (moderate)",
        "gs": "/printer",
        "loss": "Low",
        "desc": "Higher image quality. Suitable for most printing.",
    },
    {
        "label": "Prepress (large)",
        "gs": "/prepress",
        "loss": "Minimal",
        "desc": "High quality, light compression. For professional print.",
    },
    {
        "label": "Default (no preset)",
        "gs": "/default",
        "loss": "None",
        "desc": "Preserves quality; may not reduce size much.",
    },
]

METHODS = [
    {"id": "gs_preset", "label": "Ghostscript Presets (vector)"},
    {"id": "gs_raster", "label": "Ghostscript Rasterize (image-only)"},
    {"id": "pymupdf_raster", "label": "PyMuPDF Rasterize (image-only)"},
]


def find_ghostscript_in_dir(base_dir):
    if not os.path.isdir(base_dir):
        return None
    for root, _, files in os.walk(base_dir):
        for name in ("gswin64c.exe", "gswin32c.exe"):
            if name in files:
                return os.path.join(root, name)
    return None


def find_ghostscript():
    local = find_ghostscript_in_dir(GS_DIR)
    if local:
        return local

    candidates = ["gswin64c", "gswin32c", "gs"]
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path

    program_dirs = [
        os.environ.get("ProgramFiles", "C:\\Program Files"),
        os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
    ]
    gs_bins = []
    for base in program_dirs:
        if not base:
            continue
        gs_bins.extend(glob.glob(os.path.join(base, "gs", "*", "bin", "gswin64c.exe")))
        gs_bins.extend(glob.glob(os.path.join(base, "gs", "*", "bin", "gswin32c.exe")))

    if gs_bins:
        gs_bins.sort()
        return gs_bins[-1]

    return None


def format_bytes(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.2f} GB"


def run_ghostscript(gs_path, preset, input_pdf, output_pdf):
    cmd = [
        gs_path,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        f"-sOutputFile={output_pdf}",
        input_pdf,
    ]
    if preset.get("gs"):
        cmd.insert(3, f"-dPDFSETTINGS={preset['gs']}")
    extra = preset.get("args", [])
    if extra:
        cmd[3:3] = extra
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Ghostscript failed.")


def run_ghostscript_raster(gs_path, input_pdf, output_pdf, dpi):
    cmd = [
        gs_path,
        "-sDEVICE=pdfimage24",
        f"-r{dpi}",
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        "-dTextAlphaBits=4",
        "-dGraphicsAlphaBits=4",
        "-dAutoFilterColorImages=false",
        "-dColorImageFilter=/DCTEncode",
        "-dJPEGQ=60",
        f"-sOutputFile={output_pdf}",
        input_pdf,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Ghostscript rasterize failed.")


def ensure_pymupdf_installed():
    try:
        importlib.import_module("fitz")
        return True
    except Exception:
        return False


def install_pymupdf():
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "pymupdf"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "PyMuPDF install failed.")


def run_pymupdf_raster(input_pdf, output_pdf, dpi, quality):
    try:
        import fitz  # type: ignore
    except Exception as exc:
        raise RuntimeError("PyMuPDF is not installed.") from exc

    doc = fitz.open(input_pdf)
    out = fitz.open()
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        try:
            img = pix.tobytes("jpeg", jpg_quality=quality)
        except TypeError:
            img = pix.tobytes("jpeg")
        rect = page.rect
        new_page = out.new_page(width=rect.width, height=rect.height)
        new_page.insert_image(rect, stream=img)
    out.save(output_pdf, deflate=True)
    out.close()
    doc.close()


def pick_ghostscript_asset(assets):
    zip_candidates = []
    exe_candidates = []
    for asset in assets:
        name = asset.get("name", "").lower()
        if name.endswith(".zip") and "w64" in name:
            zip_candidates.append(asset)
        elif name.endswith(".exe") and "w64" in name:
            exe_candidates.append(asset)

    if zip_candidates:
        zip_candidates.sort(key=lambda item: item.get("name", ""))
        return zip_candidates[-1]
    if exe_candidates:
        exe_candidates.sort(key=lambda item: item.get("name", ""))
        return exe_candidates[-1]
    return None


def download_ghostscript(status_callback=None):
    if BUNDLED:
        raise RuntimeError("Bundled app cannot install Ghostscript at runtime.")
    os.makedirs(GS_DIR, exist_ok=True)

    api_url = "https://api.github.com/repos/ArtifexSoftware/ghostpdl-downloads/releases/latest"
    with urllib.request.urlopen(api_url, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    assets = data.get("assets", [])
    asset = pick_ghostscript_asset(assets)
    if not asset:
        raise RuntimeError("Could not find a Windows 64-bit Ghostscript zip.")

    url = asset.get("browser_download_url")
    if not url:
        raise RuntimeError("Download URL missing for Ghostscript asset.")

    tmp_dir = tempfile.mkdtemp(prefix="gs_download_")
    tmp_path = os.path.join(tmp_dir, asset.get("name", "ghostscript.zip"))

    def report(text):
        if status_callback:
            status_callback(text)

    report("Downloading Ghostscript...")
    with urllib.request.urlopen(url, timeout=60) as response:
        total = response.headers.get("Content-Length")
        total_size = int(total) if total and total.isdigit() else None
        downloaded = 0
        with open(tmp_path, "wb") as handle:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    pct = int(downloaded / total_size * 100)
                    report(f"Downloading Ghostscript... {pct}%")

    name_lower = os.path.basename(tmp_path).lower()
    if name_lower.endswith(".zip"):
        report("Extracting Ghostscript...")
        with zipfile.ZipFile(tmp_path, "r") as archive:
            archive.extractall(GS_DIR)
    elif name_lower.endswith(".exe"):
        report("Installing Ghostscript locally...")
        install_dir = os.path.join(GS_DIR, "gs")
        os.makedirs(install_dir, exist_ok=True)
        safe_tmp = tmp_path.replace("'", "''")
        safe_dir = install_dir.replace("'", "''")
        cmd = (
            "Start-Process "
            f"-FilePath '{safe_tmp}' "
            f"-ArgumentList '/S','/D={safe_dir}' "
            "-Verb RunAs -Wait"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Ghostscript installer failed.")
    else:
        raise RuntimeError("Unsupported Ghostscript package format.")

    shutil.rmtree(tmp_dir, ignore_errors=True)

    gs_path = find_ghostscript_in_dir(GS_DIR)
    if not gs_path:
        raise RuntimeError("Ghostscript was downloaded but executable was not found.")

    return gs_path


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Size Reducer")
        self.gs_path = find_ghostscript()
        self.installing = False
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}

        top = ttk.Frame(self.root)
        top.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)

        ttk.Label(top, text="Input PDF").grid(row=0, column=0, sticky="w", **pad)
        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(top, textvariable=self.input_var, width=60)
        self.input_entry.grid(row=0, column=1, sticky="we", **pad)
        ttk.Button(top, text="Browse", command=self.pick_input).grid(row=0, column=2, **pad)

        ttk.Label(top, text="Output PDF").grid(row=1, column=0, sticky="w", **pad)
        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(top, textvariable=self.output_var, width=60)
        self.output_entry.grid(row=1, column=1, sticky="we", **pad)
        ttk.Button(top, text="Save As", command=self.pick_output).grid(row=1, column=2, **pad)

        ttk.Label(top, text="Method").grid(row=2, column=0, sticky="w", **pad)
        method_choices = [m["label"] for m in METHODS]
        self.method_var = tk.StringVar(value=METHODS[0]["label"])
        self.method_menu = ttk.OptionMenu(top, self.method_var, METHODS[0]["label"], *method_choices)
        self.method_menu.grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(top, text="Preset").grid(row=3, column=0, sticky="w", **pad)
        preset_choices = [p["label"] for p in PRESETS]
        default_label = next(p["label"] for p in PRESETS if p["label"].startswith("eBook"))
        self.preset_var = tk.StringVar(value=default_label)
        self.preset_menu = ttk.OptionMenu(top, self.preset_var, default_label, *preset_choices)
        self.preset_menu.grid(row=3, column=1, sticky="w", **pad)

        self.compress_button = ttk.Button(top, text="Compress", command=self.compress)
        self.compress_button.grid(row=2, column=2, **pad)

        self.keep_smaller_var = tk.BooleanVar(value=True)
        self.keep_smaller_check = ttk.Checkbutton(
            top,
            text="Only keep if smaller",
            variable=self.keep_smaller_var,
        )
        self.keep_smaller_check.grid(row=4, column=0, sticky="w", padx=8, pady=0)

        self.desc_var = tk.StringVar()
        self.desc_label = ttk.Label(top, textvariable=self.desc_var, foreground="#555")
        self.desc_label.grid(row=4, column=1, columnspan=2, sticky="w", padx=8, pady=0)
        self._update_desc()
        self.preset_var.trace_add("write", lambda *_: self._update_desc())

        self.raster_frame = ttk.Frame(top)
        self.raster_frame.grid(row=5, column=0, columnspan=3, sticky="we", padx=8, pady=4)
        ttk.Label(self.raster_frame, text="Raster DPI").grid(row=0, column=0, sticky="w")
        self.dpi_var = tk.IntVar(value=150)
        self.dpi_scale = ttk.Scale(self.raster_frame, from_=72, to=300, orient="horizontal")
        self.dpi_scale.set(self.dpi_var.get())
        self.dpi_scale.grid(row=0, column=1, sticky="we", padx=6)
        self.dpi_value = ttk.Label(self.raster_frame, textvariable=self.dpi_var)
        self.dpi_value.grid(row=0, column=2, sticky="w")
        self.dpi_scale.bind(
            "<ButtonRelease-1>",
            lambda _e: self.dpi_var.set(int(self.dpi_scale.get())),
        )
        self.dpi_scale.bind(
            "<B1-Motion>",
            lambda _e: self.dpi_var.set(int(self.dpi_scale.get())),
        )

        ttk.Label(self.raster_frame, text="JPEG Quality").grid(row=1, column=0, sticky="w")
        self.quality_var = tk.IntVar(value=60)
        self.quality_scale = ttk.Scale(self.raster_frame, from_=25, to=85, orient="horizontal")
        self.quality_scale.set(self.quality_var.get())
        self.quality_scale.grid(row=1, column=1, sticky="we", padx=6)
        self.quality_value = ttk.Label(self.raster_frame, textvariable=self.quality_var)
        self.quality_value.grid(row=1, column=2, sticky="w")
        self.quality_scale.bind(
            "<ButtonRelease-1>",
            lambda _e: self.quality_var.set(int(self.quality_scale.get())),
        )
        self.quality_scale.bind(
            "<B1-Motion>",
            lambda _e: self.quality_var.set(int(self.quality_scale.get())),
        )
        self.raster_frame.columnconfigure(1, weight=1)
        self.raster_frame.grid_remove()

        ttk.Separator(top).grid(row=6, column=0, columnspan=3, sticky="we", padx=8, pady=10)

        ttk.Label(top, text="Possible Sizes (preview)").grid(row=7, column=0, sticky="w", **pad)
        self.preview_button = ttk.Button(top, text="Check Sizes", command=self.preview_sizes)
        self.preview_button.grid(row=7, column=2, **pad)

        self.tree = ttk.Treeview(
            top,
            columns=("preset", "loss", "size", "reduction"),
            show="headings",
            height=6,
        )
        self.tree.heading("preset", text="Preset")
        self.tree.heading("loss", text="Loss Level")
        self.tree.heading("size", text="Estimated Size")
        self.tree.heading("reduction", text="Reduction")
        self.tree.column("preset", width=170)
        self.tree.column("loss", width=100)
        self.tree.column("size", width=140)
        self.tree.column("reduction", width=100)
        self.tree.grid(row=8, column=0, columnspan=3, sticky="nsew", padx=8, pady=6)

        top.columnconfigure(1, weight=1)
        top.rowconfigure(8, weight=1)

        self.status_var = tk.StringVar(value="Ready.")
        self.status_label = ttk.Label(top, textvariable=self.status_var)
        self.status_label.grid(row=9, column=0, columnspan=3, sticky="w", padx=8, pady=6)

        self.install_button = ttk.Button(
            top,
            text="Install Ghostscript",
            command=self.install_ghostscript,
        )
        self.install_button.grid(row=10, column=0, sticky="w", padx=8, pady=6)

        self.install_pymupdf_button = ttk.Button(
            top,
            text="Install PyMuPDF",
            command=self.install_pymupdf,
        )
        self.install_pymupdf_button.grid(row=10, column=1, sticky="w", padx=8, pady=6)

        info = ttk.Label(
            top,
            text=(
                "Ultra can heavily degrade images. Image-heavy PDFs shrink most."
            ),
            foreground="#555",
        )
        info.grid(row=11, column=0, columnspan=3, sticky="w", padx=8, pady=6)

        if ensure_pymupdf_installed():
            self.install_pymupdf_button.grid_remove()

        self.method_var.trace_add("write", lambda *_: self._update_method_ui())
        self._update_method_ui()
        self._update_controls_for_dependencies()

    def _set_controls_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        self.compress_button.config(state=state)
        self.preview_button.config(state=state)

    def _update_desc(self):
        preset = self._get_selected_preset()
        self.desc_var.set(preset["desc"])

    def _update_method_ui(self):
        method = self._get_method()
        if method["id"] == "gs_preset":
            self.preset_menu.config(state="normal")
            self.raster_frame.grid_remove()
        else:
            self.preset_menu.config(state="disabled")
            self.raster_frame.grid()
        self._update_controls_for_dependencies()

    def _update_controls_for_dependencies(self):
        method = self._get_method()
        needs_gs = method["id"] in ("gs_preset", "gs_raster")
        needs_pymupdf = method["id"] == "pymupdf_raster"

        gs_ok = bool(self.gs_path)
        pymupdf_ok = ensure_pymupdf_installed()

        if BUNDLED:
            self.install_button.grid_remove()
            self.install_pymupdf_button.grid_remove()
        elif gs_ok:
            self.install_button.grid_remove()
        else:
            self.install_button.grid()

        if BUNDLED:
            pass
        elif pymupdf_ok:
            self.install_pymupdf_button.grid_remove()
        else:
            self.install_pymupdf_button.grid()

        if needs_gs and not gs_ok:
            self._set_controls_enabled(False)
            self.set_status("Ghostscript is missing. Click Install Ghostscript.")
            return

        if needs_pymupdf and not pymupdf_ok:
            self._set_controls_enabled(False)
            self.set_status("PyMuPDF is missing. Click Install PyMuPDF.")
            return

        self._set_controls_enabled(True)

    def _get_method(self):
        label = self.method_var.get()
        for method in METHODS:
            if method["label"] == label:
                return method
        return METHODS[0]

    def pick_input(self):
        path = filedialog.askopenfilename(
            title="Select PDF",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not path:
            return
        self.input_var.set(path)
        if not self.output_var.get():
            base = os.path.splitext(path)[0]
            self.output_var.set(base + "_compressed.pdf")

    def pick_output(self):
        path = filedialog.asksaveasfilename(
            title="Save compressed PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if path:
            self.output_var.set(path)

    def _get_selected_preset(self):
        label = self.preset_var.get()
        for preset in PRESETS:
            if preset["label"] == label:
                return preset
        return PRESETS[0]

    def set_status(self, text):
        self.status_var.set(text)
        self.root.update_idletasks()

    def _validate_input(self):
        input_path = self.input_var.get().strip()
        if not input_path or not os.path.isfile(input_path):
            messagebox.showerror("Missing input", "Please select a PDF file.")
            return None
        return input_path

    def install_ghostscript(self):
        if self.installing:
            return
        self.installing = True
        self.install_button.config(state="disabled")
        self.set_status("Starting Ghostscript download...")

        def update_status(text):
            self.root.after(0, lambda: self.set_status(text))

        def worker():
            try:
                gs_path = download_ghostscript(update_status)
                self.gs_path = gs_path
                self.root.after(0, lambda: self.install_button.grid_remove())
                self.root.after(0, lambda: self._update_controls_for_dependencies())
                self.root.after(0, lambda: self.set_status("Ghostscript installed."))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("Install failed", str(exc)))
                self.root.after(0, lambda: self.install_button.config(state="normal"))
                self.root.after(0, lambda: self.set_status("Install failed."))
            finally:
                self.installing = False

        threading.Thread(target=worker, daemon=True).start()

    def install_pymupdf(self):
        self.install_pymupdf_button.config(state="disabled")
        self.set_status("Installing PyMuPDF...")

        def worker():
            try:
                install_pymupdf()
                self.root.after(0, lambda: self.install_pymupdf_button.grid_remove())
                self.root.after(0, lambda: self._update_controls_for_dependencies())
                self.root.after(0, lambda: self.set_status("PyMuPDF installed."))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("Install failed", str(exc)))
                self.root.after(0, lambda: self.install_pymupdf_button.config(state="normal"))
                self.root.after(0, lambda: self.set_status("Install failed."))

        threading.Thread(target=worker, daemon=True).start()

    def preview_sizes(self):
        input_path = self._validate_input()
        if not input_path:
            return

        self.preview_button.config(state="disabled")
        self.compress_button.config(state="disabled")
        self.set_status("Checking sizes... this may take a moment.")

        for item in self.tree.get_children():
            self.tree.delete(item)

        def worker():
            temp_dir = tempfile.mkdtemp(prefix="pdf_preview_")
            results = []
            original_size = os.path.getsize(input_path)
            try:
                method = self._get_method()
                if method["id"] == "gs_preset":
                    if not self.gs_path:
                        raise RuntimeError("Ghostscript is not installed.")
                    for preset in PRESETS:
                        out_path = os.path.join(
                            temp_dir,
                            preset["label"].replace(" ", "_") + ".pdf",
                        )
                        run_ghostscript(self.gs_path, preset, input_path, out_path)
                        new_size = os.path.getsize(out_path)
                        reduction = 100 - (new_size / original_size * 100)
                        results.append(
                            (
                                preset["label"],
                                preset["loss"],
                                format_bytes(new_size),
                                f"{reduction:+.0f}%",
                            )
                        )
                elif method["id"] == "gs_raster":
                    if not self.gs_path:
                        raise RuntimeError("Ghostscript is not installed.")
                    out_path = os.path.join(temp_dir, "gs_raster.pdf")
                    run_ghostscript_raster(
                        self.gs_path,
                        input_path,
                        out_path,
                        dpi=int(self.dpi_var.get()),
                    )
                    new_size = os.path.getsize(out_path)
                    reduction = 100 - (new_size / original_size * 100)
                    results.append(
                        (
                            "Ghostscript Rasterize",
                            "Extreme",
                            format_bytes(new_size),
                            f"{reduction:+.0f}%",
                        )
                    )
                else:
                    if not ensure_pymupdf_installed():
                        raise RuntimeError("PyMuPDF is not installed.")
                    out_path = os.path.join(temp_dir, "pymupdf_raster.pdf")
                    run_pymupdf_raster(
                        input_path,
                        out_path,
                        dpi=int(self.dpi_var.get()),
                        quality=int(self.quality_var.get()),
                    )
                    new_size = os.path.getsize(out_path)
                    reduction = 100 - (new_size / original_size * 100)
                    results.append(
                        (
                            "PyMuPDF Rasterize",
                            "Extreme",
                            format_bytes(new_size),
                            f"{reduction:+.0f}%",
                        )
                    )
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

            def update_ui():
                for label, loss, size, reduction in results:
                    self.tree.insert("", "end", values=(label, loss, size, reduction))
                self.set_status("Preview complete.")
                self.preview_button.config(state="normal")
                self.compress_button.config(state="normal")

            self.root.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def compress(self):
        input_path = self._validate_input()
        if not input_path:
            return

        output_path = self.output_var.get().strip()
        if not output_path:
            base = os.path.splitext(input_path)[0]
            output_path = base + "_compressed.pdf"
            self.output_var.set(output_path)

        if os.path.exists(output_path):
            if not messagebox.askyesno(
                "Overwrite?",
                "Output file exists. Overwrite it?",
            ):
                return

        preset = self._get_selected_preset()
        method = self._get_method()
        self.compress_button.config(state="disabled")
        self.preview_button.config(state="disabled")
        if method["id"] == "gs_preset":
            status_label = f"Compressing with {preset['label']}..."
        elif method["id"] == "gs_raster":
            status_label = "Rasterizing with Ghostscript..."
        else:
            status_label = "Rasterizing with PyMuPDF..."
        self.set_status(status_label)

        def worker():
            try:
                base_dir = os.path.dirname(output_path) or os.getcwd()
                fd, temp_out = tempfile.mkstemp(prefix="pdf_tmp_", suffix=".pdf", dir=base_dir)
                os.close(fd)
                try:
                    if method["id"] == "gs_preset":
                        if not self.gs_path:
                            raise RuntimeError("Ghostscript is not installed.")
                        run_ghostscript(self.gs_path, preset, input_path, temp_out)
                    elif method["id"] == "gs_raster":
                        if not self.gs_path:
                            raise RuntimeError("Ghostscript is not installed.")
                        run_ghostscript_raster(
                            self.gs_path,
                            input_path,
                            temp_out,
                            dpi=int(self.dpi_var.get()),
                        )
                    else:
                        if not ensure_pymupdf_installed():
                            raise RuntimeError("PyMuPDF is not installed.")
                        run_pymupdf_raster(
                            input_path,
                            temp_out,
                            dpi=int(self.dpi_var.get()),
                            quality=int(self.quality_var.get()),
                        )
                    new_size = os.path.getsize(temp_out)
                    original_size = os.path.getsize(input_path)
                    grew = new_size > original_size
                    if grew and self.keep_smaller_var.get():
                        os.remove(temp_out)
                        self.root.after(
                            0,
                            lambda: messagebox.showwarning(
                                "Larger than original",
                                (
                                    "Result is larger than the original. "
                                    "Output was not saved.\n"
                                    f"Original: {format_bytes(original_size)}\n"
                                    f"Result: {format_bytes(new_size)}"
                                ),
                            ),
                        )
                        return
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    os.replace(temp_out, output_path)
                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Done",
                            f"Saved: {output_path}\nSize: {format_bytes(new_size)}",
                        ),
                    )
                finally:
                    if os.path.exists(temp_out):
                        os.remove(temp_out)
            except Exception as exc:
                self.root.after(0, lambda exc=exc: messagebox.showerror("Error", str(exc)))
            finally:
                self.root.after(0, lambda: self.set_status("Ready."))
                self.root.after(0, lambda: self.compress_button.config(state="normal"))
                self.root.after(0, lambda: self.preview_button.config(state="normal"))

        threading.Thread(target=worker, daemon=True).start()


def main():
    root = tk.Tk()
    root.minsize(640, 460)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
