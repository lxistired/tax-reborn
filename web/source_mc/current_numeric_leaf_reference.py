"""Current source numeric leaf protocol, before unresolved Mapping/MC selection.

This code accepts a real source request through the fixed reviewed loader. It
does not accept prepared InstanceValue text, flags, booleans, amount or UUIDs.
The resulting owned leaf closes the selected direct get_field_value -> leaf
constructor/SetBits protocol, conditional on the native exterior selecting this
same field and the already reviewed no-rounding precision2 branch. It is not
the result of a native Mapping read, current input-cache lookup or MC grouping.
"""
from decimal import Decimal
import hashlib,json,struct
from .numeric_current_input_reference import StoredCents,render_current_cents,create_numeric_input
from .postcopy_cache_reference import NumericState,FlatNumericMC,_numeric,_mc

FIELDS={'L1':9400,'L3':9401,'EXINT':9441}

def instance_flags(attributes,header):
    """Exact integer expression in get_field_value10153fbe0, not FV enum names."""
    if type(attributes)is not int or not 0<=attributes<=65535 or type(header)is not int or not 0<=header<=255:
        raise ValueError('Explicit current U16 FV attributes and U8 header required')
    a=attributes;h=header
    return (((a&0x208)|(h&0x10))+((h>>7)*2)|(a>>4)&4|(a>>1)&1)+((a&4)*8)|(a&0x10)<<4|(a*4)&0x80|(a>>6)&0x40|(a*4)&0x400

def _construct(record):
    # Used gates rendering, but existing Unused FV still supplies flags.
    text=render_current_cents(record)
    flags=0 if record is None else instance_flags(record.attributes,record.header)
    value=create_numeric_input(text)
    base=bytearray(16)
    base[0]=int(value is None)  # Value+08 blank, Value+09 UserInput initially0.
    word=0
    for sourcebit,targetbit in ((1,3),(0x20,10),(0x40,6),(0x80,7),(0x10,4),(4,9),(0x100,8),(8,0)):
        if flags&sourcebit:word|=1<<targetbit
    struct.pack_into('<Q',base,8,word) # Value+10hex initialized0 by ValueC2.
    leaf=NumericState(Decimal(0)if value is None else value,base,struct.pack('<II',2,0))
    return leaf,dict(has_value=value is not None,text=text,flags=flags,
        has_flags=record is not None,error68=False,
        existing_Unused_FV_retains_flag_supply=record is not None and not(record.attributes&1))

def leaf_report(leaf):
    _numeric(leaf);word=struct.unpack_from('<Q',leaf.base_8_17,8)[0]
    return dict(amount=format(leaf.coefficient,'f'),blank=bool(leaf.base_8_17[0]),
        UserInput=bool(leaf.base_8_17[1]),Computed=bool(word&8),Overridden=bool(word&1),
        Error=bool(word&4),DropAssign=bool(word&0x80),value_flag_word=str(word),
        owned_base_08_17_hex=leaf.base_8_17.hex(),
        native_known_base_mask_hex='ffff000000000000ffffffffffffffff',
        native_padding_0A_0F_not_proved_initialized=True)

def _error(value):
    if type(value)is NumericState:
        _numeric(value);return bool(value.base_8_17[8]&4)
    if type(value)is FlatNumericMC:
        _mc(value);return any(_error(v)for v in value.rows.values())
    raise ValueError('NonNULL finite Numeric or flat Numeric MC required')

def propagate_input_errors(inputs,output):
    """Finite CalcAndRound error loop; clean inputs never clear old output bits.

    Inputs here are explicit owned objects. The request API below supplies one
    authenticated source leaf, not the whole current node input vector.
    """
    if type(inputs)is not tuple or len(inputs)>64:raise ValueError('Bounded explicit input vector required')
    errors=tuple(_error(v)for v in inputs);_error(output)
    called=any(errors)
    if called:
        leaves=(output,)if type(output)is NumericState else tuple(output.rows.values())
        for leaf in leaves:leaf.base_8_17[8]|=4
    return dict(value=output,input_errors=list(errors),error_setter_called=called,
        output_error=_error(output),clears_prior_output_error=False)

