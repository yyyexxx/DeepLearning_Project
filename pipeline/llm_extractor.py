"""LLM 信息抽取。多后端适配器，支持 DashScope / OpenAI / Claude / DeepSeek。"""

import json
import re
from typing import Optional

import requests

from config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_MODEL,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    DEEPSEEK_API_KEY,
    LLM_TIMEOUT,
)


EXTRACTION_PROMPT = """你是一个专业的财务发票信息提取助手。请从以下OCR识别文字和发票图片中，提取增值税发票的关键字段。

OCR 识别文字：
{ocr_text}

请严格按以下 JSON 格式返回，找不到的字段用 null：
{{
  "invoice_code": "发票代码",
  "invoice_number": "发票号码",
  "invoice_date": "开票日期(YYYY-MM-DD)",
  "purchaser": "购买方名称",
  "seller": "销售方名称",
  "amount": "不含税金额(数字)",
  "tax": "税额(数字)",
  "total": "价税合计(数字)"
}}

只返回 JSON，不要其他内容。"""


def extract_with_llm(ocr_results: list[tuple[str, float]], image_path: str) -> dict:
    """主入口：根据 LLM_BACKEND 配置选择后端提取。"""
    from config import LLM_BACKEND

    ocr_text = "\n".join([text for text, _ in ocr_results])
    prompt = EXTRACTION_PROMPT.format(ocr_text=ocr_text)

    backends = {
        "dashscope": _extract_dashscope,
        "openai": _extract_openai,
        "anthropic": _extract_anthropic,
        "deepseek": _extract_deepseek,
    }

    fn = backends.get(LLM_BACKEND)
    if fn is None:
        raise ValueError(f"未知的 LLM_BACKEND: {LLM_BACKEND}")

    return fn(prompt, image_path)


def _parse_json_response(text: str) -> dict:
    """从 LLM 返回中提取 JSON。"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试匹配 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试匹配 { ... }
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {}


# ── 各后端实现 ─────────────────────────────────────────────


def _extract_dashscope(prompt: str, image_path: str) -> dict:
    """通义千问 DashScope 多模态 API。"""
    import dashscope
    from dashscope import MultiModalConversation

    dashscope.api_key = DASHSCOPE_API_KEY

    with open(image_path, "rb") as f:
        import base64
        image_b64 = base64.b64encode(f.read()).decode()

    messages = [{
        "role": "user",
        "content": [
            {"image": f"data:image/png;base64,{image_b64}"},
            {"text": prompt},
        ],
    }]

    response = MultiModalConversation.call(
        model=DASHSCOPE_MODEL,
        messages=messages,
    )

    if response.status_code != 200:
        raise RuntimeError(f"DashScope API 错误: {response.message}")

    text = response.output.choices[0].message.content[0].get("text", "")
    return _parse_json_response(text)


def _extract_openai(prompt: str, image_path: str) -> dict:
    """OpenAI GPT-4o 多模态 API。"""
    import base64

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4o",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
        },
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return _parse_json_response(data["choices"][0]["message"]["content"])


def _extract_anthropic(prompt: str, image_path: str) -> dict:
    """Anthropic Claude 多模态 API。"""
    import base64

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 1024,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        },
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return _parse_json_response(data["content"][0]["text"])


def _extract_deepseek(prompt: str, image_path: str) -> dict:
    """DeepSeek API（使用 OpenAI 兼容接口）。"""
    import base64

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    resp = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
        },
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return _parse_json_response(data["choices"][0]["message"]["content"])
