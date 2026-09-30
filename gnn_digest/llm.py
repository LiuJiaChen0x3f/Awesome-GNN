import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from .http import get_json
from .models import content_hash
from .evidence import EvidenceError, validate_evidence_list, fulltext_segments, resolve_evidence_ids
from .summary_policy import validate_method


def validate_summary(value, full_text):
    if not isinstance(value, dict) or type(value.get("relevant")) is not bool:
        raise ValueError("relevant must be a boolean")
    if value.get("confidence") not in ("high", "medium", "low"):
        raise ValueError("invalid confidence")
    keywords, method, evidence = (value.get(k) for k in ("keywords", "method", "evidence"))
    if not isinstance(keywords, list) or not isinstance(method, str):
        raise ValueError("invalid field types")
    if not isinstance(evidence, list):
        raise EvidenceError('evidence_type', 'evidence', 'expected an array, including for irrelevant results')
    if not value["relevant"] or value["confidence"] == "low":
        if method or keywords or evidence:
            raise ValueError("insufficient or irrelevant papers must have empty output")
        return value
    if not 1 <= len(keywords) <= 5:
        raise EvidenceError('keywords_count', 'keywords', f'expected 1-5 items, got {len(keywords)}')
    for i, keyword in enumerate(keywords):
        if not isinstance(keyword, str):
            raise EvidenceError('keyword_type', f'keywords[{i}]', 'expected a short string')
        if not 1 <= len(keyword.strip()) <= 24:
            raise EvidenceError('keyword_length', f'keywords[{i}]',
                                f'expected 1-24 characters, not words; got {len(keyword.strip())}. Use a short Chinese phrase or standard abbreviation')
    if len({k.strip().casefold() for k in keywords}) != len(keywords):
        raise ValueError("keywords must be unique")
    validate_method(method)
    evidence, locations = validate_evidence_list(evidence, full_text)
    return {**value, "keywords": [k.strip() for k in keywords],
            "evidence": evidence, "evidence_locations": locations}


def validate_search_plan(value):
    if not isinstance(value, dict) or not isinstance(value.get("queries"), list):
        raise ValueError("queries must be a list")
    queries = []
    for query in value["queries"]:
        if not isinstance(query, str):
            raise ValueError("query must be a string")
        query = re.sub(r"\s+", " ", query).strip()
        if not 3 <= len(query) <= 100 or len(query.split()) < 2:
            raise ValueError("query must be a meaningful phrase")
        if query.casefold() not in {q.casefold() for q in queries}:
            queries.append(query)
    if not 4 <= len(queries) <= 8:
        raise ValueError("search plan must contain 4-8 unique queries")
    return queries


