#!/usr/bin/env python3
"""
Overleaf Contribution Statistics - READ-ONLY

Analyzes Overleaf project history to show per-user contributions,
distinguishing between:
- New Content: Text added in updates with no deletions (original writing)
- Rewriting: Text added/removed in updates with both (editing)

SAFETY: This script ONLY uses GET requests to read history data.
It does NOT modify the project in any way.

Usage:
    # First, fetch the project history
    python overleaf_contrib.py fetch --project-id PROJECT_ID --cookie "COOKIE"

    # Then analyze with detailed diffs (takes longer but more accurate)
    python overleaf_contrib.py analyze --project-id PROJECT_ID --cookie "COOKIE"

To get your session cookie:
    1. Log into Overleaf in your browser
    2. Open Developer Tools (F12) > Application > Cookies
    3. Copy the value of the 'overleaf_session2' cookie
    Or copy the full Cookie header from a network request.
"""

import argparse
import json
import re
import requests
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# SAFETY: Only these read-only endpoints are allowed
ALLOWED_ENDPOINTS = frozenset([
    '/updates',  # GET project update history
    '/diff',     # GET diff between versions (read-only)
])

BASE_URL = "https://www.overleaf.com"


def safe_get(session, project_id, endpoint, params=None):
    """
    Perform a safe GET request - only allows whitelisted read-only endpoints.

    SAFETY: This function will REFUSE to call any endpoint not in ALLOWED_ENDPOINTS.
    """
    if endpoint not in ALLOWED_ENDPOINTS:
        raise ValueError(f"SAFETY: Endpoint '{endpoint}' not in whitelist: {ALLOWED_ENDPOINTS}")

    url = f"{BASE_URL}/project/{project_id}{endpoint}"
    response = session.get(url, params=params)
    response.raise_for_status()
    return response.json()


def create_session(cookie):
    """Create a requests session with proper headers."""
    session = requests.Session()

    # Handle both full Cookie header and just the session value
    if 'overleaf_session2=' in cookie:
        session.headers['Cookie'] = cookie
    else:
        session.headers['Cookie'] = f"overleaf_session2={cookie}"

    session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; OverleafContribStats)'
    session.headers['Accept'] = 'application/json'

    return session


def fetch_all_updates(session, project_id, max_pages=100):
    """
    Fetch all project updates, paginating through history.

    Returns list of update objects with user and file change info.
    """
    all_updates = []
    before = None

    for page in range(max_pages):
        params = {}
        if before:
            params['before'] = before

        print(f"Fetching updates page {page + 1}...", file=sys.stderr)

        data = safe_get(session, project_id, '/updates', params)

        updates = data.get('updates', [])
        if not updates:
            break

        all_updates.extend(updates)

        next_before = data.get('nextBeforeTimestamp')
        if not next_before or next_before == before:
            break
        before = next_before

    print(f"Fetched {len(all_updates)} total updates", file=sys.stderr)
    return all_updates


def fetch_diff(session, project_id, from_v, to_v, pathname):
    """Fetch diff for a specific file between versions."""
    params = {'from': from_v, 'to': to_v, 'pathname': pathname}
    try:
        data = safe_get(session, project_id, '/diff', params)
        return data.get('diff', [])
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 500:
            return None  # Diff too large or server error
        raise


def analyze_diff(diff):
    """
    Analyze a diff to extract per-user insertions and deletions.

    Returns dict: {user_id: {name, email, ins_chars, del_chars}}
    """
    user_stats = defaultdict(lambda: {
        'name': None,
        'email': None,
        'ins_chars': 0,
        'del_chars': 0,
    })

    for item in diff:
        if 'i' in item:
            text = item['i']
            users = item.get('meta', {}).get('users', [])
            if users and users[0]:
                user = users[0]
                user_id = user.get('id', 'unknown')
                user_stats[user_id]['name'] = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                user_stats[user_id]['email'] = user.get('email')
                user_stats[user_id]['ins_chars'] += len(text)

        elif 'd' in item:
            text = item['d']
            users = item.get('meta', {}).get('users', [])
            if users and users[0]:
                user = users[0]
                user_id = user.get('id', 'unknown')
                user_stats[user_id]['name'] = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                user_stats[user_id]['email'] = user.get('email')
                user_stats[user_id]['del_chars'] += len(text)

    return dict(user_stats)


