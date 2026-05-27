from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import math
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
USER_AGENT = "AIResearchBriefingMVP/0.1 (personal research digest)"


def read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_text(url: str, timeout: int = 12) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def stable_id(source: str, title: str, url: str) -> str:
    digest = hashlib.sha1(f"{source}|{title}|{url}".encode("utf-8")).hexdigest()
    return digest[:16]


def first_text(node: ET.Element, names: list[str], namespaces: dict[str, str]) -> str:
    for name in names:
        found = node.find(name, namespaces)
        if found is not None and found.text:
            return clean_text(found.text)
    return ""


def parse_arxiv(source: dict, body: str) -> list[dict]:
    namespaces = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    root = ET.fromstring(body)
    items = []
    for entry in root.findall("atom:entry", namespaces):
        title = first_text(entry, ["atom:title"], namespaces)
        abstract = first_text(entry, ["atom:summary"], namespaces)
        published = first_text(entry, ["atom:published"], namespaces)[:10]
        url = ""
        for link in entry.findall("atom:link", namespaces):
            if link.attrib.get("rel") == "alternate":
                url = link.attrib.get("href", "")
                break
        url = url or first_text(entry, ["atom:id"], namespaces)
        items.append(
            {
                "id": stable_id(source["name"], title, url),
                "title": title,
                "url": url,
                "source": source["name"],
                "source_tier": source.get("tier", 2),
                "category": source.get("category", "学术论文"),
                "source_kind": "arxiv",
                "published": published,
                "abstract": abstract,
                "citations": {"semantic_scholar": None, "openalex": None},
                "signals": {"hotness": 0.0},
            }
        )
    return items


def parse_feed(source: dict, body: str) -> list[dict]:
    root = ET.fromstring(body)
    items = []

    if root.tag.endswith("feed"):
        namespaces = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", namespaces)
        for entry in entries:
            title = first_text(entry, ["atom:title"], namespaces)
            abstract = first_text(entry, ["atom:summary", "atom:content"], namespaces)
            published = first_text(entry, ["atom:updated", "atom:published"], namespaces)[:10]
            links = entry.findall("atom:link", namespaces)
            url = next((link.attrib.get("href", "") for link in links if link.attrib.get("href")), "")
            items.append(feed_item(source, title, abstract, published, url))
        return items

    channel = root.find("channel")
    if channel is None:
        return items
    for item in channel.findall("item"):
        title = clean_text(item.findtext("title"))
        abstract = clean_text(item.findtext("description"))
        published = normalize_date(clean_text(item.findtext("pubDate")))
        url = clean_text(item.findtext("link"))
        items.append(feed_item(source, title, abstract, published, url))
    return items


def feed_item(source: dict, title: str, abstract: str, published: str, url: str) -> dict:
    return {
        "id": stable_id(source["name"], title, url),
        "title": title,
        "url": url,
        "source": source["name"],
        "source_tier": source.get("tier", 2),
        "category": source.get("category", "学术新闻"),
        "source_kind": source.get("type", "web"),
        "published": published,
        "abstract": abstract,
        "citations": {"semantic_scholar": None, "openalex": None},
        "signals": {"hotness": 0.0},
    }


def normalize_date(value: str) -> str:
    if not value:
        return dt.date.today().isoformat()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(value[:31], fmt).date().isoformat()
        except ValueError:
            pass
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    return match.group(0) if match else dt.date.today().isoformat()


def collect_items(sources: dict, include_network: bool = True) -> list[dict]:
    items: list[dict] = []
    if include_network:
        for group in sources.values():
            for source in group:
                if source.get("type") not in {"arxiv", "rss", "web", "openreview"}:
                    continue
                try:
                    if source["type"] == "openreview":
                        items.extend(fetch_openreview(source))
                        continue
                    body = fetch_text(source["url"])
                    if source["type"] == "arxiv":
                        items.extend(parse_arxiv(source, body))
                    elif source["type"] == "rss":
                        items.extend(parse_feed(source, body))
                    else:
                        items.append(parse_web_page(source, body))
                except (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError) as exc:
                    print(f"warn: skipped {source['name']}: {exc}", file=sys.stderr)

    if not items:
        items = read_json(DATA / "sample_items.json")
    return items


