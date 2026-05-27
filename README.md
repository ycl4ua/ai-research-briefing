# AI Research Briefing MVP

Personal AI research briefing app for a PhD workflow. It builds a daily "Top 10 + More 20" digest from academic, industry, and agent-skill sources, then presents it in a news-app style interface.

## Quick Start

```powershell
python .\pipeline\ai_briefing.py --refresh
python -m http.server 8080 -d .
```

Open http://127.0.0.1:8080/app/index.html.

To share it with other people, deploy the folder as a static website. See `DEPLOY.md`.

If the network is unavailable, the pipeline falls back to `data/sample_items.json` so the app remains usable.

On Windows, you can also run:

```powershell
.\run.ps1
```

## Project Layout

```text
app/                         Static PWA interface
data/                        Source config, profile, generated digest
pipeline/                    Fetch, enrich, rank, summarize pipeline
mcp-server/                  Lightweight MCP-compatible stdio server
skills/ai-research-briefing  Codex skill for analysis style and judgement
```

## MVP Scope

- Daily Top 10 must-read items and More 20 scan list.
- Topics: LLM, VLM, AI Agent, Agent Skills / MCP / Tool Use, RL, AI for Health, Medical AI, GNN, SSL.
- Sources: arXiv, official AI labs, selected newsletters/blogs, and skill/tool-use ecosystems.
- Citation counts use Semantic Scholar/OpenAlex fields when available. Google Scholar is linked as a manual search target, not scraped.
- Feedback actions are stored in browser local storage for now.
