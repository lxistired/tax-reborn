# Compare source interest locally

The Documents screen can inspect an owned binary source and compare a limited
Schedule B interest calculation through L4 and Form 1040 L8A. These are interest
amounts, not the final tax, refund or amount owed. This comparison never changes
the source file or the current Tax Reborn return.

1. Open **Documents → Try local calculation comparison → Open binary source
   for L4 / L8A comparison**. Select your source, its explicit profile and the
   matching local registries. Inspect the source.
2. Choose **Compare source interest L4 / L8A**. Select complete local
   `fdittx.3pe` and `fdif01.3pe` resources. Both content hashes must match the
   supported release, and `fdif01` must already be bound to that source.
3. Inspect the current values and any overrides, confirm the scope, then run
   the comparison. You can save the complete comparison report locally.

The inspected source also offers **Compare proposed interest adjustments**.
This separate mode evaluates nine supported source temporary fields and their
bounded adjustment path before L4 and L8A. It displays loaded field values,
a calculated baseline using saved ADJUST, and the proposed amounts separately.
For an owned source with $12.34 of accrued-interest adjustment, the calculated
baseline is $1,822.68/$1,823 and the proposed L4/L8A pair is
$1,810.34/$1,810. A current L8A override remains in effect.

The proposed mode refuses any existing Used ADJUST amount, including Used
zero. It also refuses cases requiring unsupported native blank deletion or
temporary Override handling. Retained source temporary operands stay labelled
as retained. The complete local audit includes each operand's provenance.
No temporary amount, prepared program or Boolean result can be supplied as a
substitute for source calculation. This mode does not execute native output
admission, TPS writes/reload, the dependency queue or the complete tax sequence.
The original saved-adjustment mode remains available separately.

Inspected source attachments in **Documents** have an **Open source** action.
It reuses the saved source, explicit profile and bound registry files, so the
source can be inspected again after reopening the App. A JSON return backup
does not include these separate attachments.

No original resources, decoded programs, taxpayer records or working source
fixture for this comparison are included in the repository or installers.
The existing independent wage example remains available without those files.
Changing the source, selected files, confirmation or current return invalidates
the result. Closing the dialog terminates its calculation worker.

The current reader supports its explicit acknowledged v5 binary profile and a
single root Schedule B with one matching root Form 1040. It derives current
field bindings from the same source rather than substituting file-copy IDs for
runtime copy numbers. A current L8A override is retained. If L8A storage is
absent, the comparison shows a proposal and creates no source field.

The finite calculation reads local raw calculation resources at runtime and
builds its supported interest programs in memory. INPUT10770 still uses saved
current storage; its upstream aggregation is not freshly executed. ADJUST4263
also uses saved adjustments. The EE case is limited to the qualified married
filing separately normal-return invariant. Native inventory, row UUID mapping,
the dependency queue, TPS writeback and the remaining Form 1040 sequence are
not implemented by this comparison.

That paragraph describes the original saved-adjustment mode. The proposed
mode computes the supported temporary-to-adjustment consequence subject to
the stricter refusals above; it still retains INPUT10770 and the EE condition.

Actual desktop Chrome acceptance covers file selection, source inspection,
calculation, override and absent-storage behavior, stale-result rejection and
full report download. The owned multi-form cases produce L4/L8A pairs of
$1,822.68/$1,823 and $1,945.68/$1,946; an override case retains $999. These are
synthetic cases, not original taxpayer-file or licensed-original runtime
comparisons. The initial calculation takes about 20 seconds on the tested Mac.
The observed WebAssembly allocation is about 406 MiB; this is not total memory
use or a phone memory guarantee. A fresh offline browser reload also completed
source inspection, the default interest comparison and the complete report
download from cached application assets. Original resources still came from
local file selection. Native acceptance is recorded separately in [Preview32 validation](RELEASE_PREVIEW32.md).
Mac ARM64 and a real Android device completed the proposed $12.34 adjustment
case and saved the entire identical 693,329-byte audit. Windows installed-module
and native GUI checks passed, but that new positive original-resource case was
not supplied to Windows CI. One successful phone case is not a general memory
guarantee for all devices.

The main Tax Reborn return continues to use the independently written IRS
calculation and reviewed document-import workflow. No electronic filing or
complete TurboTax compatibility is implied.
