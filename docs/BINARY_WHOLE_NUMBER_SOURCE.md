# Existing whole-number source corrections

The local binary v4/v5 workflow can inspect and correct an existing ordinary
kind13 whole-number field when its exact current template and FieldLimits list
are available in the same fully verified registry. The current template field
number is resolved from the complete saved field ID; the saved source number
stays unchanged in the exported file.

FieldLimits resources are selected using the effective template's ordered
DataHomes. The first present resource wins, including a present empty list.
A present list with no entry for the current field supplies no min/max bound;
a missing list is unknown and keeps the integer read only. No caller-supplied
bounds, resource order or write permission is accepted.

The correction admits only existing signed32 integers with header0, exponent0,
format0, flag11=0, source attributes exactly Used1 and current field attributes0.
Unused, Computed, Override, unknown profiles and currently out-of-range values
stay read only. Proposed values must be decimal whole numbers without a plus
sign, decimal point or exponent and must satisfy the selected min/max bounds.
Native validation, aliases, defaults, author events and native SetValue do not
run. This tool refuses an invalid proposed value instead of writing an error
header. Money/date conversion and new field/row creation are unchanged.

Documents → Open TaxML / binary .tax → Try independently generated binary
samples → Load whole-number sample opens the complete fictional example. Its
OWNED_UNITS field has saved number113, current number13, value7 and bounds1..12
from a nonprimary registry home. Entering13 refuses export; correcting7 to8
exports3,831 bytes with SHA256
3772cb75235635e81d47d61ff526db44b40c8a1f4a372956a0307b979428cd7f.
The four complete saved-form tails, value-note/destination bodies, nonempty
tables, child and four links remain verified after full-file writing/readback.

This source-only field cannot be silently treated as reviewed income. The
current IRS return stays unchanged. Original engine execution, original saved
return acceptance and full .tax compatibility remain unverified. Host,
WebAssembly, browser and actual native package acceptance are separate states.
