# Interactive design preview

Open [index.html](index.html) directly in a browser. No installation, server, dependencies, credentials, or network access is required.

Try: navigate the six screens; create/pause a demo rule; simulate a large print; load the OCR review sample, correct the quantity and confirm it; generate illustrative alternatives; commit another position version and see the prior suggestions expire.

Data is synthetic. Values reset on reload. The sample screenshot is an HTML representation of a positions table. Buttons simulate local UI state only: there is no actual image extraction, Webull connection, Telegram delivery, persistent storage, or trade execution. The full requirements are in [the UX specification](../docs/07-ux-and-flows.md).

Optional: run `node scripts/serve-preview.cjs` from the repository root and open http://127.0.0.1:8788. The server binds to loopback and serves only an allowlist of design files.