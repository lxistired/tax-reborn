"""One loaded actual-v5 document -> fresh bounded14873 comparison result.

No intermediate Boolean or amount is accepted from the request. Programs and
metadata must be authenticated externally by the caller. Original native copy
inventory, assignment flag effects, scheduler and physical writes do not run.
"""
import hashlib
from current_product_control_reference import project_product_control
from current_OID_execution_reference import project_OID_adjustments
from finite_adjustment_presence_reference import AdjustmentPresence


def recalculate_adjustment_presence(request,*,binary_loader,approved_bank_profile,approved_entries,approved_targets,
        approved_OID,approved_product,programs):
    if type(programs)is not dict or set(programs)!={'bank','OID','product','presence'}or any(type(v)is not dict or set(v)!={'model','sha256'}for v in programs.values()):
        raise ValueError('Four external authenticated source programs required; request self-authority is not accepted')
    loaded=binary_loader(request['source']);wire=loaded[-1];digest=hashlib.sha256(wire).hexdigest()
    def same_loader(source):
        if source!=request['source']:raise ValueError('Source changed during complete adjustment comparison')
        return loaded
    bankp,oidp,productp,presencep=(programs[k]for k in('bank','OID','product','presence'))
    product=project_product_control(request,binary_loader=same_loader,approved_profile=approved_bank_profile,
        approved_entries=approved_entries,approved_targets=approved_targets,bank_program=bankp['model'],bank_sha256=bankp['sha256'],
        approved_product=approved_product,control_program=productp['model'],control_sha256=productp['sha256'])
    OID=project_OID_adjustments(request,binary_loader=same_loader,approved_bank_profile=approved_bank_profile,approved_OID=approved_OID,
        program=oidp['model'],expected_program_sha256=oidp['sha256'])
    bank=product['upstream_bank']
    if any(x['source_sha256']!=digest for x in(product,OID,bank)):raise ValueError('All producers must read the identical loaded source snapshot')
    produced={**bank['roots'],**OID['roots'],**product['roots']};required={n['reference']for n in presencep['model']['nodes']if n['type']=='component'}
    if not required<=set(produced):raise ValueError('A required producer was not actually calculated; missing is never blank')
    components={r:produced[r]for r in required}
    engine=AdjustmentPresence(presencep['model'],expected_sha256=presencep['sha256'],components=components,prior_values=bank['nine_temporary_priors'])
    result=engine.run()
    if len(result)!=1 or type(next(iter(result.values())))is not bool:raise ValueError('Actual present Boolean result required')
    return dict(source_sha256=digest,roots=result,ThereAreAdjustments14873_recomputed=True,
        original_program_content_sha256={k:p['sha256']for k,p in programs.items()},
        computed_components=components,proposed_temporary_writes=engine.assignments,evaluated_presence_references=engine.trace,
        bank_projection=bank,product_projection={k:v for k,v in product.items()if k!='upstream_bank'},OID_projection=OID,
        no_manual_Boolean_or_amount_cutpoints=True,all_current_facts_share_one_loaded_document=True,
        copy_metadata_is_conditional_existing_source_row_projection=True,
        stored_absence_is_not_native_runtime_absence=True,native_record_inventory_verified=False,
        original_assignment_flag_mutations_executed=False,native_Defaults_Load_Fixup_executed=False,
        original_scheduler_executed=False,TPS_output_conversion_executed=False,
        owned_labels_are_native_UUIDs=False,BINT_to_INT_row_identity_verified=False,
        source_complete_L4_or_R2_calculation=False,source_complete_original_return_calculation=False,
        comparison_only=True,writeback_allowed=False,original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
