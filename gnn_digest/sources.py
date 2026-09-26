import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

from .http import get_json, request
from .models import arxiv_id, clean, paper
from .vendor.arxiv_rss import _clean_abstract, _extract_arxiv_id, _parse_authors

ATOM = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}


def arxiv(config, since, until):
    query = "(" + " OR ".join('all:"' + q.replace('"', '') + '"' for q in config["queries"]) + ")"
    query += f" AND lastUpdatedDate:[{since:%Y%m%d}0000 TO {until:%Y%m%d}2359]"
    papers = []
    limit = config["max_per_source"]
    try:
        for start in range(0, limit, 100):
            if start:
                time.sleep(3.1)
            params = {"search_query": query, "start": start, "max_results": min(100, limit-start), "sortBy": "lastUpdatedDate", "sortOrder": "descending"}
            root = ET.fromstring(request("https://export.arxiv.org/api/query?" + urlencode(params)))
            entries = root.findall("a:entry", ATOM)
            for entry in entries:
                url = entry.findtext("a:id", "", ATOM)
                aid = arxiv_id(url)
                if not aid:
                    raise ValueError("arXiv returned an error entry")
                papers.append(paper(source="arxiv", source_id=aid, title=entry.findtext("a:title", "", ATOM), abstract=entry.findtext("a:summary", "", ATOM), authors=[a.findtext("a:name", "", ATOM) for a in entry.findall("a:author", ATOM)], published=entry.findtext("a:published", "", ATOM), updated=entry.findtext("a:updated", "", ATOM), doi=entry.findtext("x:doi", "", ATOM), arxiv=aid, url=f"https://arxiv.org/abs/{aid}", publication_type="preprint"))
            if len(entries) < params["max_results"]:
                break
        return papers, {"mode": "api", "truncated": len(papers) >= limit}
    except Exception as error:
        # RSS only covers latest announcements. Never claim a complete date backfill.
        reason = type(error).__name__
    successes, failures = 0, 0
    for category in config["arxiv_categories"]:
        try:
            root = ET.fromstring(request("https://rss.arxiv.org/rss/" + category, attempts=2))
            successes += 1
            channel_date = root.findtext("channel/lastBuildDate") or root.findtext("channel/pubDate")
            for item in root.findall("channel/item"):
                aid = _extract_arxiv_id(item)
                if not aid:
                    continue
                raw_date = item.findtext("pubDate") or channel_date
                stamp = parsedate_to_datetime(raw_date).date().isoformat() if raw_date else ""
                papers.append(paper(source="arxiv", source_id=aid, title=item.findtext("title", ""), abstract=_clean_abstract(item.findtext("description", "")), authors=_parse_authors(item), published=stamp, arxiv=aid, url=f"https://arxiv.org/abs/{aid}", publication_type="preprint", date_basis="rss_announcement"))
        except Exception:
            failures += 1
        time.sleep(3.1)
    if not successes and not papers:
        raise RuntimeError("arXiv API and RSS unavailable")
    return papers, {"mode": "rss_fallback", "warning": f"API {reason}; RSS cannot backfill full window", "failed_feeds": failures, "truncated": False}


def crossref(config, since, until):
    papers, truncated = [], False
    remaining = config["max_per_source"]
    per_query = max(1, remaining // len(config["queries"]))
    for query in config["queries"]:
        if remaining <= 0:
            break
        rows = min(per_query, remaining, 1000)
        base_filter = f"from-pub-date:{since},until-pub-date:{until}"
        batches = [("proceedings-article", max(1, rows * 2 // 3)), (None, rows - max(1, rows * 2 // 3))]
        for type_filter, batch_rows in batches:
            if batch_rows <= 0:
                continue
            filter_value = base_filter + (f",type:{type_filter}" if type_filter else "")
            params = {"query": query, "filter": filter_value, "sort": "published", "order": "desc", "rows": batch_rows}
            if os.getenv("CONTACT_EMAIL"):
                params["mailto"] = os.environ["CONTACT_EMAIL"]
            data = get_json("https://api.crossref.org/works?" + urlencode(params))["message"]
            truncated |= data.get("total-results", 0) > batch_rows
            for item in data["items"]:
                parts = item.get("published", {}).get("date-parts", [[]])[0]
                stamp = "-".join(str(x).zfill(4 if i == 0 else 2) for i, x in enumerate((parts+[1, 1])[:3])) if parts else ""
                item_type = item.get("type", "")
                venue = " ".join(item.get("container-title", []))
                landing = item.get("URL") or ("https://doi.org/" + item["DOI"])
                papers.append(paper(source="crossref", source_id=item["DOI"], doi=item["DOI"], title=" ".join(item.get("title", [])), abstract=item.get("abstract", ""), authors=[clean(a.get("given", "") + " " + a.get("family", "")) for a in item.get("author", [])], published=stamp, url=landing, venue=venue, publication_type="conference" if item_type == "proceedings-article" else "journal" if item_type == "journal-article" else item_type))
        remaining -= len(data["items"])
        time.sleep(1)
    return papers, {"mode": "api", "truncated": truncated}


def reconstruct_abstract(index):
    positions = {pos: word for word, indexes in (index or {}).items() for pos in indexes}
    return " ".join(positions[pos] for pos in sorted(positions))


def openalex(config, since, until):
    key = os.getenv("OPENALEX_API_KEY")
    if not key:
        raise ValueError("OPENALEX_API_KEY missing")
    papers, truncated = [], False
    budget = config["max_per_source"]
    per_query = max(1, budget // len(config["queries"]))
    for query in config["queries"]:
        remaining, cursor = min(per_query, budget-len(papers)), "*"
        while remaining > 0:
            params = {"search": query, "filter": f"from_publication_date:{since},to_publication_date:{until}", "sort": "publication_date:desc", "per_page": min(remaining, 100), "cursor": cursor}
            data = get_json("https://api.openalex.org/works?" + urlencode(params), headers={"Authorization": "Bearer " + key})
            truncated |= data.get("meta", {}).get("count", 0) > per_query
            for item in data["results"]:
                location = item.get("primary_location") or {}
                url = location.get("landing_page_url") or item.get("doi") or item["id"]
                papers.append(paper(source="openalex", source_id=item["id"], doi=item.get("doi"), arxiv=url if "arxiv.org" in url else "", title=item.get("title") or "", abstract=reconstruct_abstract(item.get("abstract_inverted_index")), authors=[a["author"]["display_name"] for a in item.get("authorships", [])], published=item.get("publication_date", ""), url=url))
            remaining -= len(data["results"])
            cursor = data.get("meta", {}).get("next_cursor")
            if not cursor or not data["results"]:
                break
            time.sleep(1)
    return papers, {"mode": "api", "truncated": truncated}


FETCHERS = {"arxiv": arxiv, "crossref": crossref, "openalex": openalex}
