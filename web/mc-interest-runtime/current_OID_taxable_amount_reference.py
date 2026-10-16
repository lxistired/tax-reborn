"""Actual-v5 OID current storage -> filtered taxable amount comparison."""
from current_OID_snapshot_reference import read_OID_snapshot
from finite_OID_taxable_amount_reference import OIDTaxableAmount


def project_OID_taxable_amount(request,*,binary_loader,approved_bank_profile,approved_OID,program,expected_program_sha256):
    snapshot=read_OID_snapshot(request,binary_loader=binary_loader,approved_bank_profile=approved_bank_profile,approved_OID=approved_OID)
    engine=OIDTaxableAmount(program,expected_sha256=expected_program_sha256,inputs={r:snapshot['typed_inputs'][r]for r in{n['reference']for n in program['nodes']if n['type']=='input'}},prior_values=snapshot['current_assignment_storage']);roots=engine.run()
    return dict(source_sha256=snapshot['source_sha256'],program_content_sha256=expected_program_sha256,roots=roots,
        current_source_snapshot=snapshot,evaluated_references=engine.trace,proposed_graph_assignments=engine.assignments,
        blank_condition_trace=engine.blank_trace,rounding_trace=engine.rounding,
        actual_source_BOID_family_14545_recomputed=True,Line1AmountCombined14725_recomputed=False,
        source_complete_L4_or_R2_calculation=False,other_source_families_assumed_empty=False,
        saved_absence_is_not_native_runtime_absence=True,native_record_inventory_verified=False,
        original_assignment_flag_mutations_executed=False,BINT_to_INT_row_identity_verified=False,owned_labels_are_native_UUIDs=False,
        comparison_only=True,writeback_allowed=False,original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
