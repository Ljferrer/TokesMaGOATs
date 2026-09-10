# TokesMaGOATs

A lightweight, local token ledger for **Codex and Claude Code**, including subagents. Python's standard library, SQLite, and one HTML page. No dependencies, telemetry, API keys, or build step.

## Run

```sh
python3 app.py
```

Open http://127.0.0.1:8765. Python 3.9+ with timezone data is required. The first import scans all histories and can take a minute or more; later syncs parse only changed files. Click **Sync usage** for new activity. Use `--port 8766` to change the port or `--sync` to import and print a JSON summary without starting a server.

The dashboard includes a yearly contribution grid, daily totals, input/output breakdown, cache reads, subagent totals, client/model breakdowns, and source coverage. The current-year grid ends at today. Additional summaries show your largest day and week, current-week usage against the same weekdays last week, and a seven-calendar-day average. Weekly bars stack main chat (solid, bottom), task subagents (striped, middle), and auditors (dotted), and other usage (crosshatched, top), with all four groups subdivided by model using consistent colors. Hover or focus a segment for its exact token count and share of the week. An expandable table lists main-chat, task-subagent, auditor, other, and combined totals; the daily pace chart shows up to 90 days and a seven-day average. Weeks start Monday; weekly charts count only the selected year, while the largest-week summary spans all retained history. Hover or click a day (or activate it with Enter/Space) to see a pie chart of its main-chat/task-subagent/auditor/other usage subdivided by model, with exact counts and percentages. Pie diameter interpolates linearly from 100 to 200 pixels using the day’s tokens divided by the largest day across all years (50% usage gives a 150-pixel diameter); hovering previews a day; keyboard focus alone does not change the pie. The daily ledger is collapsed by default and can be expanded for raw totals. Hover over abbreviated numbers for exact values.

## Sources and accounts

Defaults scan `~/.codex/sessions`, `~/.codex/archived_sessions`, and `~/.claude/projects` recursively, including Claude's nested `subagents` directories and Codex subagent sessions. Histories are streamed; transcript content is not retained in memory between records. All accounts whose usage appears in these directories are combined. Local logs do not reliably identify the authenticated account, so the app does not invent account attribution.

For custom profile directories, copy `config.example.json` to `config.json`, add sources using provider `Codex` or `Claude Code`, and optionally give each an `account` label. Set `timezone` to your IANA timezone. Restart after config changes. Config is ignored by git.

Coverage is limited to retained local records. Deleted histories, other computers, and missing usage measurements cannot be reconstructed. This app does not scrape web accounts or estimate subscription limits or dollar costs.

## Accounting

- **Total = input + output.** Cached input is included once. Reasoning is part of output, not added again.
- Codex: use per-response `token_usage_record` entries and deduplicate by response ID across live, archived, forked, and copied histories. For older files without those records, use changes in cumulative `token_count` counters; repeated snapshots are ignored. Copied parent responses retain their parent classification when encountered in a child log. Legacy histories lack response IDs, so timestamp-and-counter deduplication and subagent attribution are best effort. Files with detailed records use those instead of cumulative snapshots, which can carry inherited context usage.
- Claude Code: input includes ordinary input, cache creation, and cache reads. Repeated streaming messages are merged by message ID using the greatest reported counters. Nested subagents and sidechain messages are included.
- Local calendar dates use the configured timezone (default `America/Los_Angeles`).
- SQLite stores usage metadata only, never prompts, responses, tool content, or credentials. Session count represents distinct client/session IDs; Claude subagents often share their parent's session ID.
- Imports retain recorded events even if source files later disappear. To rebuild after changing parser behavior or source selection, stop the app, remove `data/usage.sqlite3`, and restart. This only removes the derived ledger, not the original histories.

The server binds to loopback. Keep it local; it has no authentication. `data/`, databases, personal configuration, and environment files are ignored by git.

## Verify

```sh
python3 -m unittest -v
node test_dashboard.cjs
```

Node is only needed for the optional dashboard tests, not to run the app.

Tests cover repeated and copied histories, streaming updates, subagents, cache accounting, cumulative legacy counters, incomplete writes, and timezone boundaries.

**Roles are determined by recorded launch provenance, not model choice.** Codex child sessions launched during an explicit `$snipe` (or namespaced Snipe) invocation turn are Auditors. Claude agents attributed to `war-auditor`, through the assistant record or adjacent `.meta.json` agent type, are Auditors. Other subagents remain Task subagents even when they use Sol, Sonnet, or Opus. Codex's `codex-auto-review` belongs to Other. All four categories contribute to the overall total, without overlap.

When audit provenance is missing from retained logs, a subagent remains a Task subagent; the app does not guess based on its model or mentions of auditing in ordinary conversation. Role metadata is stored separately from usage and existing histories are reclassified automatically on the first sync after this update. No prompt text is stored in the ledger.

## Estimated carbon footprint

The dashboard includes daily and all-time **metric tons of operational electricity CO₂**, low/central/high sensitivity scenarios, model-specific fresh/cache/output energy assumptions, and one-way economy LAX–JFK passenger flight equivalents. This is an estimate from retained token records, not measured provider power or a full life-cycle assessment. Parameter sizes remain undisclosed; open-weight reference models provide clearly labeled compute proxies.

See [CARBON_METHODOLOGY.md](CARBON_METHODOLOGY.md) for the research, primary sources, equations, per-model assignments, scope, and optional `config.json` overrides. Cache-heavy histories are especially sensitive to assumed cache energy. No usage or footprint report is uploaded with the source code.
