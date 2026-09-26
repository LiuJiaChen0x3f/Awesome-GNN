import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError(f"Another run may be active; inspect {path} before removing a stale lock") from None
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)


def export_site(papers, report, directory):
    # Abstracts/evidence stay in the research archive; only compact summaries go public.
    fields = ("id", "title", "authors", "published", "updated", "sources", "status", "keywords", "method", "confidence", "summarized_at")
    public = [{key: p[key] for key in fields if key in p} for p in papers if p.get("status") != "irrelevant"]
    write_json(directory / "data" / "papers.json", {"schema_version": 1, "generated_at": report.get("finished_at"), "report": report, "papers": public})