def content_value(content: dict, field: str, default=""):
    value = content.get(field, default)
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def date_from_ms(value) -> str:
    try:
        return dt.datetime.fromtimestamp(int(value) / 1000, tz=dt.timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return dt.date.today().isoformat()


def fetch_openreview(source: dict) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "content.venueid": source["venue_id"],
            "limit": source.get("max_results", 20),
        }
    )
    payload = json.loads(fetch_text(f"https://api2.openreview.net/notes?{params}"))
    items: list[dict] = []
    for note in payload.get("notes", []):
        content = note.get("content", {})
        title = clean_text(content_value(content, "title"))
        abstract = clean_text(content_value(content, "abstract"))
        keywords = content_value(content, "keywords", [])
        venue = clean_text(content_value(content, "venue", source["name"]))
        if isinstance(keywords, list):
            abstract = f"{abstract} Keywords: {', '.join(keywords)}"
        if not title:
            continue
        url = f"https://openreview.net/forum?id={note.get('id')}"
        items.append(
            {
                "id": stable_id(source["name"], title, url),
                "title": title,
                "url": url,
                "source": source["name"],
                "source_tier": source.get("tier", 1),
                "category": source.get("category", "学术论文"),
                "source_kind": "conference",
                "accepted": True,
                "venue": venue,
                "published": date_from_ms(note.get("pdate") or note.get("mdate") or note.get("cdate")),
                "abstract": abstract,
                "citations": {"semantic_scholar": None, "openalex": None},
                "signals": {"hotness": 0.75},
            }
        )
    return items


def parse_web_page(source: dict, body: str) -> dict:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", body, flags=re.IGNORECASE | re.DOTALL)
    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    title = clean_text(title_match.group(1) if title_match else source["name"])
    abstract = clean_text(desc_match.group(1) if desc_match else title)
    return feed_item(source, title, abstract, dt.date.today().isoformat(), source["url"])


def classify_topics(item: dict, profile: dict) -> list[str]:
    text = f"{item.get('title', '')} {item.get('abstract', '')} {item.get('source', '')}".lower()
    topics = set(item.get("topics") or [])
    for topic, aliases in profile["topic_aliases"].items():
        if any(alias.lower() in text for alias in aliases):
            topics.add(topic)
    if not topics and item.get("category") == "工业界":
        topics.add("LLM")
    return sorted(topics)


def title_zh(item: dict) -> str:
    existing = item.get("title_zh")
    if existing:
        return existing
    title = item.get("title", "")
    replacements = [
        ("Large Language Models", "大语言模型"),
        ("Language Models", "语言模型"),
        ("Vision-Language", "视觉语言"),
        ("Agents", "智能体"),
        ("Agent", "智能体"),
        ("Graph Neural Networks", "图神经网络"),
        ("Self-Supervised", "自监督"),
        ("Medical", "医学"),
        ("Clinical", "临床"),
        ("Evaluation", "评估"),
        ("Benchmark", "基准"),
    ]
    zh = title
    for src, dst in replacements:
        zh = re.sub(src, dst, zh, flags=re.IGNORECASE)
    return zh


def summarize_zh(item: dict) -> list[str]:
    topics = "、".join(item.get("topics") or ["AI"])
    terms = extract_key_terms(item)
    term_text = "、".join(terms[:6]) if terms else item.get("title", "")[:80]
    return [
        f"问题：这条内容聚焦 {topics}，核心对象是 {item.get('title', '')[:100]}。",
        f"方法：摘要线索包括 {term_text}；阅读时重点核对具体方法、数据集、benchmark 和实验设置。",
        f"影响：{why_it_matters(item)}",
    ]


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def extract_key_terms(item: dict) -> list[str]:
    text = f"{item.get('title', '')} {item.get('abstract', '')}"
    patterns = [
        r"\b[A-Z][A-Za-z0-9]+(?:-[A-Za-z0-9]+)+\b",
        r"\b[A-Z]{2,}[A-Za-z0-9-]*\b",
        r"\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+\b",
        r"\b\w+(?:Net|Former|BERT|GPT|CLIP|SAM|LLaMA|Bench|Eval|Graph|RAG)\b",
    ]
    terms: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            if match not in terms and len(match) > 1:
                terms.append(match)
    for phrase in [
        "tool use",
        "tool-calling",
        "vision-language",
        "self-supervised",
        "graph neural network",
        "reward model",
        "clinical evaluation",
        "medical imaging",
        "dataset shift",
        "multimodal reasoning",
    ]:
        if phrase.lower() in text.lower() and phrase not in terms:
            terms.append(phrase)
    return terms


def why_it_matters(item: dict) -> str:
    topics = item.get("topics") or []
    if item.get("accepted"):
        venue = item.get("venue") or item.get("source")
        return f"它已经被 {venue} 接收，比普通 arXiv 预印本更值得优先检查。"
    if "Agent Skills / MCP / Tool Use" in topics:
        return "它可能直接影响 Codex、Claude Code、LangChain 等 agent 工作流的可用能力。"
    if "Medical AI" in topics or "AI for Health" in topics:
        return "它和医学 AI 的数据、验证或临床落地相关，值得检查数据集和验证强度。"
    if "Graph Neural Network" in topics:
        return "它覆盖图表示学习或知识图谱方向，可能与你的 GNN 研究线索相关。"
    if "Self-Supervised Learning" in topics:
        return "它涉及预训练和表示学习，适合判断是否能迁移到低标注或医学场景。"
    if "AI Agent" in topics:
        return "它关系到 agent 架构、工具调用或多步推理，是当前系统型 AI 的关键方向。"
    return "它来自高优先级来源，且与当前 AI 前沿主题匹配。"


