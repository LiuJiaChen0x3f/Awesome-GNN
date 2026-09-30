"""Locate quotations in supplied text; tolerate whitespace, never paraphrases."""
import re


class EvidenceError(ValueError):
    def __init__(self, code, field, detail):
        self.code, self.field = code, field
        super().__init__(f'{field}: {code}; {detail}')


def locate_evidence(quote, full_text, field):
    if not isinstance(quote, str):
        raise EvidenceError('evidence_type', field, 'expected a string copied from full_text')
    normalized = ' '.join(quote.split())
    if not 15 <= len(normalized) <= 200:
        raise EvidenceError('evidence_length', field,
                            f'expected 15-200 characters after whitespace normalization, got {len(normalized)}')
    start = full_text.find(quote) if quote else -1
    if start >= 0 and len(quote) <= 200:
        return quote, {'start':start, 'end':start+len(quote)}
    # Keep a source offset for every normalized character so the saved evidence
    # is the actual continuous source span, including original line breaks.
    chunks, offsets = [], []
    for match in re.finditer(r'\S+', full_text):
        if chunks:
            chunks.append(' ')
            offsets.append(match.start()-1)
        chunks.append(match.group())
        offsets.extend(range(match.start(), match.end()))
    start = ''.join(chunks).find(normalized)
    if start < 0:
        raise EvidenceError('evidence_not_found', field,
                            'not found in full_text; copy one continuous passage without translation, ellipsis or changed punctuation')
    left, right = offsets[start], offsets[start+len(normalized)-1]+1
    if right-left > 200:
        raise EvidenceError('evidence_length', field,
                            'matched source span exceeds 200 characters; choose a shorter passage')
    return full_text[left:right], {'start':left, 'end':right}


def validate_evidence_list(value, full_text):
    if not isinstance(value, list):
        raise EvidenceError('evidence_type', 'evidence', 'expected an array')
    if not 1 <= len(value) <= 3:
        raise EvidenceError('evidence_count', 'evidence', f'expected 1-3 passages, got {len(value)}')
    matches = [locate_evidence(q, full_text, f'evidence[{i}]') for i,q in enumerate(value)]
    return [m[0] for m in matches], [m[1] for m in matches]


def fulltext_segments(text, size=180):
    """Partition the ENTIRE text into addressable, continuous source spans."""
    segments, start = [], 0
    while start < len(text):
        end = min(len(text), start+size)
        if end < len(text):
            # Avoid splitting words where possible; retain all whitespace.
            boundary = max(text.rfind(' ', start+size//2, end),
                           text.rfind('\n', start+size//2, end))
            if boundary >= 0:
                end = boundary+1
        segments.append({'id':f'S{len(segments)+1:04d}', 'text':text[start:end],
                         'start':start, 'end':end})
        start = end
    return segments


def resolve_evidence_ids(value, segments):
    """IDs select original text; a fabricated ID or supplied quote earns no trust."""
    if not isinstance(value, dict):
        return value
    by_id = {s['id']:s['text'] for s in segments}
    def resolve(ref, field):
        if not isinstance(ref, str) or ref not in by_id:
            raise EvidenceError('evidence_id_unknown', field, 'choose an existing full_text_segments id')
        return by_id[ref]
    result = dict(value)
    if 'evidence_ids' in value:
        refs = value['evidence_ids']
        if not isinstance(refs, list):
            raise EvidenceError('evidence_type', 'evidence_ids', 'expected an array of segment IDs')
        result['evidence'] = [resolve(ref, f'evidence_ids[{i}]') for i,ref in enumerate(refs)]
    if 'topic_evidence_ids' in value:
        refs = value['topic_evidence_ids']
        if not isinstance(refs, dict):
            raise EvidenceError('evidence_type', 'topic_evidence_ids', 'expected topic-to-segment-ID object')
        result['topic_evidence'] = {t:resolve(ref, f'topic_evidence_ids.{t}') for t,ref in refs.items()}
    return result
