# Next Steps

Updated: 2026-08-22 20:28:22 +08:00

1. Review the complete M6 diff and browser evidence.
2. Establish an M6 Git checkpoint only after explicit approval; exclude `.pytest_tmp_m6*` and local runtime database artifacts.
3. Keep product availability backend-derived and keep persisted package snapshots as the frontend source of truth.
4. Treat automatic Story/Experience/Resource generation for a newly succeeded Run as a separate orchestration milestone; do not conceal the current partial-package state.
5. Do not push or enter M7 without a separately approved scope.

Boundary to preserve: M6 is complete. The browser consumes validated Catalog projections, formal Runtime state, and exact persisted package snapshots; it never generates cultural facts, calls an LLM, or ranks local resources.
