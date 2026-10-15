# Edit a supported Mac decimal source field

Open **Documents → Open TaxML / binary tax**. Under the independently generated samples, choose **Load Mac decimal source sample**. Inspect the source and choose **Inspect / edit decimal fields**. Select a stored field, edit its decimal value, confirm the correction, then download the complete corrected container.

The example has two entities, seven form copies and 47 stored fields. Its three decimal fields contain 0.7, 1.2 and -0.3. The fields store coefficients with one fractional digit. They are not money and are never added to the App income or IRS calculation.

The supported v2 profile selects `null_filter` or `controller_filter` explicitly. Names, full field IDs, current ordinals, kinds and CID data must come from the matching complete registration. Source and profile hashes bind each confirmation. Only an existing supported field can be corrected. Unknown kinds, attributes, render formats, copy bindings and stale confirmations are refused.

Changing the first decimal from 0.7 to 0.8 produces a complete 2,241-byte ZIP. The other 46 fields, all seven income candidates, the manifest and the other four raw local records remain unchanged. Windows, Mac and a real Android phone have saved exactly the same bytes through their system save dialogs. Their old saved returns remain unchanged.

This is a cleartext source-copy correction. It does not create native forms or field inventory, run the original SetValue operation or recalculate derived original values. The original default encrypted container is unsupported. The [existing monetary source workflow](MAC_TAXML_SOURCE.md) and the App’s normal IRS calculations remain separate.
