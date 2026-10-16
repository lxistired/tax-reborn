"""Caller-local resource bytes + actual current document -> bounded L4 comparison.

No normalized program argument is accepted. Original resource authority and
metadata authority must come from the embedding host, outside untrusted request
JSON. This still uses an owned phase order, retained current priors and the
existing MFS-only invariant; it neither runs native dispatch nor commits writes.
"""
from raw_interest_program_reference import compile_current_interest_programs
from current_source_L4_reference import project_source_L4


def project_raw_source_L4(request,*,binary_loader,authorities,caller_resource,resource_authority):
 if type(request)is not dict or any(k in request for k in('program','programs','compiled_programs','intermediate_values','manual_amounts','manual_booleans')):raise ValueError('Original document inputs only; external normalized/intermediate programs refused')
 compiled=compile_current_interest_programs(caller_resource,authority=resource_authority)
 output=project_source_L4(request,binary_loader=binary_loader,authorities=authorities,programs=compiled['programs'])
 return dict(result=output,resource_provenance=compiled['provenance'],program_canonical_sha256=_hashes(compiled['programs']),programs_derived_from_caller_owned_original_bytes=True,external_normalized_programs_accepted=False,native_dependency_schedule_executed=False,native_current_inventory_verified=False,comparison_only=True,writeback_allowed=False,remaining_source_conditions=['EE12 unresolved cuts only eliminated by the qualified MFS normal-return value invariant','INPUT10770 remains actual saved/current storage, not a fresh aggregation','ADJUST4263 is observed saved storage, not rebuilt from newly computed temporary adjustments','native factory/inventory, row UUID, dependency queue and TPS output conversion are not executed'],original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)


def _hashes(programs):
 if set(programs)=={'model','sha256'}:return programs['sha256']
 return{k:_hashes(v)for k,v in programs.items()}
