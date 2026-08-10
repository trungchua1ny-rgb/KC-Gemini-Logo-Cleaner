from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

from .geometry import calculate_mask_box
from .models import MaskConfig, ProcessingResult
from .processor import clean_array, collect_images, load_image, process_batch


APP_BACKGROUND = "#070C13"
PANEL_BACKGROUND = "#0C141F"
ELEVATED_BACKGROUND = "#101A27"
INPUT_BACKGROUND = "#080F18"
BORDER = "#1D2B3B"
TEXT = "#F4F7FB"
MUTED = "#94A3B8"
PRIMARY = "#2878FF"
SUCCESS = "#22C55E"
ERROR = "#EF4444"


class LogoCleanerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("KC Gemini Logo Cleaner")
        self.geometry("1160x790")
        self.minsize(980, 700)
        self.configure(bg=APP_BACKGROUND)

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.recursive_var = tk.BooleanVar(value=True)
        self.width_var = tk.DoubleVar(value=5.2)
        self.height_var = tk.DoubleVar(value=9.4)
        self.right_var = tk.DoubleVar(value=4.7)
        self.bottom_var = tk.DoubleVar(value=8.9)
        self.padding_var = tk.DoubleVar(value=0.8)
        self.radius_var = tk.DoubleVar(value=4.0)
        self.method_var = tk.StringVar(value="lama-ai")
        self.shape_var = tk.StringVar(value="rounded-rectangle")
        self.status_var = tk.StringVar(value="Chọn thư mục ảnh để bắt đầu.")
        self.progress_var = tk.DoubleVar(value=0)
        self.image_paths: list[Path] = []
        self.preview_original: ImageTk.PhotoImage | None = None
        self.preview_cleaned: ImageTk.PhotoImage | None = None
        self.cancel_event = threading.Event()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None

        self._configure_styles()
        self._build_ui()
        self.after(100, self._poll_events)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=APP_BACKGROUND)
        style.configure("Panel.TFrame", background=PANEL_BACKGROUND)
        style.configure("TLabel", background=APP_BACKGROUND, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=PANEL_BACKGROUND, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=APP_BACKGROUND, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("PanelMuted.TLabel", background=PANEL_BACKGROUND, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=APP_BACKGROUND, foreground=TEXT, font=("Segoe UI Semibold", 20))
        style.configure("CardTitle.TLabel", background=PANEL_BACKGROUND, foreground=TEXT, font=("Segoe UI Semibold", 11))
        style.configure("TButton", font=("Segoe UI Semibold", 9), padding=(10, 7))
        style.configure("Primary.TButton", foreground="white", background=PRIMARY, bordercolor=PRIMARY)
        style.map("Primary.TButton", background=[("active", "#3B8BFF"), ("disabled", "#25364C")])
        style.configure("TCheckbutton", background=PANEL_BACKGROUND, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", PANEL_BACKGROUND)])
        style.configure("TCombobox", fieldbackground=INPUT_BACKGROUND, background=INPUT_BACKGROUND, foreground=TEXT)
        style.configure("TProgressbar", troughcolor=INPUT_BACKGROUND, background=PRIMARY, bordercolor=INPUT_BACKGROUND)

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(22, 18, 22, 12))
        header.pack(fill="x")
        ttk.Label(header, text="KC Gemini Logo Cleaner", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Xử lý hàng loạt logo nhìn thấy ở góc phải dưới. Ảnh nguồn luôn được giữ nguyên.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        path_panel = ttk.Frame(self, style="Panel.TFrame", padding=16)
        path_panel.pack(fill="x", padx=22, pady=(0, 12))
        path_panel.columnconfigure(1, weight=1)
        ttk.Label(path_panel, text="THƯ MỤC", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self._path_row(path_panel, 1, "Ảnh nguồn", self.source_var, self._choose_source)
        self._path_row(path_panel, 2, "Kết quả", self.output_var, self._choose_output)
        ttk.Checkbutton(path_panel, text="Quét cả thư mục con", variable=self.recursive_var).grid(
            row=3, column=1, sticky="w", pady=(7, 0)
        )
        ttk.Button(path_panel, text="Quét ảnh", command=self.scan_images).grid(row=3, column=2, sticky="e", pady=(7, 0))

        body = ttk.Frame(self, padding=(22, 0, 22, 12))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=280)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        settings = ttk.Frame(body, style="Panel.TFrame", padding=16)
        settings.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ttk.Label(settings, text="TỰ ĐỘNG XÁC ĐỊNH LOGO", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Label(
            settings,
            text="Không cần bấm chọn điểm. App tự dùng vị trí chuẩn của logo Gemini ở góc phải dưới và co giãn theo độ phân giải ảnh.",
            style="PanelMuted.TLabel",
            wraplength=245,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        badge = tk.Label(
            settings,
            text="✓  PRESET GEMINI ĐÃ HIỆU CHỈNH",
            bg="#0D2A22",
            fg=SUCCESS,
            font=("Segoe UI Semibold", 9),
            padx=10,
            pady=8,
        )
        badge.pack(fill="x", pady=(0, 10))
        ai_badge = tk.Label(
            settings,
            text="AI LAMA · PHỤC HỒI VẬT THỂ TỰ NHIÊN",
            bg="#0B2340",
            fg="#6DB5FF",
            font=("Segoe UI Semibold", 9),
            padx=10,
            pady=8,
        )
        ai_badge.pack(fill="x", pady=(0, 10))
        ttk.Label(
            settings,
            text="Vị trí chuẩn: tâm khoảng 93% chiều rộng và 87% chiều cao ảnh.",
            style="PanelMuted.TLabel",
            wraplength=245,
            justify="left",
        ).pack(anchor="w", pady=(0, 14))
        ttk.Button(settings, text="Xem lại kết quả tự động", command=self.update_preview).pack(fill="x")
        self.advanced_button = ttk.Button(
            settings,
            text="Tinh chỉnh nâng cao (dự phòng)",
            command=self.toggle_advanced,
        )
        self.advanced_button.pack(fill="x", pady=(8, 0))

        self.advanced_frame = ttk.Frame(settings, style="Panel.TFrame")
        self._number_field(self.advanced_frame, "Chiều rộng (%)", self.width_var, 0.1)
        self._number_field(self.advanced_frame, "Chiều cao (%)", self.height_var, 0.1)
        self._number_field(self.advanced_frame, "Lề phải (%)", self.right_var, 0.1)
        self._number_field(self.advanced_frame, "Lề dưới (%)", self.bottom_var, 0.1)
        self._number_field(self.advanced_frame, "Padding (%)", self.padding_var, 0.05)
        self._number_field(self.advanced_frame, "Bán kính phục hồi", self.radius_var, 0.5)
        ttk.Label(self.advanced_frame, text="Hình dạng mask", style="Panel.TLabel").pack(anchor="w", pady=(8, 3))
        shape = ttk.Combobox(
            self.advanced_frame,
            textvariable=self.shape_var,
            values=("gemini-sparkle", "rounded-rectangle", "ellipse"),
            state="readonly",
        )
        shape.pack(fill="x")
        ttk.Label(self.advanced_frame, text="Thuật toán (mặc định: lama-ai)", style="Panel.TLabel").pack(anchor="w", pady=(8, 3))
        method = ttk.Combobox(
            self.advanced_frame,
            textvariable=self.method_var,
            values=("lama-ai", "texture-patch", "telea", "navier-stokes"),
            state="readonly",
        )
        method.pack(fill="x")
        ttk.Button(self.advanced_frame, text="Khôi phục preset Gemini", command=self.reset_preset).pack(fill="x", pady=(10, 0))

        preview = ttk.Frame(body, style="Panel.TFrame", padding=16)
        preview.grid(row=0, column=1, sticky="nsew")
        preview.columnconfigure(0, weight=1)
        preview.columnconfigure(1, weight=1)
        preview.rowconfigure(2, weight=1)
        ttk.Label(preview, text="XEM TRƯỚC", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.file_selector = ttk.Combobox(preview, state="readonly")
        self.file_selector.grid(row=0, column=1, sticky="ew", padx=(12, 0))
        self.file_selector.bind("<<ComboboxSelected>>", lambda _event: self.update_preview())
        ttk.Label(preview, text="Ảnh gốc · app tự xác định vùng logo", style="PanelMuted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(10, 6)
        )
        ttk.Label(preview, text="Kết quả dự kiến", style="PanelMuted.TLabel").grid(
            row=1, column=1, sticky="w", padx=(12, 0), pady=(10, 6)
        )
        self.original_label = tk.Label(preview, bg=INPUT_BACKGROUND, fg=MUTED, text="Chưa có ảnh")
        self.original_label.grid(row=2, column=0, sticky="nsew", padx=(0, 6))
        self.cleaned_label = tk.Label(preview, bg=INPUT_BACKGROUND, fg=MUTED, text="Chưa có ảnh")
        self.cleaned_label.grid(row=2, column=1, sticky="nsew", padx=(6, 0))

        footer = ttk.Frame(self, padding=(22, 10, 22, 18))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w")
        ttk.Progressbar(footer, variable=self.progress_var, maximum=100).pack(fill="x", pady=(7, 10))
        actions = ttk.Frame(footer)
        actions.pack(fill="x")
        ttk.Button(actions, text="Mở thư mục kết quả", command=self.open_output).pack(side="left")
        self.stop_button = ttk.Button(actions, text="Dừng", command=self.cancel_processing, state="disabled")
        self.stop_button.pack(side="right", padx=(8, 0))
        self.process_button = ttk.Button(
            actions,
            text="Xử lý toàn bộ ảnh",
            command=self.start_processing,
            style="Primary.TButton",
        )
        self.process_button.pack(side="right")

    def _path_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        command: object,
    ) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        entry = tk.Entry(
            parent,
            textvariable=variable,
            bg=INPUT_BACKGROUND,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=PRIMARY,
        )
        entry.grid(row=row, column=1, sticky="ew", ipady=7, pady=4)
        ttk.Button(parent, text="Chọn…", command=command).grid(row=row, column=2, padx=(10, 0), pady=4)

    def _number_field(self, parent: ttk.Frame, label: str, variable: tk.DoubleVar, increment: float) -> None:
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, style="Panel.TLabel").pack(side="left")
        spin = tk.Spinbox(
            row,
            from_=0,
            to=30,
            increment=increment,
            textvariable=variable,
            width=8,
            bg=INPUT_BACKGROUND,
            fg=TEXT,
            buttonbackground=ELEVATED_BACKGROUND,
            insertbackground=TEXT,
            relief="flat",
        )
        spin.pack(side="right", ipady=3)

    def _choose_source(self) -> None:
        selected = filedialog.askdirectory(title="Chọn thư mục ảnh nguồn")
        if not selected:
            return
        self.source_var.set(selected)
        self.output_var.set(str(Path(selected) / "KC_Logo_Cleaned"))
        self.scan_images()

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(title="Chọn thư mục kết quả")
        if selected:
            self.output_var.set(selected)

    def _config(self) -> MaskConfig:
        return MaskConfig(
            width_percent=self.width_var.get(),
            height_percent=self.height_var.get(),
            right_margin_percent=self.right_var.get(),
            bottom_margin_percent=self.bottom_var.get(),
            padding_percent=self.padding_var.get(),
            inpaint_radius=self.radius_var.get(),
            method=self.method_var.get(),  # type: ignore[arg-type]
            shape=self.shape_var.get(),  # type: ignore[arg-type]
        )

    def reset_preset(self) -> None:
        self.width_var.set(5.2)
        self.height_var.set(9.4)
        self.right_var.set(4.7)
        self.bottom_var.set(8.9)
        self.padding_var.set(0.8)
        self.radius_var.set(4.0)
        self.method_var.set("lama-ai")
        self.shape_var.set("rounded-rectangle")
        self.update_preview()

    def toggle_advanced(self) -> None:
        if self.advanced_frame.winfo_manager():
            self.advanced_frame.pack_forget()
            self.advanced_button.configure(text="Tinh chỉnh nâng cao (dự phòng)")
        else:
            self.advanced_frame.pack(fill="x", pady=(10, 0))
            self.advanced_button.configure(text="Ẩn tinh chỉnh nâng cao")

    def scan_images(self) -> None:
        try:
            if not self.source_var.get().strip():
                raise ValueError("Hãy chọn thư mục ảnh nguồn.")
            source = Path(self.source_var.get()).expanduser()
            output = Path(self.output_var.get()).expanduser() if self.output_var.get() else source / "KC_Logo_Cleaned"
            self.image_paths = collect_images(source, output, self.recursive_var.get())
            self.file_selector["values"] = [path.name for path in self.image_paths]
            if self.image_paths:
                self.file_selector.current(0)
                self.status_var.set(f"Đã tìm thấy {len(self.image_paths)} ảnh.")
                self.update_preview()
            else:
                self.status_var.set("Không tìm thấy ảnh PNG/JPG/JPEG/WebP/BMP/TIFF.")
                self.original_label.configure(image="", text="Không có ảnh")
                self.cleaned_label.configure(image="", text="Không có ảnh")
        except Exception as error:
            messagebox.showerror("Không thể quét ảnh", str(error))

    def _selected_image(self) -> Path | None:
        index = self.file_selector.current()
        if index < 0 or index >= len(self.image_paths):
            return None
        return self.image_paths[index]

    def update_preview(self) -> None:
        path = self._selected_image()
        if path is None:
            return
        try:
            config = self._config()
            image, _metadata = load_image(path)
            rgb = image.convert("RGB")
            box = calculate_mask_box(rgb.width, rgb.height, config)
            marked = rgb.copy()
            draw = ImageDraw.Draw(marked)
            line_width = max(2, round(min(rgb.size) * 0.003))
            draw.rectangle((box.left, box.top, box.right, box.bottom), outline=ERROR, width=line_width)

            import numpy as np

            cleaned_array, _ = clean_array(np.asarray(rgb, dtype=np.uint8), config)
            cleaned = Image.fromarray(cleaned_array)
            self._show_preview(marked, cleaned)
            self.status_var.set(f"Đang xem: {path.name} · {rgb.width}×{rgb.height}")
        except Exception as error:
            messagebox.showerror("Không thể xem thử", str(error))

    def _show_preview(self, original: Image.Image, cleaned: Image.Image) -> None:
        max_size = (390, 380)
        original.thumbnail(max_size, Image.Resampling.LANCZOS)
        cleaned.thumbnail(max_size, Image.Resampling.LANCZOS)
        self.preview_original = ImageTk.PhotoImage(original)
        self.preview_cleaned = ImageTk.PhotoImage(cleaned)
        self.original_label.configure(image=self.preview_original, text="")
        self.cleaned_label.configure(image=self.preview_cleaned, text="")

    def start_processing(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        try:
            if not self.source_var.get().strip():
                raise ValueError("Hãy chọn thư mục ảnh nguồn.")
            if not self.output_var.get().strip():
                raise ValueError("Hãy chọn thư mục kết quả.")
            source = Path(self.source_var.get()).expanduser().resolve()
            output = Path(self.output_var.get()).expanduser().resolve()
            config = self._config()
            config.validate()
            images = collect_images(source, output, self.recursive_var.get())
            if not images:
                raise ValueError("Không có ảnh để xử lý.")
        except Exception as error:
            messagebox.showerror("Chưa thể xử lý", str(error))
            return

        self.cancel_event.clear()
        self.progress_var.set(0)
        self.process_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set(f"Bắt đầu xử lý {len(images)} ảnh…")

        def run() -> None:
            try:
                results = process_batch(
                    source,
                    output,
                    config,
                    self.recursive_var.get(),
                    progress=lambda current, total, path, result: self.events.put(
                        ("progress", (current, total, path, result))
                    ),
                    cancelled=self.cancel_event.is_set,
                )
                self.events.put(("completed", (output, results)))
            except Exception as error:
                self.events.put(("error", str(error)))

        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()

    def cancel_processing(self) -> None:
        self.cancel_event.set()
        self.status_var.set("Đang dừng sau ảnh hiện tại…")

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "progress":
                    current, total, path, result = payload  # type: ignore[misc]
                    self.progress_var.set((current / max(total, 1)) * 100)
                    suffix = "đã xử lý" if result and result.status == "completed" else "có lỗi"
                    self.status_var.set(f"{current}/{total} · {path.name} · {suffix}")
                elif event == "completed":
                    output, results = payload  # type: ignore[misc]
                    completed = sum(item.status == "completed" for item in results)
                    failed = sum(item.status == "failed" for item in results)
                    cancelled = any(item.status == "cancelled" for item in results)
                    self._set_idle()
                    if cancelled:
                        self.status_var.set(f"Đã dừng. Hoàn thành {completed} ảnh, lỗi {failed} ảnh.")
                    else:
                        self.progress_var.set(100)
                        self.status_var.set(f"Hoàn tất {completed} ảnh; lỗi {failed} ảnh. Kết quả: {output}")
                        messagebox.showinfo("Đã hoàn tất", f"Đã xử lý {completed} ảnh.\nLỗi: {failed}\n\n{output}")
                elif event == "error":
                    self._set_idle()
                    messagebox.showerror("Xử lý thất bại", str(payload))
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _set_idle(self) -> None:
        self.process_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

    def open_output(self) -> None:
        path = Path(self.output_var.get()).expanduser()
        if not path.exists():
            messagebox.showinfo("Chưa có kết quả", "Thư mục kết quả chưa được tạo.")
            return
        os.startfile(path)  # type: ignore[attr-defined]


def main() -> None:
    app = LogoCleanerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
