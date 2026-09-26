import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from .http import get_json
from .models import content_hash


def validate_summary(value, abstract):
    if not isinstance(value, dict) or type(value.get("relevant")) is not bool:
        raise ValueError("relevant must be a boolean")
    if value.get("confidence") not in ("high", "medium", "low"):
        raise ValueError("invalid confidence")
    keywords, method, evidence = (value.get(k) for k in ("keywords", "method", "evidence"))
    if not isinstance(keywords, list) or not isinstance(method, str) or not isinstance(evidence, list):
        raise ValueError("invalid field types")
    if not value["relevant"] or value["confidence"] == "low":
        if method or keywords or evidence:
            raise ValueError("insufficient or irrelevant papers must have empty output")
        return value
    if len(keywords) != 5 or any(not isinstance(k, str) or not 1 <= len(k.strip()) <= 24 for k in keywords):
        raise ValueError("exactly five short keywords required")
    if len({k.strip().casefold() for k in keywords}) != 5:
        raise ValueError("keywords must be unique")
    if not 1 <= len(method) <= 100 or not re.search(r"[\u4e00-\u9fff]", method):
        raise ValueError("method must be Chinese and 1-100 characters")
    if not 1 <= len(evidence) <= 3 or any(not isinstance(e, str) or not 15 <= len(e) <= 200 or e not in abstract for e in evidence):
        raise ValueError("evidence must be 1-3 verbatim abstract spans")
    return {**value, "keywords": [k.strip() for k in keywords]}


class Summarizer:
    def __init__(self, config, prompt):
        self.config, self.prompt = config, prompt
        self.base = os.getenv("LLM_BASE_URL", "").rstrip("/")
        self.key = os.getenv("LLM_API_KEY", "")
        self.model = os.getenv("LLM_MODEL", "")
        self.reasoning_effort = os.getenv("LLM_REASONING_EFFORT") or config.get("reasoning_effort")
        if not all((self.base, self.key, self.model)):
            raise ValueError("Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL, or use --no-llm")
        parsed = urlparse(self.base)
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")):
            raise ValueError("LLM endpoint must use HTTPS (HTTP allowed only for localhost)")
        self.endpoint = self.base if self.base.endswith("/chat/completions") else self.base + "/chat/completions"
        self.prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()

    def cached(self, p):
        return p.get("status") in ("ready", "irrelevant", "insufficient") and p.get("summary_input_hash") == content_hash(p) and p.get("prompt_hash") == self.prompt_hash and p.get("llm_model") == self.model and p.get("llm_reasoning_effort") == self.reasoning_effort

    def summarize(self, p):
        abstract = p["abstract"][:20000]
        messages = [{"role": "system", "content": self.prompt}, {"role": "user", "content": json.dumps({"title": p["title"], "abstract": abstract}, ensure_ascii=False)}]
        for attempt in range(self.config["attempts"]):
            raw = None
            payload = {"model": self.model, "messages": messages}
            if self.config.get("temperature") is not None:
                payload["temperature"] = self.config["temperature"]
            payload[self.config.get("token_limit_parameter", "max_tokens")] = self.config["max_tokens"]
            if self.reasoning_effort:
                payload["reasoning_effort"] = self.reasoning_effort
            if self.config.get("json_mode", True):
                payload["response_format"] = {"type": "json_object"}
            try:
                response = get_json(self.endpoint, payload=payload, headers={"Authorization": "Bearer " + self.key}, timeout=self.config["timeout"], attempts=1)
                raw = response["choices"][0]["message"]["content"]
                result = validate_summary(json.loads(raw), abstract)
                status = "irrelevant" if not result["relevant"] else "insufficient" if result["confidence"] == "low" else "ready"
                p.update({k: result[k] for k in ("keywords", "method", "confidence", "evidence")})
                p.update(status=status, summary_input_hash=content_hash(p), prompt_hash=self.prompt_hash, llm_model=self.model, llm_reasoning_effort=self.reasoning_effort, summarized_at=datetime.now(timezone.utc).isoformat())
                if isinstance(response.get("usage"), dict):
                    p["llm_usage"] = {k: v for k, v in response["usage"].items() if k in ("prompt_tokens", "completion_tokens", "total_tokens") and isinstance(v, int)}
                p.pop("error", None)
                return
            except Exception as error:
                if attempt == self.config["attempts"] - 1:
                    p.update(status="failed", keywords=[], method="", error=type(error).__name__)
                    return
                time.sleep(min(2 ** attempt, 8))
                # Send schema repair instruction, never expose provider body or credentials.
                if isinstance(raw, str):
                    messages.append({"role": "assistant", "content": raw[:12000]})
                detail = str(error) if isinstance(error, (ValueError, json.JSONDecodeError)) else type(error).__name__
                messages.append({"role": "user", "content": "上次输出或请求未通过校验：" + detail + "。请修正后输出完整JSON。证据必须从输入摘要复制连续原文，不改写、不省略，不加省略号。严格检查五个不同关键词、中文百字限制和字段类型。"})
