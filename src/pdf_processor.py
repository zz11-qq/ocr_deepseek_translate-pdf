"""Render PDF pages to OCR-ready PNG images with PyMuPDF."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import fitz

from .utils import ensure_dir, sanitize_filename, validate_pdf_path

MAX_IMAGE_BYTES = 4 * 1024 * 1024
FALLBACK_DPI = 150


class PDFProcessingError(RuntimeError):
    """Raised when a PDF cannot be opened or rendered."""


class PDFProcessor:
    """Create an output directory and render every PDF page as PNG."""

    def __init__(self, dpi: int = 200, max_image_bytes: int = MAX_IMAGE_BYTES) -> None:
        self.dpi = dpi
        self.max_image_bytes = max_image_bytes

    @staticmethod
    def create_output_dir(pdf_path: Path) -> Path:
        """Create <pdf_stem>_translated_output beside the source PDF."""
        folder_name = f"{sanitize_filename(pdf_path.stem)}_translated_output"
        return ensure_dir(pdf_path.parent / folder_name)

    def render_pdf(
        self,
        pdf_path: str | Path,
        output_dir: Path | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[Path]:
        """Render pages and return image paths in source order."""
        source = validate_pdf_path(pdf_path)
        destination = output_dir or self.create_output_dir(source)
        images_dir = ensure_dir(destination / "images")
        image_paths: list[Path] = []

        try:
            document = fitz.open(str(source))
        except Exception as exc:
            raise PDFProcessingError(f"无法打开 PDF：{exc}") from exc

        try:
            if document.page_count == 0:
                raise PDFProcessingError("PDF 没有可处理的页面。")
            for index in range(document.page_count):
                image_path = images_dir / f"page_{index + 1:03d}.png"
                try:
                    page = document.load_page(index)
                    self._render_page(page, image_path, self.dpi)
                    if image_path.stat().st_size > self.max_image_bytes and self.dpi > FALLBACK_DPI:
                        self._render_page(page, image_path, FALLBACK_DPI)
                    size = image_path.stat().st_size
                    if size > self.max_image_bytes:
                        raise PDFProcessingError(
                            f"第 {index + 1} 页在 {FALLBACK_DPI} DPI 下仍有 {size / 1024 / 1024:.2f} MB，"
                            f"超过 {self.max_image_bytes / 1024 / 1024:.0f} MB 限制。"
                        )
                except PDFProcessingError:
                    raise
                except Exception as exc:
                    raise PDFProcessingError(f"PDF 第 {index + 1} 页渲染失败：{exc}") from exc
                image_paths.append(image_path)
                if progress_callback:
                    progress_callback(index + 1, document.page_count)
        finally:
            document.close()
        return image_paths

    @staticmethod
    def _render_page(page: fitz.Page, path: Path, dpi: int) -> None:
        zoom = dpi / 72
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pixmap.save(path)
