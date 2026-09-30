"""Render coverage from actual cached IDs and outcomes, without API requests."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gnn_digest.storage import read_json, write_json
from gnn_digest.models import identity_keys


def successful_reviews(folder, candidates):
    primary, extra, gaps = set(), set(), set()
    for path in (folder / 'latest-title-screen').glob('*.json'):
        batch = read_json(path, {})
        if not batch.get('error'):
            primary.update(batch.get('ids', []))
    for dirname, destination in [('extra-title-screen', extra), ('gap-title-screen', gaps)]:
        for path in (folder / dirname).glob('*.json'):
            batch = read_json(path, {})
            if not batch.get('error'):
                destination.update(batch.get('reviewed_ids', []))
    return {i for i, c in enumerate(candidates) if c.get('catalog_id') in primary} | extra | gaps


def main():
    folder = ROOT / '.local/literature-audit'
    scope = read_json(ROOT / 'data/literature_audit_scope.json', {})
    candidates = read_json(ROOT / 'data/latest_literature_candidates.json', {})['candidates']
    latest = {c['venue_label']: c['selected_year'] for c in scope['conferences']}
    eligible = {i for i, c in enumerate(candidates) if c['year'] == latest.get(c['venue_label'])}
    reviewed = successful_reviews(folder, candidates) & eligible
    existing = {i for i in eligible if candidates[i].get('existing_id')}
    holes = eligible - reviewed - existing
    outcomes = [read_json(p, {}) for p in (folder / 'outcomes').glob('*.json')]
    public = read_json(ROOT / 'site/data/papers.json', {})['papers']
    report = read_json(ROOT / 'data/literature_audit_report.json', {})
    added = read_json(ROOT / 'data/literature_audit_results.json', {})['results']
    baseline = read_json(folder / 'archive-before-audit.json', {})['papers']
    baseline_keys = set().union(*(identity_keys(p) for p in baseline))
    archive = read_json(ROOT / 'data/papers.json', {})['papers']
    actual_new = [p for p in archive if not identity_keys(p) & baseline_keys and p.get('status') == 'ready']
    assert len(actual_new) == len(added), 'Report additions disagree with persistent archive identities'
    pending = []
    for path in (folder / 'outcomes').glob('*.json'):
        o = read_json(path, {})
        if o['status'] not in {'metadata_unresolved', 'fulltext_unresolved', 'summary_request_failed', 'summary_validation_failed', 'fulltext_prepared'}:
            continue
        if o['year'] != latest.get(o['venue']):
            continue
        p = read_json(folder / 'papers' / path.name, {})
        pending.append({
            'cache_key': path.stem, 'title': o['title'], 'venue': o['venue'], 'year': o['year'],
            'status': o['status'], 'error': o.get('error'), 'errors': o.get('errors', []),
            'pdf_url': p.get('pdf_url'), 'verified_source': p.get('verification', {}).get('url'),
            'discovery': o.get('discovery', {}),
        })
    pending.sort(key=lambda p: (p['status'], p['venue'], p['title']))
    coverage = {
        'generated_at': datetime.now(timezone.utc).isoformat(), 'coverage_complete': False,
        'source_union_entries': len(candidates), 'eligible_latest_entries': len(eligible),
        'successful_title_review_entries': len(reviewed),
        'already_archived_without_additional_title_review': len(existing - reviewed),
        'unreviewed_entries': [{'union_id': i, **candidates[i]} for i in sorted(holes)],
        'separate_emnlp_2026_candidates': len(read_json(ROOT / 'data/emnlp_2026_import_manifest.json', {})['candidates']),
        'status_counts': dict(Counter(o['status'] for o in outcomes)),
        'pending_count': len(pending), 'new_ready_papers': len(actual_new), 'public_total': len(public),
    }
    write_json(ROOT / 'data/literature_coverage_check.json', coverage)
    write_json(ROOT / 'data/literature_pending.json', {'updated_at': coverage['generated_at'], 'papers': pending})
    rows = []
    for s in sorted(scope['conferences'], key=lambda x: x['venue_label']):
        venue, year = s['venue_label'], s['selected_year']
        fresh = sum(p['venue_label'] == venue and p['conference_year'] == year for p in added)
        total = sum(p.get('venue_label') == venue and p.get('conference_year') == year for p in public) if year else 0
        waiting = sum(p['venue'] == venue and p['year'] == year for p in pending)
        status = {'latest_list_unresolved': '最新名单待核验', 'provisional_2025_fallback': '2025 暂作回退，2026 仍待确认', 'verified_edition': '已核验该届论文来源'}[s['selection_status']]
        rows.append(f'| {venue} | {year or "待确认"} | {fresh} | {total} | {waiting} | {status} |')
    lines = [
        '# TAG / OOD 最新会议论文覆盖审计', '',
        f'核查基准日：{scope["as_of"]}。报告生成：{coverage["generated_at"]}。', '',
        f'本轮去重后新增 **{len(actual_new)} 篇**，本地公开索引合计 **{len(public)} 篇**。',
        '这是有来源证据的补漏结果，不是“已收齐全部相关论文”的声明。未获得全文、名单访问失败和审核失败均保留为待处理项。', '',
        '## 范围和取舍', '',
        '- 每个会议独立选择最新公开可核验届次：有 2026 就用 2026，否则核查 2025。访问失败不能证明 2026 尚未公布。',
        '- 保留原有 113 篇公开记录；本轮新增执行最新届次规则，没有擅自删除之前收录的旧届论文。',
        '- 范围扩展至 ICLR、LoG、ICDM、WSDM、NAACL。仅主会，排除 Findings、workshop、非主会/尚未核验的投稿。',
        '- TAG/OOD 必须是论文实际方法或实验设置。仅背景提及、普通归纳划分、训练客户端 Non-IID 不足以认定 OOD。',
        '- 每篇卡片有完整正文输入、151–200 可见字符方法总结、1–4 处方法加粗、1–5 个内部关键词和可定位全文证据；网页只展示 TAG/OOD 主题。', '',
        '## 各会议结果', '',
        '“页面该届”包含之前已收录的相同届次；“待处理”是候选数，不是已确认相关论文数。', '',
        '| 会议 | 本轮届次 | 新增 | 页面该届 | 待处理 | 届次证据状态 |',
        '|---|---:|---:|---:|---:|---|', *rows, '',
        '## 发现与筛选覆盖', '',
        '- 参考仓库完整 Git tree 未截断；读取了 25 个 2025/2026 索引，共 3,598 条目录记录。结合官网、出版方元数据形成独立候选集。',
        f'- 合并候选集 {len(candidates)} 条，其中符合最终届次的 {len(eligible)} 条；按真实候选 ID 统计成功初筛 {len(reviewed)} 条，另有 {len(existing-reviewed)} 条已在原库，无成功初筛且不在原库的 {len(holes)} 条。',
        '- 初筛是高召回候选选择，不是全文排除证明；题名未明显表达 TAG/OOD 的论文仍可能漏检。',
        '- EMNLP 2026 独立处理：官方公开日程含 2,710 个 MAIN 条目，提取并核验 85 个图相关题名；该计数不混入前面的历史索引 ID。',
        '- 修正了额外初筛缓存的批次编号漂移：覆盖率按成功 reviewed_ids 的并集计算；补审缓存以输入内容哈希命名，不再通过批次数推断覆盖率。', '',
        '## 仍然存在的缺口', '',
        '- LoG 2026 有录用公布线索，但官方 OpenReview 名单/轨道尚未完整取得，API 返回 403。本轮不将 LoG 2025 冒充已确认的最新届次。',
        '- NeurIPS 2026 官网目录返回 403，尚未取得完整公开名单；2025 作为可核验回退。ACM MM / ICDM 的 2026 公开论文集也未完成确认，不能断言不存在。',
        '- EMNLP 2026 多数题名尚未定位到可核对的完整正文；两篇原有 arXiv 记录已根据官方 MAIN 名单补充会议归属，不重复新增。',
        '- ECCV 2026 未在参考仓库快照中发现相应索引，官网请求发生 SSL 错误；记录为范围缺口，不宣称已覆盖。',
        '- 出版方/OpenReview PDF 返回访问错误、无可匹配全文，以及超出 PDF 安全大小限制的候选仍未上架；不能使用相似题名替代。',
        f'- 当前仍有 {coverage["status_counts"].get("summary_request_failed", 0)} 篇完整正文因模型请求失败待总结；失败以网络超时为主。此前恢复探针官网和模型均返回 200，但不能保证持续可达。', '',
        '## 可复核文件与恢复', '',
        '- `data/literature_audit_scope.json`：有效届次和证据限制。',
        '- `data/literature_audit_results.json`：新增论文题名、会议、总结和 PDF。',
        '- `data/literature_coverage_check.json`：实际成功审核 ID 的覆盖核算。',
        '- `data/literature_pending.json`：所有未解决候选、错误及原站线索。',
        '- `.local/literature-audit/`：本机全文缓存、失败历史、修订前记录；不进入公开网页。', '',
        '```powershell',
        '# 只恢复已有全文的总结，连续请求失败会停止；会调用本机配置的 API',
        'python -X utf8 scripts/summarize_literature_candidates.py --retry-failed --limit 150',
        '# 仅核验并导出已完成结果，不调用模型',
        'python -X utf8 scripts/publish_literature_audit.py --final',
        'python -X utf8 scripts/report_literature_audit.py',
        '```', '',
        '本轮更新在本地；未提交或推送 GitHub。最终结果须以最后一次导出后的数字为准。', '',
        '## 主要来源', '',
        '- https://github.com/naganandy/graph-based-deep-learning-literature/tree/master',
        *[f'- {s["venue_label"]}: {s["source_url"]}' for s in scope['conferences'] if s.get('source_url')], '',
    ]
    (ROOT / 'docs/latest_conference_coverage_audit.md').write_text('\n'.join(lines), encoding='utf-8')
    print({k: coverage[k] for k in ('new_ready_papers', 'public_total', 'successful_title_review_entries', 'pending_count')})


if __name__ == '__main__':
    main()
