# Overleaf Contribution Stats

Analyze Overleaf project history to break down individual author contributions per source file.

This tool distinguishes between:
- **New Content**: Text added in updates with no deletions (original writing)
- **Rewriting/Editing**: Text added and removed in the same update (revisions)

## Why This Tool?

Overleaf's git integration doesn't preserve accurate author attribution - whoever syncs to git becomes the commit author, not the person who wrote the content. This tool accesses Overleaf's internal history API to get the real per-user contribution data.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Step 1: Get Your Session Cookie

1. Log into [Overleaf](https://www.overleaf.com) in your browser
2. Open Developer Tools (F12) → Application → Cookies → overleaf.com
3. Copy the value of the `overleaf_session2` cookie

Or copy the full Cookie header from any network request.

### Step 2: Fetch Project History

```bash
python overleaf_contrib.py fetch \
    --project-id YOUR_PROJECT_ID \
    --cookie "overleaf_session2=YOUR_COOKIE"
```

The project ID is in your Overleaf URL: `https://www.overleaf.com/project/PROJECT_ID`

This creates `overleaf_history_<id>.json` with all update metadata.

### Step 3: Analyze Contributions

For detailed analysis of specific files:

```bash
# Analyze all .tex files
python overleaf_contrib.py analyze \
    --project-id YOUR_PROJECT_ID \
    --cookie "YOUR_COOKIE" \
    --file-pattern "\.tex$"

# Or specific files
python overleaf_contrib.py analyze \
    --project-id YOUR_PROJECT_ID \
    --cookie "YOUR_COOKIE" \
    --files main.tex sections/intro.tex sections/methods.tex
```

## Output

The tool generates a markdown report showing:

### Overall Summary
| Name | New Content (chars) | Rewriting +/- | Total Inserted | Original Draft % |
|------|---------------------|---------------|----------------|------------------|
| Alice | 15,000 | +5,000/-3,000 | 20,000 | 75.0% |
| Bob | 8,000 | +12,000/-10,000 | 20,000 | 40.0% |

### Per-File Breakdown
Shows the same metrics broken down by each file analyzed.

## Methodology

For each update in Overleaf's history, the tool:

1. Fetches the detailed diff showing insertions and deletions
2. Attributes each change to the user who made it
3. Classifies the update type:
   - **New Content**: User only inserted text (no deletions) → original writing
   - **Rewriting**: User both inserted and deleted text → editing/revising
4. Aggregates character counts per user per file

The **Original Draft %** represents what fraction of a user's total inserted characters came from "new content" updates versus "rewriting" updates.

## Safety

This tool is **read-only**. It:
- Only uses GET requests
- Only accesses `/updates` and `/diff` endpoints
- Has a hardcoded whitelist preventing access to any other endpoints
- Does not modify your Overleaf project in any way

## Options

### fetch command
- `--project-id`: Overleaf project ID (required)
- `--cookie`: Session cookie (required)
- `--output`: Output JSON file (default: `overleaf_history_<id>.json`)

### analyze command
- `--project-id`: Overleaf project ID (required)
- `--cookie`: Session cookie (required)
- `--updates-file`: JSON file from fetch command (auto-detected)
- `--output`: Output markdown file (default: `contribution_report.md`)
- `--files`: List of specific files to analyze
- `--file-pattern`: Regex pattern to filter files (e.g., `\.tex$`)
- `--sample N`: Only process N updates per file (for testing)
- `--verbose`: Show detailed error messages

## License

MIT License - see LICENSE file.
