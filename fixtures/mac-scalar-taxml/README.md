# Independently generated decimal source

This fixture contains no vendor data or original saved return. Run
`python3 scripts/create_mac_scalar_fixture.py` to reproduce it.

The complete XPRF contains ordinary kind13/format0/attributes0 `DECIMAL` fields
at current ordinal9 in three FW2 copies. The two entities contain seven form
copies and 47 present fields. Their decimal text is `0.7`, `1.2`, and `-0.3`.
Each coefficient has one implied fractional digit. These fields do not enter
the reviewed income boxes, App income records, or tax calculation.

The explicit `tax-reborn-taxml-native-mac-profile-v2` profile requires
`filter_profile` equal to `controller_filter` or `null_filter`. The controller
sample binds every exact `field` current ordinal and `elem="0"` attribute.
The separate NULL sample has neither debug attribute. The profile does not
certify native factory acceptance or execute a native setter.

The normal ZIP contains five members, including an unchanged manifest and
four unselected local records. The blocked sample has unmodeled manifest
metadata and permits inspection only. Protected original files are unsupported.

For the actual App workflow, load `owned-mac-scalar.zip`, `profile.json`, and
`owned-mac-scalar.xprf`, or select **Load Mac decimal source sample**. Choose
**Inspect / edit decimal fields**, select the first field, replace `0.7` with
`0.8`, confirm, and download the complete container. The expected output is
2241 bytes, SHA-256
`1da9b78f366be589372251a598ba28bc03922d03adc70337d114f93a09c32412`.
All other fields, copies, entities, manifest bytes, and four local records
remain unchanged. `scripts/verify_mac_scalar_native.py` verifies the result.