def classify_update_contribution(diff_stats):
    """
    Classify each user's contribution in an update as:
    - 'new_content': Only insertions, no deletions (writing new text)
    - 'rewriting': Both insertions and deletions (editing existing text)
    - 'deletion_only': Only deletions (removing text)

    Returns dict: {user_id: {'type': str, 'ins_chars': int, 'del_chars': int, ...}}
    """
    classified = {}

    for user_id, stats in diff_stats.items():
        ins = stats['ins_chars']
        dels = stats['del_chars']

        if ins > 0 and dels == 0:
            contrib_type = 'new_content'
        elif ins > 0 and dels > 0:
            contrib_type = 'rewriting'
        elif dels > 0:
            contrib_type = 'deletion_only'
        else:
            continue

        classified[user_id] = {
            'name': stats['name'],
            'email': stats['email'],
            'type': contrib_type,
            'ins_chars': ins,
            'del_chars': dels,
        }

    return classified


def get_files_from_updates(updates, file_pattern=None):
    """Extract unique file paths from updates, optionally filtered by pattern."""
    files = set()
    for update in updates:
        for path in update.get('pathnames', []):
            if file_pattern:
                if re.search(file_pattern, path):
                    files.add(path)
            else:
                files.add(path)
    return sorted(files)


def cmd_fetch(args):
    """Fetch command - get project update history."""
    session = create_session(args.cookie)

    print(f"Fetching history for project: {args.project_id}", file=sys.stderr)
    print("SAFETY: Only using read-only GET requests", file=sys.stderr)
    print("", file=sys.stderr)

    try:
        updates = fetch_all_updates(session, args.project_id)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("ERROR: Authentication failed. Check your cookie.", file=sys.stderr)
        elif e.response.status_code == 403:
            print("ERROR: Access denied. Check project permissions.", file=sys.stderr)
        else:
            print(f"ERROR: HTTP {e.response.status_code}: {e}", file=sys.stderr)
        sys.exit(1)

    # Analyze basic stats
    per_user = defaultdict(lambda: {'name': None, 'email': None, 'updates': 0, 'files': set()})

    for update in updates:
        users = update.get('meta', {}).get('users', [])
        pathnames = update.get('pathnames', [])

        for user in users:
            if user is None:
                continue
            user_id = user.get('id', 'unknown')
            per_user[user_id]['name'] = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            per_user[user_id]['email'] = user.get('email')

        if users and users[0]:
            user_id = users[0].get('id', 'unknown')
            per_user[user_id]['updates'] += 1
            per_user[user_id]['files'].update(pathnames)

    # Save raw data
    output_file = args.output or f"overleaf_history_{args.project_id}.json"
    with open(output_file, 'w') as f:
        json.dump({'updates': updates}, f, indent=2, default=str)
    print(f"History saved to: {output_file}", file=sys.stderr)

    # Print summary
    print("\n## Contributors Summary\n")
    print("| Name | Email | Updates | Files Touched |")
    print("|------|-------|---------|---------------|")

    for user_id, data in sorted(per_user.items(), key=lambda x: -x[1]['updates']):
        name = data['name'] or user_id
        email = data['email'] or 'N/A'
        print(f"| {name} | {email} | {data['updates']} | {len(data['files'])} |")


