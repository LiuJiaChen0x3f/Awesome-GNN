import hashlib
import html
import re
import unicodedata
from datetime import date
from urllib.parse import unquote


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()


def norm_title(value):
    return "".join(c for c in unicodedata.normalize("NFKC", value).casefold() if c.isalnum())


def norm_doi(value):
    value = unquote(str(value or "")).strip().lower()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value)
    return value if value.startswith("10.") and "/" in value else ""


def arxiv_id(value):
    match = re.search(r"(?:arxiv:|arxiv\.org/(?:abs|pdf)/)?((?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7}))(?:v\d+)?", str(value or ""), re.I)
    return match.group(1).lower() if match else ""


def paper(*, source, source_id, title, abstract="", authors=None, published="", updated="", url="", doi="", arxiv="", venue="", publication_type="", date_basis="publication"):
    title = clean(title)
    return {
        "id": "p-" + hashlib.sha256(f"{source}:{source_id}".encode()).hexdigest()[:20],
        "title": title, "abstract": clean(abstract), "authors": authors or [],
        "published": published[:10], "updated": (updated or published)[:10],
        "doi": norm_doi(doi), "arxiv_id": arxiv_id(arxiv),
        "venue": clean(venue), "publication_type": clean(publication_type),
        "sources": [{"name": source, "id": str(source_id), "url": url, "date_basis": date_basis}],
        "status": "pending", "keywords": [], "method": "",
    }


def identity_keys(p):
    keys = set(p.get("identity_aliases", []))
    keys.update(f"source:{s['name']}:{s['id']}" for s in p["sources"])
    if p.get("doi"):
        keys.add("doi:" + norm_doi(p["doi"]))
    if p.get("arxiv_id"):
        keys.add("arxiv:" + arxiv_id(p["arxiv_id"]))
    title = norm_title(p["title"])
    if title:
        keys.add("title:" + title)
    return keys


def content_hash(p):
    return hashlib.sha256((p["title"] + "\n" + p["abstract"] +
                          ("\n" + p['full_text'] if p.get('full_text') else '')).encode()).hexdigest()


def merge_records(records):
    """Transitive union by DOI, versionless arXiv ID, source ID or normalized title."""
    groups, index = {}, {}
    for incoming in records:
        keys = identity_keys(incoming)
        matched = sorted({index[k] for k in keys if k in index})
        root = matched[0] if matched else len(records) + len(groups)
        if not matched:
            while root in groups:
                root += 1
        members = []
        for group_id in matched:
            members.extend(groups.pop(group_id))
        members.append(incoming)
        groups[root] = members
        for member in members:
            for key in identity_keys(member):
                index[key] = root
    result = []
    for members in groups.values():
        # Keep an already persisted ID and a stable ordering of provenance.
        merged = dict(members[0])
        # Do not carry the pre-full-text method-only cache into new records.
        merged.pop('method_text', None)
        with_abstract = [p for p in members if p.get("abstract")]
        richest = max(with_abstract or members, key=lambda p: (p.get("updated", ""), len(p.get("abstract", ""))))
        for field in ("abstract", "title", "authors"):
            merged[field] = richest[field] or merged.get(field, "")
        for field in ("doi", "arxiv_id"):
            merged[field] = next((p[field] for p in members if p.get(field)), "")
        merged["venue"] = next((p.get("venue", "") for p in members if p.get("venue")), "")
        merged["publication_type"] = next((p.get("publication_type", "") for p in members if p.get("publication_type")), "")
        dates = [p["published"] for p in members if p.get("published")]
        merged["published"] = min(dates, default="")
        merged["updated"] = max((p.get("updated", "") for p in members), default="")
        provenance = {(s["name"], s["id"]): s for p in members for s in p["sources"]}
        merged["sources"] = list(provenance.values())
        merged["identity_aliases"] = sorted({key for p in members for key in identity_keys(p)})
        verified = [p for p in members if p.get('verification')]
        if verified:
            events = {(e['date'], e['basis'], e['url']):e for p in verified for e in p.get('publication_events', [])}
            merged['publication_events'] = list(events.values())
            # Prefer the newly fetched record when the original publication date ties.
            recent = max(reversed(verified), key=lambda p:p.get('display_date', p['published']))
            for field in ('display_date','date_basis','verification','pdf_url'):
                if field in recent:
                    merged[field] = recent[field]
            conference = next((p for p in verified if p.get('venue_label') not in (None, '', 'arXiv')), None)
            merged['venue_label'] = conference['venue_label'] if conference else 'arXiv'
            merged['venue'] = conference['venue_label'] if conference else ''
            merged['ccf_venue'] = conference is not None
            # Prefer newly verified text, not stale richer descriptions from older sources.
            for field in ('title','abstract','authors','full_text','fulltext_source','conference_evidence'):
                if field in recent:
                    merged[field] = recent[field]
        # A newly verified route can arrive before a previously downloaded
        # full text. Preserve that text when the identity is merged, but never
        # revive a historical method-section-only field.
        fulltext = next((p for p in reversed(members)
                         if p.get('full_text') and
                         p.get('fulltext_source', {}).get('scope') == 'full_text'), None)
        if fulltext:
            merged['full_text'] = fulltext['full_text']
            merged['fulltext_source'] = fulltext['fulltext_source']
        # Reuse valid summaries even when merging an additional source.
        valid = next((p for p in reversed(members) if p.get("summary_input_hash") == content_hash(merged)), None)
        if valid:
            for field in ("status", "keywords", "method", "confidence", "evidence", "summary_input_hash", "prompt_hash", "llm_model", "llm_reasoning_effort", "llm_usage", "summarized_at", "topics", "topic_evidence"):
                if field in valid:
                    merged[field] = valid[field]
        elif merged.get("summary_input_hash"):
            merged.update(status="pending", keywords=[], method="")
        result.append(merged)
    return sorted(result, key=lambda p: (p.get("published", ""), p["id"]), reverse=True)


def within_window(p, since, until):
    try:
        return since <= date.fromisoformat(p["updated"] or p["published"]) <= until
    except (KeyError, ValueError):
        return False


def candidate(p, queries):
    text = (p["title"] + " " + p["abstract"]).casefold()
    return any(q.casefold() in text for q in queries) or bool(re.search(r"\bgnns?\b", text))


def is_ccf_venue(venue, names):
    if not venue:
        return False
    return any(re.search(r"(?<![a-z0-9])" + re.escape(name.casefold()) + r"(?![a-z0-9])", venue.casefold()) for name in names)
