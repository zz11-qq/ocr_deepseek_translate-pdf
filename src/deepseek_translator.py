"""Academic translation through DeepSeek's OpenAI-compatible API."""

from __future__ import annotations

import re
import time
from typing import Callable

from openai import OpenAI

from .utils import format_page_header, split_text_by_length

SYSTEM_PROMPT = """你是一名严谨的学术文献翻译助手。请将英文论文内容翻译为简体中文。要求：
1. 保留原文的页码标记；
2. 尽量保留标题、段落、编号、公式符号、引用编号；
3. 不要翻译专有名词中的模型名、方法名、数据集名；
4. 公式、变量、希腊字母、引用如 [1]、(Smith et al., 2020) 原样保留；
5. 不要添加原文没有的解释；
6. 不要输出“以下是翻译”等额外废话，只输出译文。"""

PAGE_PATTERN = re.compile(r"(?m)^===== Page (\d+) =====\s*$")


class DeepSeekTranslationError(RuntimeError):
    """Raised after all DeepSeek request attempts fail."""


class DeepSeekTranslator:
    """Split OCR text page-first and translate chunks in order."""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        chunk_size: int = 2500,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        # Disable SDK-level retries so the explicit loop below is the single
        # source of truth and the total attempt count never exceeds 3 by default.
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=60.0,
            max_retries=0,
        )
        self.model = model
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def build_chunks(self, text: str) -> list[str]:
        """Prefer page boundaries, splitting oversized pages at natural boundaries."""
        matches = list(PAGE_PATTERN.finditer(text))
        if not matches:
            return split_text_by_length(text, self.chunk_size)

        chunks: list[str] = []
        prefix = text[: matches[0].start()].strip()
        if prefix:
            chunks.extend(split_text_by_length(prefix, self.chunk_size))
        for index, match in enumerate(matches):
            page_number = int(match.group(1))
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[match.end() : end].strip()
            header = format_page_header(page_number)
            available = max(1, self.chunk_size - len(header) - 2)
            parts = split_text_by_length(body, available) or [""]
            chunks.extend(f"{header}\n\n{part}".rstrip() for part in parts)
        return chunks

    def translate(
        self,
        text: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[str, int]:
        """Translate every chunk and return joined text plus chunk count."""
        chunks = self.build_chunks(text)
        translated: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            translated.append(self._translate_chunk(chunk, index, len(chunks)))
            if progress_callback:
                progress_callback(index, len(chunks))
        return "\n\n".join(translated), len(chunks)

    def _translate_chunk(self, text: str, index: int, total: int) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": f"请翻译以下 OCR 识别出的论文文本：\n\n{text}",
                        },
                    ],
                    temperature=0.1,
                )
                content = response.choices[0].message.content
                if not content or not content.strip():
                    raise ValueError("API 返回了空译文")
                return content.strip()
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
        raise DeepSeekTranslationError(
            f"DeepSeek 翻译 Chunk {index}/{total} 连续失败 {self.max_retries} 次：{last_error}"
        ) from last_error
