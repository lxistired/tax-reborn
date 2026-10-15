"""Caller-owned constant-Boolean field section -> owned proposed kind10 state.

Only the independently audited normal local enterable target, Boolean literal
and field assignment operations are admitted. Native runtime/defaults/queues,
physical missing-key creation and source writeback are never executed.
"""
from dataclasses import dataclass
from decimal import Decimal
import hashlib,struct
from source_calculation_reference import CarrierBytes,index_carrier,_decode_program

@dataclass(frozen=True)
class IntegerStorage:
    raw64:int
    attributes:int
    header:int=0


def execute_section(carrier_wire,*,approved_section,current_storage,approved_fields):
    keys={'carrier_sha256','resource_type','resource_id','body_sha256','body_bytes'}
    if type(approved_section)is not dict or set(approved_section)!=keys:raise ValueError('External trusted complete program authority required')
    if type(approved_fields)is not list or not 1<=len(approved_fields)<=16:raise ValueError('Explicit finite complete target metadata required')
    metadata={}
    for p in approved_fields:
        if type(p)is not dict or set(p)!={'field_id','ordinal','kind','format','template_attributes'}or any(type(p[k])is not int for k in('ordinal','kind','format','template_attributes'))or(p['kind'],p['format'],p['template_attributes'])!=(10,0,0):
            raise ValueError('Finite exact kind10/format0 current field metadata required')
        ordinal=p['ordinal']
        if type(ordinal)is not int or not 1<=ordinal<=65535 or ordinal in metadata:raise ValueError('Unique U16 field targets required')
        metadata[ordinal]=p
    if type(current_storage)is not dict or set(current_storage)!=set(metadata):raise ValueError('Explicit current storage including None for every target required')
    for old in current_storage.values():
        if old is not None and(type(old)is not IntegerStorage or type(old.raw64)is not int or not 0<=old.raw64<(1<<64)or type(old.attributes)is not int or old.attributes not in(0,1,2,3,8,9,10,11)or type(old.header)is not int or old.header!=0):
            raise ValueError('Ordinary current storage or explicit absent field required')
    records,frames=index_carrier(CarrierBytes('caller-owned-information-resource',carrier_wire,approved_section['carrier_sha256']))
    body=records.get((approved_section['resource_type'],approved_section['resource_id']))
    if body is None or len(body)!=approved_section['body_bytes']or hashlib.sha256(body).hexdigest()!=approved_section['body_sha256']:
        raise ValueError('Exact approved original section body required')
    program=_decode_program(body)
    if program.local_types or program.arrays or program.parameter_types:raise ValueError('Scalar no-local/no-parameter information section required')
    state=dict(current_storage);stack=[];seen=set();trace=[];writes=[]
    for instruction in program.instructions:
        op=instruction.opcode;payload=instruction.payload
        if op==0x85:
            ordinal,flag=struct.unpack('<HB',payload)
            if flag or ordinal not in metadata:raise ValueError('Exact approved scalar local target required')
            stack.append(('target',ordinal))
        elif op==0x54:
            if payload not in(b'0',b'1'):raise ValueError('Exact Boolean literal0/1 required')
            stack.append(payload==b'1')
        elif op==0x72:
            if len(stack)<2:raise ValueError('Complete assign stack required')
            value,target=stack.pop(),stack.pop()
            if type(value)is not bool or type(target)is not tuple or target[0]!='target':raise ValueError('Only present Boolean to kind10 field assignments supported')
            ordinal=target[1]
            if ordinal in seen:raise ValueError('Finite one assignment per target profile required')
            seen.add(ordinal);old=state[ordinal]
            preserved=old is not None and bool(old.attributes&8)
            # Boolean false is present. Kind10 zero is Used1/Computed, unlike
            # null enterable assignments or checkbox-group clear semantics.
            if not preserved:state[ordinal]=IntegerStorage(int(value),3)
            writes.append(dict(field_id=metadata[ordinal]['field_id'],ordinal=ordinal,computed_boolean=value,
                source_node_exists=old is not None,override_preserved=preserved,after=state[ordinal],
                target_origin='owned_proposed_state',can_commit_to_source=False))
        else:raise ValueError('Unknown or unsupported information opcode refused')
        trace.append(dict(pc=instruction.pc,opcode=op,raw_sha256=hashlib.sha256(instruction.raw).hexdigest()))
    if stack or seen!=set(metadata):raise ValueError('Complete normal section and all reviewed field assignments required')
    return dict(proposed_storage=state,assignments=writes,instruction_trace=trace,program_body_sha256=approved_section['body_sha256'],
        source_content_origin_authority_external=True,manual_section_sequence=True,native_scheduler_executed=False,
        native_original_runtime=0,physical_writes=0,source_newkey_creation_executed=False,comparison_only=True,writeback_allowed=False)
