<h1 align="center">
  Overleaf Contribution Stats
</h1>

<p align="center">
  <strong>Discover who actually wrote what in your Overleaf projects</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#why-this-tool">Why This Tool</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#output">Output</a> •
  <a href="#methodology">Methodology</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.7+-blue.svg" alt="Python 3.7+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/read--only-safe-brightgreen.svg" alt="Read-only Safe">
</p>

---

## Features

- **Accurate Attribution** — Get real author data from Overleaf's internal history, not misleading git commits
- **Contribution Breakdown** — Distinguish between original writing and editing/rewriting
- **Per-File Analysis** — See who contributed to each file in your project
- **Markdown Reports** — Generate clean, shareable contribution reports

## Why This Tool?

Overleaf's git integration has a significant limitation: **whoever syncs to git becomes the commit author**, not the person who actually wrote the content. This makes git history unreliable for tracking individual contributions.

This tool solves that problem by accessing Overleaf's internal history API to retrieve the **real per-user contribution data** with full attribution.

> Perfect for academic collaborations where you need to understand who contributed what to a paper.

## Installation

```bash
git clone https://github.com/yourusername/OverleafContributionStats.git
cd OverleafContributionStats
pip install -r requirements.txt
```

**Requirements:** Python 3.7+ and the `requests` library.

## Usage

### Step 1: Get Your Session Cookie

1. Log into [Overleaf](https://www.overleaf.com) in your browser
2. Open Developer Tools (`F12`) → **Application** → **Cookies** → `overleaf.com`
3. Copy the value of the `overleaf_session2` cookie

> Alternatively, copy the full `Cookie` header from any network request in the Network tab.

### Step 2: Fetch Project History

```bash
python overleaf_contrib.py fetch \
    --project-id YOUR_PROJECT_ID \
    --cookie "overleaf_session2=YOUR_COOKIE"
```

Find your project ID in the Overleaf URL:
```
https://www.overleaf.com/project/YOUR_PROJECT_ID
                                 ^^^^^^^^^^^^^^^^
```

This creates `overleaf_history_<id>.json` containing all update metadata.

### Step 3: Analyze Contributions

**Analyze all `.tex` files:**
```bash
python overleaf_contrib.py analyze \
    --project-id YOUR_PROJECT_ID \
    --cookie "YOUR_COOKIE" \
    --file-pattern "\.tex$"
```

**Analyze specific files:**
```bash
python overleaf_contrib.py analyze \
    --project-id YOUR_PROJECT_ID \
    --cookie "YOUR_COOKIE" \
    --files main.tex sections/intro.tex sections/methods.tex
```

## Output

The tool generates a markdown report with two main sections:

### Overall Summary

| Name | New Content (chars) | Rewriting +/- | Total Inserted | Original Draft % |
|------|---------------------|---------------|----------------|------------------|
| Alice | 15,000 | +5,000/-3,000 | 20,000 | 75.0% |
| Bob | 8,000 | +12,000/-10,000 | 20,000 | 40.0% |

### Per-File Breakdown

Detailed contribution metrics for each analyzed file, showing the same statistics broken down by source file.

## Methodology

For each update in Overleaf's history, the tool:

1. **Fetches** the detailed diff showing insertions and deletions
2. **Attributes** each change to the user who made it
3. **Classifies** the update type:
   | Classification | Criteria | Interpretation |
   |----------------|----------|----------------|
   | **New Content** | Only insertions (no deletions) | Original writing |
   | **Rewriting** | Both insertions and deletions | Editing/revising |
4. **Aggregates** character counts per user per file

The **Original Draft %** represents what fraction of a user's total inserted characters came from "new content" updates versus "rewriting" updates — a useful metric for understanding contribution patterns.

## Safety

This tool is **completely read-only**. It:

| Safety Feature | Description |
|----------------|-------------|
| GET requests only | Never sends POST, PUT, DELETE, or PATCH |
| Endpoint whitelist | Only accesses `/updates` and `/diff` endpoints |
| Hardcoded restrictions | Cannot be configured to access other endpoints |
| No modifications | Your Overleaf project remains untouched |

## Command Reference

### `fetch` — Download project history

| Option | Required | Description |
|--------|----------|-------------|
| `--project-id` | Yes | Overleaf project ID from URL |
| `--cookie` | Yes | Session cookie for authentication |
| `--output` | No | Output JSON file (default: `overleaf_history_<id>.json`) |

### `analyze` — Generate contribution report

| Option | Required | Description |
|--------|----------|-------------|
| `--project-id` | Yes | Overleaf project ID |
| `--cookie` | Yes | Session cookie |
| `--updates-file` | No | JSON file from fetch (auto-detected) |
| `--output` | No | Output markdown file (default: `contribution_report.md`) |
| `--files` | No | List of specific files to analyze |
| `--file-pattern` | No | Regex pattern to filter files (e.g., `\.tex$`) |
| `--sample N` | No | Process only N updates per file (for testing) |
| `--verbose` | No | Show detailed error messages |

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <sub>Built for researchers who need accurate contribution tracking</sub>
</p>
