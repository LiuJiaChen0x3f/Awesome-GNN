import argparse
import json
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .llm import SearchPlanner, Summarizer
from .models import candidate, is_ccf_venue, merge_records, within_window
from .sources import FETCHERS
from .storage import export_site, lock, read_json, write_json
from .fulltext import load_fulltext, coerce_legacy_fulltext
from .verification import VerificationError

# Compatibility patch point; the implementation now always reads full text.
load_methods = load_fulltext

ROOT = Path(__file__).resolve().parents[1]


def load_env(path):
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def validate_config(config):
    for name in ("days", "max_per_source", "max_llm_papers"):
        if type(config.get(name)) is not int or config[name] < 1:
            raise ValueError(f"{name} must be a positive integer")
    if "queries" in config and not all(isinstance(q, str) and q.strip() for q in config["queries"]):
        raise ValueError("fallback queries must contain nonempty strings")
    if not config.get("sources") or any(k not in FETCHERS or type(v) is not bool for k, v in config["sources"].items()):
        raise ValueError("invalid sources")
    if not 1 <= config["llm"]["attempts"] <= 5:
        raise ValueError("llm.attempts must be 1-5")
    if type(config.get("llm_concurrency", 1)) is not int or not 1 <= config.get("llm_concurrency", 1) <= 8:
        raise ValueError("llm_concurrency must be 1-8")


