# Third-party source and licensing

Tax Reborn #000002 is distributed under AGPL-3.0-only because its local state worker includes the Invaro OpenTax core, US corpus and state composers. The independent portions were initially MIT; that notice is retained in original-independent-code-MIT.txt. Ledger Reborn #000001 has a separate MIT license and is unaffected.

OpenTax is pinned to commit 72e1fc73ce0454c20c2fa6e8f7b7b41cd292e261. The complete committed corresponding source is in opentax/corresponding-source.tar.gz, with its authentic license and source metadata. No hosted API, telemetry, MCP-server component or commercial license is used by the application. Rebuild with Python3.12+ and Node22+ using `python scripts/build_state.py --work-dir <temporary-directory>`. The archive has its pnpm9.15.4 lockfile; the adapter source is scripts/state-worker-entry.mjs.

Zod3 (MIT), bundled with the state worker, comes from the pinned OpenTax dependency lockfile. Runtime browser resources and authentic notices are in web/vendor: Pyodide0.29.3 (MPL2.0), Python3.13.2 (PSF), pypdf6.10.0 (BSD3Clause), Tesseract.js6.0.1 and core6.0.0 (Apache2.0), and English trained data (Apache2.0). Each resource group has a source manifest. Native desktop dependencies have their authentic installed-package notices collected at build time.
