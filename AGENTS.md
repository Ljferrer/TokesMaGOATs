# Repository instructions

## Documentation lifecycle

- Keep `docs/` for maintained product and developer guidance: workflows, data contracts, architecture, and reference material. Keep living doctrine and active plans with the application. `docs/engineering-evidence.md` is served by the app and stays here.
- Store audit traces, Snipe panels, repair logs, validation/mutation evidence, and run reports in [Ljferrer/DocTrail](https://github.com/Ljferrer/DocTrail), checked out at `~/GitHub/DocTrail`. Do not commit these execution records to this repository.
- Retire completed or abandoned plans and superseded specs to DocTrail when they no longer guide active work. Use its `audits/`, `reports/`, `plans/`, or `specs/` shelf under `TokesMaGOATs/`, following DocTrail's `CONTEXT.md`. Keep one episode together in a dated bundle, including its ledger and supporting reports.
- Before retiring a document, check code, tests, links, and other live readers; preserve or redirect every reader. Pin the source commit, preserve original filenames and bytes, and record provenance in `RETIREMENT.md`. Name the DocTrail bundle in the source deletion commit and link PRs to the archived evidence. Never rewrite landed archives.
