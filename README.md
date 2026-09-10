# TokesMaGOATs

A lightweight, local token ledger for **Codex and Claude Code**, including subagents. Python's standard library, SQLite, and one HTML page. No dependencies, telemetry, API keys, or build step.

## Run

```sh
python3 app.py
```

Open http://127.0.0.1:8765. Python 3.9+ with timezone data is required. The first import scans all histories and can take a minute or more; later syncs parse only changed files. Click **Sync usage** for new activity. Use `--port 8766` to change the port or `--sync` to import and print a JSON summary without starting a server.

The dashboard includes a contribution grid, token and cache totals, client/model breakdowns, and source coverage. All charts and totals use the applied date/provider/model/project/role selection. Summary cards show its largest day and week, final week, and trailing average. Weekly bars stack main chat, task subagents, auditors, and other usage, subdivided by model. Hover or focus weekly segments for exact counts; expandable ledgers retain raw totals. Daily activity and its pie use compact K/M/B token counts. Hover or click a day (or activate it with Enter/Space) to inspect its role/model pie. Pie diameter interpolates from 100 to 200 pixels relative to the largest recorded day across all years, even when filtering. The current range never extends beyond today.

## Sources and accounts

Defaults scan `~/.codex/sessions`, `~/.codex/archived_sessions`, and `~/.claude/projects` recursively, including Claude's nested `subagents` directories and Codex subagent sessions. Histories are streamed; transcript content is not retained in memory between records. All accounts whose usage appears in these directories are combined. Local logs do not reliably identify the authenticated account, so the app does not invent account attribution.

For custom profile directories, copy `config.example.json` to `config.json`, add sources using provider `Codex` or `Claude Code`, and optionally give each an `account` label. Set `timezone` to your IANA timezone. Restart after config changes. Config is ignored by git.

Coverage is limited to retained local records. Deleted histories, other computers, and missing usage measurements cannot be reconstructed. This app does not scrape web accounts or estimate subscription limits or billed charges. It can estimate API-equivalent costs.

## Accounting

- **Total = input + output.** Cached input is included once. Reasoning is part of output, not added again.
- Codex: use per-response `token_usage_record` entries and deduplicate by response ID across live, archived, forked, and copied histories. For older files without those records, use changes in cumulative `token_count` counters; repeated snapshots are ignored. Copied parent responses retain their parent classification when encountered in a child log. Legacy histories lack response IDs, so timestamp-and-counter deduplication and subagent attribution are best effort. Files with detailed records use those instead of cumulative snapshots, which can carry inherited context usage.
- Claude Code: input includes ordinary input, cache creation, and cache reads. Repeated streaming messages are merged by message ID using the greatest reported counters. Nested subagents and sidechain messages are included.
- Local calendar dates use the configured timezone (default `America/Los_Angeles`).
- SQLite stores usage metadata and short task labels (saved titles/summaries or opening-request excerpts), not full transcripts, tool content, or credentials. Session count represents distinct client/session IDs; Claude subagents often share their parent's session ID.
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

When audit provenance is missing from retained logs, a subagent remains a Task subagent; the app does not guess based on its model or mentions of auditing in ordinary conversation. Role metadata is stored separately from usage and existing histories are reclassified automatically on the first sync after this update. Work grouping may store a short opening-request excerpt as a task label.

## Estimated carbon footprint

The dashboard includes daily and all-time **metric tons of operational electricity CO₂**, low/central/high sensitivity scenarios, model-specific fresh/cache/output energy assumptions, and one-way economy LAX–JFK passenger flight equivalents. This is an estimate from retained token records, not measured provider power or a full life-cycle assessment. Parameter sizes remain undisclosed; open-weight reference models provide clearly labeled compute proxies.

See [CARBON_METHODOLOGY.md](CARBON_METHODOLOGY.md) for the research, primary sources, equations, per-model assignments, scope, and optional `config.json` overrides. Cache-heavy histories are especially sensitive to assumed cache energy. No usage or footprint report is uploaded with the source code.

## Work grouping

Project totals merge worktree folders and attach Codex child sessions to their parent task. Claude subagents share their parent session. Expand project or work-type bars to see task labels and exact totals for the applied selection. Work types use local title keywords, not model calls; mixed-topic sessions get one approximate category, and missing labels remain unclassified. All classification runs locally and personal labels stay in the ignored database.

## Sharing snapshots

Use **Save PNG** on any chart panel or the header to download a shareable image of that panel or the whole dashboard. The selected day also has its own export. Snapshots preserve current selections and expanded details, and include visible project/task labels. Images are generated locally using bundled [html-to-image 1.11.13](https://github.com/bubkoo/html-to-image) (MIT); nothing is uploaded or published automatically.

## Filters, comparisons, and cost

Choose a date preset or custom dates, provider, model, project, and role, then Apply filters. Totals and charts use that selection. Compare against the preceding equal number of calendar days or the full calendar month before the selected start date. A partial current month can therefore be compared explicitly to a full previous month. Reset returns to the current year. Project aliases with the same display name are selected together. The daily pie diameter still uses the largest recorded day of all time.

API-equivalent cost applies published standard short-context rates checked September 10, 2026 to recorded usage. It is not a subscription bill or a historical invoice. Cache reads and writes are priced separately; net cache savings include write premiums. Unknown models remain unpriced and reduce visible pricing coverage. Add `cost_rates` to your private `config.json` to override a model with `[fresh_input, cached_read, cache_write, output]` USD per million tokens. Assumptions exclude long-context/fast premiums, batch discounts, residency, tools, taxes and historical rate changes; cache writes assume five-minute TTL. Sources: [OpenAI](https://developers.openai.com/api/docs/pricing) and [Anthropic](https://platform.claude.com/docs/en/about-claude/pricing).

## Getting started and refresh

The dashboard opens while history imports run in the background. Getting started reports detected, missing, empty, and unreadable sources and explains custom paths. Dismiss it with Got it; it remains available for troubleshooting. A scan failure retains previously imported data and offers a manual retry.

Auto refresh defaults to every five minutes while the page is visible; choose every minute or Off. The choice persists in this browser. One scan runs at a time, including requests from multiple tabs. Refresh preserves applied filters, the carbon scenario, and the selected day when it remains in range. Import and connection errors appear in the status line; automatic mode retries on its next interval. No AI API calls are made.

After rendering, a visible Download PNG link remains available if your browser suppresses the automatic download.
