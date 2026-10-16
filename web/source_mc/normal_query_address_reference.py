"""Normal query-address construction, separate from native current context."""
import re

class QueryAddressOutsideProfile(ValueError):pass

def starting_unspecified(declared,supplied):
    if type(declared) is not tuple or type(supplied) is not tuple or len(declared)>64 or len(supplied)>64:
        raise QueryAddressOutsideProfile('Bounded ordered MC component indices required')
    if any(type(i) is not int or not 0<=i<=63 for i in declared+supplied):
        raise QueryAddressOutsideProfile('Finite nonnegative MC index required')
    maximum=max((-1,)+supplied);declared_max=max((-1,)+declared)
    if maximum>=declared_max:return -1
    # Source returns the FIRST stored index greater than the supplied maximum,
    # not the minimum of a re-sorted set.
    return next(i for i in declared if i>maximum)

def query_components(start,existing,target):
    if type(start) is not int or not 0<=start<64 or type(existing) is not tuple or type(target) is not tuple:
        raise QueryAddressOutsideProfile('Finite original unspecified-index branch required')
    if not 1<=len(target)<=64 or len(existing)>len(target) or start>=len(target):
        # Native checks target count < start; this finite helper also excludes
        # equality, which could otherwise access beyond the vector boundary.
        raise QueryAddressOutsideProfile('Required target query component unavailable')
    if any(type(p) is not bytes or not p or len(p)>512 for p in existing+target):
        raise QueryAddressOutsideProfile('Bounded nonempty byte components required')
    if len(existing)>start:return existing
    return existing+target[len(existing):start+1]

def format_address(parts,*,full_field):
    if type(parts) is not tuple or not parts or any(type(p) is not bytes or not p or len(p)>512 for p in parts):
        raise QueryAddressOutsideProfile('Explicit finite component vector required')
    if type(full_field) is not bool:raise QueryAddressOutsideProfile('Internal formatter selection required')
    if full_field:
        if len(parts)<3:raise QueryAddressOutsideProfile('Finite field address requires a form and field')
        return parts[0]+b'$'+b':'.join(parts[1:-1])+b'.'+parts[-1]
    return parts[0]+b'$'+b':'.join(parts[1:])

def query_address(start,existing,target):
    parts=query_components(start,existing,target)
    return dict(components=parts,address=format_address(parts,full_field=len(parts)==len(target)),
        is_full_field_address=len(parts)==len(target))

def owned_summary_query(mapping,owned_projection):
    """No external context/amount/cache argument; use fixed selected own scope.

    This supplies the address selected by an independent implementation whose
    current owner is the already validated source summary. It is not proof of
    the native caller's current FT or of native FDI namespace resolution.
    """
    if type(mapping) is not dict or mapping.get('Mapping_class')!='ordinary Mapping' or mapping.get('read_constraint_count')!=0:
        raise QueryAddressOutsideProfile('Exact authenticated ordinary no-constraint Mapping required')
    if owned_projection.get('owned_selected_projection_executed') is not True:
        raise QueryAddressOutsideProfile('Actual same-source owned selected projection required')
    path=mapping['tps_path'].encode('ascii')
    match=re.fullmatch(rb'(FDI)\$(FSCHB):(F1099I)\[uuid_1\]\.(L1|L3|EXINT)',path)
    if match is None:raise QueryAddressOutsideProfile('Exact raw source ordinary interest Mapping required')
    target=tuple(match.groups());context=target[:2]
    # Fixed application selection: summary_path is this owned receiver's current
    # scope. It does not assert a successful native FormSet lookup or Load.
    index=starting_unspecified((2,),())
    query=query_address(index,context,target)
    if query['is_full_field_address']:raise AssertionError('Expected source form-only query')
    return dict(context_origin='application-owned selected same-source summary scope',
        owned_context_components=[p.decode('ascii') for p in context],
        raw_mapping_TPS_components=[p.decode('ascii') for p in target],
        source_declared_MC_indices=[2],owned_context_supplied_MC_indices=[],
        first_unspecified_MC_index=index,owned_query_components=[p.decode('ascii') for p in query['components']],
        owned_FindInstances_query=query['address'].decode('ascii'),owned_query_is_form_only=True,
        native_starting_unspecified_slot='Mapping.v1A8',
        native_current_FT_context_verified=False,native_FDI_FormSet_lookup_verified=False,
        native_FindInstances_executed=False,native_get_field_instances_executed=False,
        computed_from_raw_mapping_and_owned_scope=True,no_caller_query_or_success_flags=True,
        original_runtime=0,physical_TPS_writes=0,comparison_only=True,writeback_allowed=False)