def action_for(item: dict) -> str:
    topics = item.get("topics") or []
    if item.get("accepted"):
        return "优先读 OpenReview 页面，查看接收 venue、abstract 和相关讨论"
    if "Agent Skills / MCP / Tool Use" in topics:
        return "看官方文档或 repo，判断是否能装进你的 Codex 工作流"
    if item.get("category") == "学术论文" and item.get("source_tier") == 1:
        return "收藏周末精读，重点看方法、实验和局限"
    if item.get("category") == "工业界":
        return "看官方 demo 或技术细节，避免只读营销表述"
    return "快速扫读，必要时收藏"


def score_item(item: dict, profile: dict) -> float:
    weights = profile["ranking_weights"]
    topics = item.get("topics") or []
    text = f"{item.get('title', '')} {item.get('abstract', '')}".lower()
    topic_relevance = min(1.0, len(topics) / 3)
    source_credibility = 1.0 if item.get("source_tier") == 1 else 0.72 if item.get("source_tier") == 2 else 0.45
    novelty = novelty_score(item.get("published"))
    hotness = item.get("signals", {}).get("hotness") or 0.0
    citations = item.get("citations", {}) or {}
    citation_value = max(citations.get("semantic_scholar") or 0, citations.get("openalex") or 0)
    citation_score = min(1.0, math.log1p(citation_value) / 7)
    boost = sum(0.03 for keyword in profile["boost_keywords"] if keyword.lower() in text)
    penalty = sum(0.08 for keyword in profile["downrank_keywords"] if keyword.lower() in text)
    if item.get("accepted"):
        boost += 0.75
    if item.get("source_kind") == "arxiv":
        penalty += 0.18
    return (
        weights["topic_relevance"] * topic_relevance
        + weights["source_credibility"] * source_credibility
        + weights["novelty"] * novelty
        + weights["hotness"] * hotness
        + weights["citations"] * citation_score
        + boost
        - penalty
    )


def novelty_score(date_text: str | None) -> float:
    if not date_text:
        return 0.5
    try:
        age = (dt.date.today() - dt.date.fromisoformat(date_text[:10])).days
    except ValueError:
        return 0.5
    if age <= 2:
        return 1.0
    if age <= 7:
        return 0.82
    if age <= 30:
        return 0.58
    return 0.25


def dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for item in items:
        key = re.sub(r"\W+", "", item.get("title", "").lower())[:120]
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def build_digest(include_network: bool = True) -> dict:
    profile = read_json(DATA / "profile.json")
    sources = read_json(DATA / "sources.json")
    items = collect_items(sources, include_network=include_network)
    items = dedupe(items)

    for item in items:
        item["topics"] = classify_topics(item, profile)
        item["title_zh"] = title_zh(item)
        item["summary_zh"] = summarize_zh(item)
        item["why_it_matters"] = why_it_matters(item)
        item["action"] = action_for(item)
        item["score"] = round(score_item(item, profile), 4)

    ranked = sorted(items, key=lambda item: item["score"], reverse=True)
    accepted_ranked = [item for item in ranked if item.get("accepted")]
    non_arxiv_ranked = [item for item in ranked if item.get("source_kind") != "arxiv" and not item.get("accepted")]
    arxiv_ranked = [item for item in ranked if item.get("source_kind") == "arxiv"]
    today_ranked = dedupe(accepted_ranked + non_arxiv_ranked + arxiv_ranked)
    latest_arxiv = sorted(arxiv_ranked, key=lambda item: (item.get("published") or "", item.get("score", 0)), reverse=True)
    latest_other = sorted(
        [item for item in items if item.get("source_kind") != "arxiv" and not item.get("accepted")],
        key=lambda item: (item.get("published") or "", item.get("score", 0)),
        reverse=True,
    )
    latest_ranked = dedupe(latest_arxiv + latest_other)
    paper_ranked = [item for item in today_ranked if item.get("source_kind") in {"conference", "arxiv"}]
    limits = profile["daily_limits"]
    now = dt.datetime.now().replace(microsecond=0).isoformat()
    return {
        "title": f"{dt.date.today().isoformat()} AI Research Briefing",
        "description": "Top 10 必读 + More 20 可扫，按你的研究兴趣画像生成。",
        "generated_at": now,
        "top_10": today_ranked[: limits["top"]],
        "more_20": today_ranked[limits["top"] : limits["top"] + limits["more"]],
        "latest_items": latest_ranked[: limits["top"] + limits["more"]],
        "paper_items": paper_ranked[: limits["top"] + limits["more"]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the AI research daily briefing.")
    parser.add_argument("--refresh", action="store_true", help="Fetch sources and write data/digests/daily.json.")
    parser.add_argument("--offline", action="store_true", help="Use sample items only.")
    args = parser.parse_args()

    if not args.refresh:
        parser.print_help()
        return 0

    digest = build_digest(include_network=not args.offline)
    write_json(DATA / "digests" / "daily.json", digest)
    print(f"Generated {len(digest['top_10'])} top items and {len(digest['more_20'])} scan items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
