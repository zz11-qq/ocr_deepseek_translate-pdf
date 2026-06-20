"""Tkinter desktop entry point for PDF OCR and DeepSeek translation."""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.baidu_ocr import BaiduOCRClient
from src.config import AppConfig
from src.deepseek_translator import DeepSeekTranslator
from src.output_writer import OutputWriter
from src.pdf_processor import PDFProcessor
from src.utils import close_logger, join_nonempty, setup_logger, validate_pdf_path


class TranslatorApp:
    """Small responsive GUI that schedules the translation pipeline."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PDF OCR DeepSeek Translator")
        self.root.geometry("760x530")
        self.root.minsize(640, 430)
        self.pdf_path = tk.StringVar()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._build_ui()
        self.root.after(100, self._drain_events)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(4, weight=1)

        ttk.Label(frame, text="PDF OCR DeepSeek Translator", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 14)
        )
        path_frame = ttk.Frame(frame)
        path_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW)
        path_frame.columnconfigure(0, weight=1)
        ttk.Entry(path_frame, textvariable=self.pdf_path).grid(row=0, column=0, sticky=tk.EW, padx=(0, 8))
        self.choose_button = ttk.Button(path_frame, text="选择 PDF", command=self._choose_pdf)
        self.choose_button.grid(row=0, column=1)

        self.start_button = ttk.Button(frame, text="开始处理", command=self._start)
        self.start_button.grid(row=2, column=0, columnspan=2, pady=12)
        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(0, 10))

        log_frame = ttk.LabelFrame(frame, text="运行日志", padding=6)
        log_frame.grid(row=4, column=0, columnspan=2, sticky=tk.NSEW)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

    def _choose_pdf(self) -> None:
        selected = filedialog.askopenfilename(title="选择 PDF", filetypes=[("PDF files", "*.pdf")])
        if selected:
            self.pdf_path.set(selected)

    def _start(self) -> None:
        try:
            pdf_path = validate_pdf_path(self.pdf_path.get())
            config = AppConfig.from_env(Path(__file__).resolve().parent / ".env")
        except Exception as exc:
            self._append_log(f"错误：{exc}")
            messagebox.showerror("无法开始", str(exc))
            return

        self.start_button.configure(state=tk.DISABLED)
        self.choose_button.configure(state=tk.DISABLED)
        self.progress["value"] = 0
        self._append_log(f"开始处理：{pdf_path}")
        threading.Thread(target=self._run_pipeline, args=(pdf_path, config), daemon=True).start()

    def _run_pipeline(self, pdf_path: Path, config: AppConfig) -> None:
        logger: logging.Logger | None = None
        try:
            output_dir = PDFProcessor.create_output_dir(pdf_path)
            logger = setup_logger(output_dir / "run_log.txt", lambda text: self.events.put(("log", text)))
            logger.info("开始时间；PDF 路径：%s", pdf_path)

            processor = PDFProcessor(dpi=config.ocr_render_dpi)
            images = processor.render_pdf(
                pdf_path,
                output_dir,
                lambda current, total: self._progress(0, 35, current, total),
            )
            logger.info("PDF 共 %d 页，渲染完成。", len(images))

            ocr_client = BaiduOCRClient(config.baidu_api_key, config.baidu_secret_key)
            pages: list[str] = []
            for index, image_path in enumerate(images, start=1):
                logger.info("第 %d/%d 页 OCR 开始。", index, len(images))
                pages.append(ocr_client.recognize_image(image_path, index))
                logger.info("第 %d/%d 页 OCR 成功。", index, len(images))
                self._progress(35, 35, index, len(images))
            ocr_text = join_nonempty(pages)

            translator = DeepSeekTranslator(
                api_key=config.deepseek_api_key,
                model=config.deepseek_model,
                base_url=config.deepseek_base_url,
                chunk_size=config.translation_chunk_size,
            )
            translated_text, chunk_count = translator.translate(
                ocr_text,
                lambda current, total: self._progress(70, 25, current, total),
            )
            logger.info("DeepSeek 翻译完成，共 %d 个 Chunk。", chunk_count)

            output_paths = OutputWriter(output_dir).write_all(pdf_path, ocr_text, translated_text)
            for name, path in output_paths.items():
                logger.info("输出文件 %s：%s", name, path)
            logger.info("全部处理完成，输出目录：%s", output_dir)
            self.events.put(("progress", 100.0))
            self.events.put(("done", output_dir))
        except Exception as exc:
            if logger:
                logger.exception("处理失败：%s", exc)
            else:
                self.events.put(("log", f"处理失败：{exc}"))
            self.events.put(("error", str(exc)))
        finally:
            if logger:
                close_logger(logger)

    def _progress(self, offset: float, span: float, current: int, total: int) -> None:
        value = offset + (span * current / max(total, 1))
        self.events.put(("progress", value))

    def _drain_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "log":
                    self._append_log(str(payload))
                elif event == "progress":
                    self.progress["value"] = float(payload)
                elif event == "done":
                    self._set_idle()
                    messagebox.showinfo("处理完成", f"结果已保存到：\n{payload}")
                elif event == "error":
                    self._set_idle()
                    messagebox.showerror("处理失败", str(payload))
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text.rstrip() + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_idle(self) -> None:
        self.start_button.configure(state=tk.NORMAL)
        self.choose_button.configure(state=tk.NORMAL)


def main() -> None:
    """Start the desktop application."""
    root = tk.Tk()
    TranslatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
