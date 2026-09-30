"""Check the real archive and public index without network or model calls."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gnn_digest.storage import read_json
from gnn_digest.models import identity_keys
from gnn_digest.llm import validate_summary
from gnn_digest.agent import validate_topics


def main():
    archive = read_json(ROOT / 'data/papers.json', {})['papers']
    public = read_json(ROOT / 'site/data/papers.json', {})['papers']
    additions = read_json(ROOT / 'data/literature_audit_results.json', {})['results']
    scope = read_json(ROOT / 'data/literature_audit_scope.json', {})['conferences']
    latest = {s['venue_label']: s['selected_year'] for s in scope}
    by_id = {p['id']: p for p in archive}
    assert len(by_id) == len(archive), 'Duplicate persistent IDs'
    identities = set()
    for p in archive:
        keys = identity_keys(p)
        assert not keys & identities, f'Duplicate identity: {p["title"]}'
        identities.update(keys)
    public_ids = {p['id'] for p in public}
    assert len(public_ids) == len(public), 'Duplicate public IDs'
    expected = {p['id'] for p in archive if p.get('status') != 'irrelevant'}
    assert public_ids == expected, 'Export and archive disagree'
    for p in public:
        source = by_id[p['id']]
        assert p['status'] == 'ready', f'Unfinished public record: {p["title"]}'
        assert source.get('full_text') and source.get('fulltext_source', {}).get('scope') == 'full_text'
        value = {'relevant': True, **{k: source[k] for k in ('keywords', 'method', 'confidence', 'evidence', 'topics', 'topic_evidence')}}
        validate_topics(validate_summary(value, source['full_text']), source['full_text'])
        assert p['method'] == source['method'] and p['topics'] == source['topics']
        assert not {'full_text', 'evidence', 'topic_evidence', 'abstract'} & set(p)
        assert p.get('pdf_url') or p.get('sources'), 'No outbound paper link'
    for p in additions:
        assert p['id'] in public_ids
        assert p['conference_year'] == latest[p['venue_label']], 'New paper violates selected latest edition'
    print(f'Validated {len(public)} public cards; {len(additions)} latest-edition additions; unique identities, full-text evidence, 151–200-character methods, TAG/OOD, no private full text in public records.')


if __name__ == '__main__':
    main()