def run(args):
    root = Path(args.root).resolve()
    load_env(root / ".env")
    config = read_json(Path(args.config) if args.config else root / "config.json", {})
    validate_config(config)
    if args.command == 'search':
        from .agent import search
        return search(root, config, args)
    state_path = root / "data" / "papers.json"
    with lock(root / "data" / "pipeline.lock"):
        archive = read_json(state_path, {"schema_version": 1, "papers": []})
        papers = archive["papers"]
        if args.command == "build":
            export_site(papers, read_json(root / "data" / "last_run.json", {}), root / "site")
            print(f"Exported {len(papers)} archived papers")
            return 0
        engine = None if args.no_llm else Summarizer({**config["llm"], 'require_fulltext':True}, (root / "prompts" / "summarize.zh.txt").read_text(encoding="utf-8"))
        search_prompt_path = root / "prompts" / "search.en.txt"
        if not search_prompt_path.exists():
            search_prompt_path = ROOT / "prompts" / "search.en.txt"
        planner = None if args.no_llm else SearchPlanner(config["llm"], search_prompt_path.read_text(encoding="utf-8"))
        today = date.fromisoformat(args.until) if args.until else datetime.now(timezone.utc).date()
        days = args.days or config["days"]
        if days < 1:
            raise ValueError("days must be positive")
        since = today - timedelta(days=days-1)
        report = {"started_at": datetime.now(timezone.utc).isoformat(), "window": {"since": str(since), "until": str(today)}, "sources": {}, "llm_enabled": engine is not None}
        queries = list(config.get("queries", []))
        if planner and args.command != "summarize":
            queries = planner.plan({"user_request": "Find recent graph neural network research.", "date_window": {"since": str(since), "until": str(today)}, "ccf_venues": config.get("ccf_venues", []), "fallback_queries": queries})
            report["search_queries"] = queries
            print(json.dumps({"llm_search_queries": queries}, ensure_ascii=False), flush=True)
        fetch_config = dict(config)
        fetch_config["queries"] = queries
        if args.command == "summarize":
            previous = read_json(root / "data" / "last_run.json", {})
            report["sources"] = previous.get("sources", {})
            report["window"] = previous.get("window", report["window"])
            report["collection_started_at"] = previous.get("collection_started_at", previous.get("started_at"))
        fetched = []
        if args.command != "summarize":
            for name, enabled in config["sources"].items():
                if not enabled:
                    continue
                print(f"Fetching {name}...", flush=True)
                try:
                    found, metadata = FETCHERS[name](fetch_config, since, today)
                    eligible = [p for p in found if within_window(p, since, today) and candidate(p, queries)]
                    fetched.extend(eligible)
                    report["sources"][name] = {"ok": True, "fetched": len(found), "candidates": len(eligible), **metadata}
                except Exception as error:
                    report["sources"][name] = {"ok": False, "error": type(error).__name__}
                print(json.dumps({name: report["sources"][name]}, ensure_ascii=False), flush=True)
            if not any(s["ok"] for s in report["sources"].values()):
                report.update(finished_at=datetime.now(timezone.utc).isoformat(), error="All enabled sources failed; archive preserved")
                write_json(root / "data" / "last_run.json", report)
                print(report["error"])
                return 2
        papers = merge_records(papers + fetched)
        for p in papers:
            p["ccf_venue"] = is_ccf_venue(p.get("venue", ""), config.get("ccf_venues", []))
        report["deduplicated"] = len(archive["papers"]) + len(fetched) - len(papers)
        write_json(state_path, {"schema_version": 1, "papers": papers})
        processed = 0
        llm_started = time.monotonic()
        eligible = []
        for p in papers:
            if engine and not engine.cached(p) and p.get("status") in ("ready", "irrelevant", "insufficient"):
                p.update(status="pending", keywords=[], method="")
            if engine and not engine.cached(p):
                eligible.append(p)
        if engine:
            # Workers return copies; only the main thread changes and saves the archive.
            def summarize_copy(p):
                copy = dict(p)
                try:
                    load_methods(copy)
                    coerce_legacy_fulltext(copy)
                    engine.summarize(copy)
                except VerificationError as exc:
                    copy.update(status='missing_fulltext', keywords=[], method='', error=str(exc)[:160])
                return copy
            budget = config["max_llm_papers"]
            queue = iter(eligible[:budget])
            workers = max(1, min(8, config.get("llm_concurrency", 1)))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                pending = {}
                def submit_next():
                    if time.monotonic() - llm_started >= config.get("max_llm_seconds", 1200):
                        return
                    p = next(queue, None)
                    if p is not None:
                        pending[pool.submit(summarize_copy, p)] = p
                for _ in range(workers):
                    submit_next()
                while pending:
                    done, _ = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        p = pending.pop(future)
                        p.update(future.result())
                        processed += 1
                        write_json(state_path, {"schema_version": 1, "papers": papers})
                        print(f"Summarized {processed}/{min(len(eligible), budget)}: {p['id']} {p['status']}", flush=True)
                        submit_next()
        report.update(finished_at=datetime.now(timezone.utc).isoformat(), llm_processed=processed, total=len(papers), statuses=dict(Counter(p["status"] for p in papers)))
        if engine:
            report["llm_remaining"] = sum(not engine.cached(p) for p in papers)
        write_json(state_path, {"schema_version": 1, "papers": papers})
        write_json(root / "data" / "last_run.json", report)
        export_site(papers, report, root / "site")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 3 if any(p["status"] == "failed" for p in papers) and engine else 0


def main():
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description="Discover, deduplicate and summarize GNN papers")
    parser.add_argument("command", choices=("run", "search", "summarize", "build"), nargs="?", default="run")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--config")
    parser.add_argument("--days", type=int)
    parser.add_argument("--conference-days", type=int, help="Override conference start with a lookback")
    parser.add_argument("--arxiv-days", type=int, help="Override arXiv start with a lookback")
    parser.add_argument("--conference-since", help="Conference publication start date, default 2025-01-01")
    parser.add_argument("--arxiv-since", help="arXiv v1 start date; defaults to two calendar months before the cutoff")
    parser.add_argument("--resume", action="store_true", help="Resume the matching bulk checkpoint without repeating completed batches")
    parser.add_argument("--until", help="UTC date YYYY-MM-DD; defaults to actual execution date")
    parser.add_argument("--no-llm", action="store_true", help="Collect metadata without inventing summaries")
    parser.add_argument("--limit", type=int, default=5, help="Target verified papers (1-100); >20 runs a venue/year coverage sweep")
    args = parser.parse_args()
    try:
        if args.limit < 1:
            raise ValueError("limit must be positive")
        return run(args)
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        print(f"Pipeline error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