def read_source_leaf(request,*,binary_loader,approved_profile):
    """Same actual-v5 context -> full D2/FindValue -> direct leaf protocol.

    The fixed outer API owns metadata and loader selection. No source UUID is
    inferred from word7c, saved149/14A, sourcepath or an owned row label.
    """
    from .interest_snapshot_reference import read_snapshot
    from .strict_bint_row_scope_reference import reject_extra_bint_rows
    from .strict_actual_array_interest_reference import exact_source_owner_ids
    required={'source','expected_source_sha256','summary_path','source_formset_index','row_number','field_id','need_native_row_uuid'}
    if type(request)is not dict or set(request)!=required or request['field_id']not in FIELDS:
        raise ValueError('Exact current-source leaf request; no prepared values/programs/flags accepted')
    if type(request['source'])is not dict or request['source'].get('profile',{}).get('format')!='tax-reborn-binary-entity-profile-v5':
        raise ValueError('Actual reviewed v5 source with same-registry arrays required')
    loaded=binary_loader(request['source']);doc,buffers,bound,registry,selected,wire=loaded
    if getattr(bound,'document',None)is not doc:raise ValueError('One identical actual document/binding required')
    digest=hashlib.sha256(wire).hexdigest()
    if request['expected_source_sha256']!=digest:raise ValueError('Current source digest mismatch')
    calls=1
    def same(source):
        if source!=request['source']:raise ValueError('Source changed during one read')
        return loaded
    if type(request['summary_path'])is not list or len(request['summary_path'])!=2 or any(type(i)is not int or i<0 for i in request['summary_path']):
        raise ValueError('One actual root summary path required')
    if type(request['source_formset_index'])is not int or request['source_formset_index']!=request['summary_path'][0]:
        raise ValueError('Exact same source FormSet index required')
    q={k:v for k,v in request.items()if k!='source_formset_index'};q['field_id']='L1'
    snapshot=read_snapshot(q,binary_loader=same,approved_profile=approved_profile)
    path=tuple(snapshot['owner_proof']['summary_path'])
    scope=reject_extra_bint_rows(doc,bound,path)
    exact=exact_source_owner_ids(doc,snapshot['owner_proof'])
    trace=next(t for t in snapshot['current_field_trace']if t['field_id']==request['field_id']and t['reference']==FIELDS[request['field_id']])
    record=None
    if trace['source_storage']=='stored':
        # This finite source profile refuses special FV flags even for Unused
        # storage. It does not widen old header-error/current-format support.
        if trace['FV_attributes']not in(0,1,2,3,8,9,10,11)or trace['value_header']!=0 or trace['format_flag10']!=0:
            raise ValueError('Ordinary kind11 current header0/format0 protocol required')
        record=StoredCents(trace['kind'],int(trace['raw64']),trace['FV_attributes'],
            trace['value_header'],trace['format_flag10'],trace['flag11'],trace['packed_exponent'])
    leaf,instance=_construct(record)
    return dict(source_sha256=digest,binary_context_calls=calls,current_field=dict(trace),
        raw_current_instance=instance,direct_numeric_leaf=leaf_report(leaf),
        source_owner_proof=snapshot['owner_proof'],strict_BINT_scope=scope,exact_owner_IDs=exact,
        ValueTypes=2,precision_if_present=2,source_record_bytes_unchanged=True,
        direct_current_field_protocol_complete=True,Mapping_read_executed=False,
        direct_protocol_is_conditional_on_same_selected_FV_and_precision2=True,
        existing_owner_profile_requires_Used_L1_flag11_zero=True,
        this_leaf_ErrorBit_proved_false=True,whole_input_error_vector_verified=False,
        actual_GetMultiCopyInputValue_executed=False,active_input_cache_verified=False,
        runtime_Record_UUID_verified=False,native_record_inventory_verified=False,
        comparison_only=True,writeback_allowed=False,native_runtime=0,physical_writes=0,
        remaining=['Mapping read constraints/path transform and Instance aggregation',
            'active scoped ancestors/AutoMC input cache and grouping keys',
            'runtime Record inventory and UUID supplier','other input Value error bits',
            'source-current post-Load/defaults and native dispatch','TPS writeback'])