def cmd_analyze(args):
    """Analyze command - detailed diff analysis for contribution breakdown."""
    session = create_session(args.cookie)

    # Load updates
    updates_file = args.updates_file or f"overleaf_history_{args.project_id}.json"

    if not Path(updates_file).exists():
        print(f"Updates file not found: {updates_file}", file=sys.stderr)
        print("Run 'fetch' command first, or specify --updates-file", file=sys.stderr)
        sys.exit(1)

    print(f"Loading updates from {updates_file}...", file=sys.stderr)
    with open(updates_file) as f:
        data = json.load(f)
    updates = data['updates']

    print("SAFETY: Only using read-only GET requests", file=sys.stderr)
    print("", file=sys.stderr)

    # Get files to analyze
    if args.files:
        target_files = args.files
    else:
        target_files = get_files_from_updates(updates, args.file_pattern)

    if not target_files:
        print("No files to analyze. Specify --files or --file-pattern", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing {len(target_files)} files...", file=sys.stderr)

    # Aggregate stats per user per file
    file_user_stats = defaultdict(lambda: defaultdict(lambda: {
        'name': None, 'email': None,
        'new_content_chars': 0,
        'new_content_updates': 0,
        'rewriting_ins_chars': 0,
        'rewriting_del_chars': 0,
        'rewriting_updates': 0,
        'deletion_only_chars': 0,
    }))

    # Process each file
    for filename in target_files:
        print(f"\nProcessing {filename}...", file=sys.stderr)

        file_updates = [u for u in updates if filename in u.get('pathnames', [])]

        if args.sample > 0:
            file_updates = file_updates[:args.sample]

        print(f"  {len(file_updates)} updates to process", file=sys.stderr)

        success = 0
        failed = 0

        for i, update in enumerate(file_updates):
            from_v = update['fromV']
            to_v = update['toV']

            if i > 0 and i % 10 == 0:
                time.sleep(0.5)

            try:
                diff = fetch_diff(session, args.project_id, from_v, to_v, filename)

                if diff is None:
                    failed += 1
                    continue

                diff_stats = analyze_diff(diff)
                classified = classify_update_contribution(diff_stats)

                for user_id, contrib in classified.items():
                    fus = file_user_stats[filename][user_id]
                    fus['name'] = contrib['name'] or fus['name']
                    fus['email'] = contrib['email'] or fus['email']

                    if contrib['type'] == 'new_content':
                        fus['new_content_chars'] += contrib['ins_chars']
                        fus['new_content_updates'] += 1
                    elif contrib['type'] == 'rewriting':
                        fus['rewriting_ins_chars'] += contrib['ins_chars']
                        fus['rewriting_del_chars'] += contrib['del_chars']
                        fus['rewriting_updates'] += 1
                    elif contrib['type'] == 'deletion_only':
                        fus['deletion_only_chars'] += contrib['del_chars']

                success += 1

            except Exception as e:
                failed += 1
                if args.verbose:
                    print(f"    Error on v{from_v}-v{to_v}: {e}", file=sys.stderr)

            if (i + 1) % 20 == 0:
                print(f"    Processed {i+1}/{len(file_updates)}...", file=sys.stderr)

        print(f"  Done: {success} successful, {failed} failed", file=sys.stderr)

    # Generate report
    print("\nGenerating report...", file=sys.stderr)
    report = generate_report(file_user_stats, target_files)

    output_file = args.output or "contribution_report.md"
    with open(output_file, 'w') as f:
        f.write(report)

    print(f"\nReport saved to: {output_file}", file=sys.stderr)
    print(report)


def generate_report(file_user_stats, target_files):
    """Generate markdown report from analysis results."""

    # Aggregate totals per user
    user_totals = defaultdict(lambda: {
        'name': None, 'email': None,
        'new_content_chars': 0,
        'new_content_updates': 0,
        'rewriting_ins_chars': 0,
        'rewriting_del_chars': 0,
        'rewriting_updates': 0,
        'files': {}
    })

    for filename, users in file_user_stats.items():
        for user_id, stats in users.items():
            user_totals[user_id]['name'] = stats['name'] or user_totals[user_id]['name']
            user_totals[user_id]['email'] = stats['email'] or user_totals[user_id]['email']
            user_totals[user_id]['new_content_chars'] += stats['new_content_chars']
            user_totals[user_id]['new_content_updates'] += stats['new_content_updates']
            user_totals[user_id]['rewriting_ins_chars'] += stats['rewriting_ins_chars']
            user_totals[user_id]['rewriting_del_chars'] += stats['rewriting_del_chars']
            user_totals[user_id]['rewriting_updates'] += stats['rewriting_updates']
            user_totals[user_id]['files'][filename] = dict(stats)

    lines = []
    lines.append("# Overleaf Contribution Analysis")
    lines.append("")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append("This analysis fetches detailed diffs from Overleaf's history and classifies each update:")
    lines.append("")
    lines.append("- **New Content**: Updates where a user ONLY inserted text (no deletions)")
    lines.append("  - These represent writing new/original text")
    lines.append("- **Rewriting/Editing**: Updates where a user BOTH inserted AND deleted text")
    lines.append("  - These represent revising/editing existing text")
    lines.append("")
    lines.append("The **Original Draft %** shows what fraction of a user's total inserted characters")
    lines.append("came from new content updates (vs rewriting updates).")
    lines.append("")

    # Summary table
    lines.append("## Overall Summary")
    lines.append("")
    lines.append("| Name | New Content (chars) | Rewriting +/- | Total Inserted | Original Draft % |")
    lines.append("|------|---------------------|---------------|----------------|------------------|")

    for user_id, data in sorted(user_totals.items(),
                                 key=lambda x: -(x[1]['new_content_chars'] + x[1]['rewriting_ins_chars'])):
        name = data['name'] or user_id
        new_chars = data['new_content_chars']
        rewrite_ins = data['rewriting_ins_chars']
        rewrite_del = data['rewriting_del_chars']
        total_ins = new_chars + rewrite_ins

        orig_pct = (new_chars / total_ins * 100) if total_ins > 0 else 0

        if total_ins > 0:
            lines.append(f"| {name} | {new_chars:,} | +{rewrite_ins:,}/-{rewrite_del:,} | {total_ins:,} | {orig_pct:.1f}% |")

    lines.append("")

    # Per-file breakdown
    lines.append("## Per-File Breakdown")
    lines.append("")

    for filename in target_files:
        short_name = Path(filename).stem
        lines.append(f"### {short_name}")
        lines.append("")

        users = file_user_stats.get(filename, {})
        if not users:
            lines.append("*No data available*")
            lines.append("")
            continue

        lines.append("| Name | New Content | Rewriting +/- | Total Ins | Original % |")
        lines.append("|------|-------------|---------------|-----------|------------|")

        for user_id, stats in sorted(users.items(),
                                      key=lambda x: -(x[1]['new_content_chars'] + x[1]['rewriting_ins_chars']))[:15]:
            name = stats['name'] or user_id
            new_chars = stats['new_content_chars']
            rewrite_ins = stats['rewriting_ins_chars']
            rewrite_del = stats['rewriting_del_chars']
            total_ins = new_chars + rewrite_ins

            orig_pct = (new_chars / total_ins * 100) if total_ins > 0 else 0

            if total_ins > 0:
                lines.append(f"| {name} | {new_chars:,} | +{rewrite_ins:,}/-{rewrite_del:,} | {total_ins:,} | {orig_pct:.1f}% |")

        lines.append("")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Overleaf Contribution Statistics (READ-ONLY)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SAFETY NOTICE:
  This tool ONLY performs GET requests to read history data.
  It does NOT modify Overleaf projects in any way.

Examples:
  # Fetch project history
  python overleaf_contrib.py fetch --project-id abc123 --cookie "overleaf_session2=..."

  # Analyze with detailed diffs (for .tex files)
  python overleaf_contrib.py analyze --project-id abc123 --cookie "..." --file-pattern "\\.tex$"

  # Analyze specific files
  python overleaf_contrib.py analyze --project-id abc123 --cookie "..." --files main.tex chapter1.tex
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Fetch command
    fetch_parser = subparsers.add_parser('fetch', help='Fetch project history')
    fetch_parser.add_argument('--project-id', required=True, help='Overleaf project ID (from URL)')
    fetch_parser.add_argument('--cookie', required=True, help='Session cookie')
    fetch_parser.add_argument('--output', help='Output JSON file (default: overleaf_history_<id>.json)')

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Detailed contribution analysis')
    analyze_parser.add_argument('--project-id', required=True, help='Overleaf project ID')
    analyze_parser.add_argument('--cookie', required=True, help='Session cookie')
    analyze_parser.add_argument('--updates-file', help='JSON file with updates (from fetch command)')
    analyze_parser.add_argument('--output', help='Output markdown file (default: contribution_report.md)')
    analyze_parser.add_argument('--files', nargs='+', help='Specific files to analyze')
    analyze_parser.add_argument('--file-pattern', help='Regex pattern to filter files (e.g., "\\.tex$")')
    analyze_parser.add_argument('--sample', type=int, default=0, help='Only process N updates per file (for testing)')
    analyze_parser.add_argument('--verbose', action='store_true', help='Show detailed error messages')

    args = parser.parse_args()

    if args.command == 'fetch':
        cmd_fetch(args)
    elif args.command == 'analyze':
        cmd_analyze(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
