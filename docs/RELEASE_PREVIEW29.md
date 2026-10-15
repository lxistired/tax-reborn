# Preview.29 candidate: complete cleartext container export

This version adds a complete source archive workflow around the existing TaxML income review. A supported explicitly cleartext container can contain other stored documents and unreferenced members. Correcting one supported income form now saves a complete checked ZIP while retaining the original manifest and every unselected local record. The original attachment and current IRS return remain unchanged by source export.

[Feature scope and usage](CLEARTEXT_CONTAINER_SOURCE.md) · [Actual browser checks](../qa/cleartext-container-20261015/browser-acceptance.json) · [Actual dedicated-worker checks](../qa/cleartext-container-worker/cleartext-container-worker-receipt.json).

Source validation:727host checks,616actual Pyodide executions plus2explicit skips. Actual Chrome HTTP/SQLite and390px Pyodide/IndexedDB pass reviewed income entry, saved344refund, reload/JSON restoration, duplicate refusal, the built-in example and a complete corrected archive download. The separate local source-comparison worker remains functional after its package-path allowlist update.

Native package generation, installation, changed UI flows, system-saved file readback, publication and anonymous full-download verification remain separate pending gates. Preview.28 remains the last fully tested public installer release until these gates pass. This candidate does not add Intel Mac or native iOS acceptance.

The original default container is encrypted and is unsupported here. This selected cleartext profile does not establish original template registration, full `.tax` migration, source recalculation, original engine parity or electronic filing. Original licensed runtime executions and original saved taxpayer fixtures remain zero.