class Summarizer:
    def __init__(self, config, prompt, extra_validator=None):
        self.config, self.prompt = config, prompt
        self.extra_validator = extra_validator
        self.base = os.getenv("LLM_BASE_URL", "").rstrip("/")
        self.key = os.getenv("LLM_API_KEY", "")
        self.model = os.getenv("LLM_MODEL", "")
        self.reasoning_effort = os.getenv("LLM_REASONING_EFFORT") or config.get("reasoning_effort")
        if not all((self.base, self.key, self.model)):
            raise ValueError("Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL, or use --no-llm")
        parsed = urlparse(self.base)
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")):
            raise ValueError("LLM endpoint must use HTTPS (HTTP allowed only for localhost)")
        base = self.base[:-len('/responses')] if self.base.endswith('/responses') else self.base
        self.endpoint = base if base.endswith("/chat/completions") else base + "/chat/completions"
        self.prompt_hash = hashlib.sha256(('tag-ood-markdown-151-200-v4\n' + prompt).encode()).hexdigest()

    def cached(self, p):
        fulltext_ok = (p.get("full_text") and p.get("fulltext_source", {}).get("scope") == "full_text")
        if self.config.get('require_fulltext', False) and not fulltext_ok:
            return False
        return (p.get("status") in ("ready", "irrelevant", "insufficient") and
                p.get("summary_input_hash") == content_hash(p) and
                p.get("prompt_hash") == self.prompt_hash and p.get("llm_model") == self.model and
                p.get("llm_reasoning_effort") == self.reasoning_effort)

    def summarize(self, p):
        full_text = p.get('full_text', '')
        if not full_text and not self.config.get('require_fulltext', False):
            # Compatibility for direct callers of this low-level class. The
            # production run/search paths set require_fulltext and never use it.
            full_text = p.get('abstract', '')
        if not full_text:
            p.update(status='missing_fulltext', keywords=[], method='')
            return
        segments = fulltext_segments(full_text) if self.config.get('evidence_mode') == 'segments' else []
        document = {'title':p['title']}
        if segments:
            document['full_text_segments'] = [{'id':s['id'], 'text':s['text']} for s in segments]
        else:
            document['full_text'] = full_text
        messages = [{"role": "system", "content": self.prompt}, {"role": "user", "content": json.dumps(document, ensure_ascii=False)}]
        p['validation_errors'] = []
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
                value = json.loads(raw)
                if segments:
                    value = resolve_evidence_ids(value, segments)
                result = validate_summary(value, full_text)
                if self.extra_validator:
                    result = self.extra_validator(result, full_text)
                status = "irrelevant" if not result["relevant"] else "insufficient" if result["confidence"] == "low" else "ready"
                p.update({k: result[k] for k in ("keywords", "method", "confidence", "evidence")})
                p['evidence_locations'] = result.get('evidence_locations', [])
                if self.extra_validator:
                    p.update(topics=result['topics'], topic_evidence=result['topic_evidence'])
                    p['topic_evidence_locations'] = result.get('topic_evidence_locations', {})
                p.update(status=status, summary_input_hash=content_hash(p), prompt_hash=self.prompt_hash, llm_model=self.model, llm_reasoning_effort=self.reasoning_effort, summarized_at=datetime.now(timezone.utc).isoformat())
                if isinstance(response.get("usage"), dict):
                    p["llm_usage"] = {k: v for k, v in response["usage"].items() if k in ("prompt_tokens", "completion_tokens", "total_tokens") and isinstance(v, int)}
                p.pop("error", None)
                p.pop('error_code', None)
                return
            except Exception as error:
                detail = str(error) if isinstance(error, (ValueError, json.JSONDecodeError)) else type(error).__name__
                code = getattr(error, 'code', type(error).__name__)
                p['validation_errors'].append({'attempt':attempt+1, 'code':code,
                    'field':getattr(error, 'field', ''), 'detail':detail[:300]})
                if attempt == self.config["attempts"] - 1:
                    p.update(status="failed", keywords=[], method="", error=detail[:300], error_code=code)
                    return
                time.sleep(min(2 ** attempt, 8))
                # Send schema repair instruction, never expose provider body or credentials.
                if isinstance(raw, str):
                    messages.append({"role": "assistant", "content": raw[:12000]})
                evidence_help = ('证据请返回full_text_segments中已有的片段编号，使用evidence_ids和topic_evidence_ids，不要自己重写长引文。' if segments else '证据请选取全文中较短的连续原句（建议40至120字符），保留大小写、标点、数字，不要加省略号或改写。')
                messages.append({"role": "user", "content": "上次输出未通过校验：" + detail + "。只针对报告的字段纠正，然后输出完整JSON；不要重新检索论文。" + evidence_help + "严格检查1至5个不同关键词（每项最多24字符）、method去掉Markdown标记和空白后必须151至200字符（建议170至190），用**名称**加粗1至4个重点方法或模块。信息不足不要靠泛话凑字数；主题只允许TAG、OOD。"})


class SearchPlanner:
    """Generate bounded source queries; paper metadata never becomes an instruction."""
    def __init__(self, config, prompt):
        self.config = config
        self.prompt = prompt
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

    def plan(self, context):
        messages = [{"role": "system", "content": self.prompt}, {"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
        last_error = None
        for attempt in range(self.config["attempts"]):
            try:
                payload = {"model": self.model, "messages": messages, self.config.get("token_limit_parameter", "max_tokens"): min(self.config.get("max_tokens", 4096), 1200), "response_format": {"type": "json_object"}}
                if self.reasoning_effort:
                    payload["reasoning_effort"] = self.reasoning_effort
                response = get_json(self.endpoint, payload=payload, headers={"Authorization": "Bearer " + self.key}, timeout=self.config["timeout"], attempts=1)
                return validate_search_plan(json.loads(response["choices"][0]["message"]["content"]))
            except Exception as error:
                last_error = error
                if attempt + 1 < self.config["attempts"]:
                    time.sleep(min(2 ** attempt, 8))
        raise ValueError("LLM search plan failed: " + type(last_error).__name__)
