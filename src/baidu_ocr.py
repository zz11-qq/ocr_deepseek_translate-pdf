"""Baidu Intelligent Cloud OCR API client."""

from __future__ import annotations

import base64
from pathlib import Path

import requests

from .utils import format_page_header

TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"


class BaiduOCRError(RuntimeError):
    """Raised when authentication or OCR fails."""


class BaiduOCRClient:
    """Recognize one local image at a time using Baidu accurate basic OCR."""

    def __init__(self, api_key: str, secret_key: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout
        self._access_token: str | None = None
        self.session = requests.Session()

    def get_access_token(self) -> str:
        """Fetch and cache a Baidu OAuth access token."""
        if self._access_token:
            return self._access_token
        try:
            response = self.session.post(
                TOKEN_URL,
                params={
                    "grant_type": "client_credentials",
                    "client_id": self.api_key,
                    "client_secret": self.secret_key,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise BaiduOCRError("获取百度 access_token 网络超时。") from exc
        except (requests.RequestException, ValueError) as exc:
            raise BaiduOCRError(f"获取百度 access_token 失败：{exc}") from exc
        token = data.get("access_token")
        if not token:
            detail = data.get("error_description") or data.get("error") or data
            raise BaiduOCRError(f"获取百度 access_token 失败：{detail}")
        self._access_token = str(token)
        return self._access_token

    def recognize_image(self, image_path: str | Path, page_number: int) -> str:
        """OCR an image and return text prefixed by its page marker."""
        path = Path(image_path)
        try:
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        except OSError as exc:
            raise BaiduOCRError(f"无法读取第 {page_number} 页图片：{exc}") from exc

        try:
            response = self.session.post(
                OCR_URL,
                params={"access_token": self.get_access_token()},
                data={"image": encoded, "detect_direction": "true", "paragraph": "false"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise BaiduOCRError(f"百度 OCR 第 {page_number} 页请求超时。") from exc
        except (requests.RequestException, ValueError) as exc:
            raise BaiduOCRError(f"百度 OCR 第 {page_number} 页请求失败：{exc}") from exc

        if "error_code" in data:
            raise BaiduOCRError(
                f"百度 OCR 第 {page_number} 页返回错误 "
                f"[{data.get('error_code')}] {data.get('error_msg', '未知错误')}"
            )
        words_result = data.get("words_result")
        if not isinstance(words_result, list):
            raise BaiduOCRError(f"百度 OCR 第 {page_number} 页响应缺少 words_result。")
        lines = [str(item.get("words", "")).strip() for item in words_result]
        body = "\n".join(line for line in lines if line)
        return f"{format_page_header(page_number)}\n\n{body}".rstrip()
