# Deploy AI Research Briefing

This project can be shared as a static website. Visitors do not need Python or Codex; they only load the generated JSON digest and static app files.

## Option A: GitHub Pages

1. Create a GitHub repository, for example `ai-research-briefing`.
2. Copy this folder into the repository and commit it.
3. In GitHub, open `Settings > Pages`.
4. Set `Build and deployment` to `Deploy from a branch`.
5. Choose the `main` branch and `/root`.
6. Open the published URL.

The root `index.html` redirects to `app/index.html`, so the site works from the repository homepage.

## Option B: Vercel

1. Import the repository into Vercel.
2. Framework preset: `Other`.
3. Build command: leave empty.
4. Output directory: leave empty or use `.`.
5. Deploy.

## Updating The Daily Briefing

Run this locally before publishing:

```powershell
cd C:\Doctorial\AI_MVP
.\run.ps1
```

If you only want to refresh the data without starting the local server:

```powershell
C:\Users\12608\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe .\pipeline\ai_briefing.py --refresh
```

Then commit and push the changed `data/digests/daily.json`.

## What Others Will See

- The published site shows the current generated Top 10 + More 20.
- Each visitor's saved/read/hidden actions stay in their own browser local storage.
- There is no login, backend database, or private user tracking in this MVP.

