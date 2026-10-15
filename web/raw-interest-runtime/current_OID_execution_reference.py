"""Same actual-v5 current OID facts -> finite thirteen source contributions."""
from current_OID_snapshot_reference import read_OID_snapshot
from finite_OID_adjustment_reference import OIDAdjustment


def project_OID_adjustments(request,*,binary_loader,approved_bank_profile,approved_OID,program,expected_program_sha256):
    snapshot=read_OID_snapshot(request,binary_loader=binary_loader,approved_bank_profile=approved_bank_profile,approved_OID=approved_OID)
    engine=OIDAdjustment(program,expected_sha256=expected_program_sha256,inputs=snapshot['typed_inputs'],prior_values=snapshot['current_assignment_storage'])
    roots=engine.run()
    return dict(source_sha256=snapshot['source_sha256'],program_content_sha256=expected_program_sha256,roots=roots,
        current_source_snapshot=snapshot,evaluated_references=engine.trace,proposed_graph_assignments=engine.assignments,
        blank_condition_trace=engine.blank_trace,rounding_trace=engine.rounding,
        complete_selected172_graph=True,all13_OID_contributions_recomputed=True,
        fresh_Default_source_guard='Both Default targets absent/Unused, plus no exterior Override/itemization; any stored Used String including empty refuses',
        nonProduct_IsUserInput_flags_assumed_false=False,native_assignment_flag_mutations_executed=False,
        source_complete14873=False,source_complete_calculation=False,native_record_inventory_verified=False,
        owned_labels_are_native_UUIDs=False,comparison_only=True,writeback_allowed=False,
        original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
