"""Canonical identifier normalization."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse, urlunparse


def normalize_doi(doi: str) -> str:
    d = doi.strip().lower()
    d = d.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    d = d.removeprefix("doi:")
    return f"doi:{d}"


def normalize_arxiv(arxiv_id: str) -> str:
    a = arxiv_id.strip().lower()
    a = a.removeprefix("arxiv:")
    a = re.sub(r"v\d+$", "", a)
    return f"arxiv:{a}"


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    query = parse_qs(parsed.query, keep_blank_values=True)
    clean_query = "&".join(f"{k}={query[k][0]}" for k in sorted(query))
    return urlunparse((scheme, netloc, path, "", clean_query, ""))


def normalize_repo_url(url: str) -> str:
    u = normalize_url(url)
    u = u.replace("github.com", "github.com").rstrip(".git")
    if u.endswith(".git"):
        u = u[:-4]
    return u


def normalize_local_uri(path: str) -> str:
    p = path.replace("\\", "/")
    while "/./" in p:
        p = p.replace("/./", "/")
    return f"file:{p.lower()}"


def canonical_key(identifier_type: str, value: str) -> str:
    if identifier_type == "doi":
        return normalize_doi(value)
    if identifier_type == "arxiv":
        return normalize_arxiv(value)
    if identifier_type == "url":
        return normalize_url(value)
    if identifier_type == "repo":
        return normalize_repo_url(value)
    if identifier_type == "local":
        return normalize_local_uri(value)
    return f"{identifier_type}:{value.strip().lower()}"
