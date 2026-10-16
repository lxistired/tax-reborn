"""Owned object -> legacy finite graph domain, with one actual source owner.

This adapter does not restore a native cache/row UUID or give MC key spelling
native authority. The finite graph's copy domain is an owned comparison label.
"""
from dataclasses import dataclass,field
from decimal import Decimal
import hashlib
from source_mc.owned_current_MC_value_reference import OwnedCurrentMCReceiver,value_report

@dataclass
class ActualMCState:
    document:object
    current:dict
    receiver:OwnedCurrentMCReceiver
    value:object
    leaf:object
    source_key:bytes
    consumptions:list=field(default_factory=list)

class SourceSnapshot(tuple):
    def __new__(cls,loaded,state):
        if type(loaded)is not tuple or len(loaded)!=6 or type(state)is not ActualMCState or state.document is not loaded[0]:
            raise ValueError('An internally constructed identical source/MC object context is required')
        obj=super().__new__(cls,loaded);obj.owned_MC_state=state;return obj

def bridge_prefix_snapshot(loaded,snapshot,request):
    if type(loaded)is not SourceSnapshot:raise ValueError('This source-MC graph requires the actual internally constructed source receiver')
    state=loaded.owned_MC_state
    if type(state)is not ActualMCState or state.document is not loaded[0]or state.current['source_sha256']!=hashlib.sha256(loaded[-1]).hexdigest()or request['expected_source_sha256']!=state.current['source_sha256']:
        raise ValueError('MC input and formula must consume one identical source document')
    current=state.current['current_field'];traces=[t for t in snapshot['current_field_trace']if t['reference']==9400 and t['field_id']=='L1']
    if len(traces)!=1:raise ValueError('Actual source L1/reference9400 is required')
    trace=traces[0]
    keys=('document_path','source_ordinal','current_ordinal','element_index','source_storage','kind','FV_attributes','raw64','packed_exponent','format_flag10','flag11','value_header','present')
    if any(trace.get(k)!=current.get(k)for k in keys):raise ValueError('Graph field facts differ from the actual MC input source binding')
    value=state.receiver.get_value();report=value_report(value)
    if value is not state.value or len(value.rows)!=1 or value.rows.get(state.source_key)is not state.leaf or report['Error']or report['top_blank']:
        raise ValueError('An actual nonblank clean owned MC input object is required')
    leaf=state.leaf;amount=leaf.coefficient
    if leaf.base_8_17[0]or type(amount)is not Decimal or snapshot['inputs'][9400]!={snapshot['source_label']:amount}:
        raise ValueError('Exact typed existing current amount must agree before graph substitution')
    # A singleton deterministic domain isomorphism, used only by this finite
    # graph. It neither changes the actual MC object nor claims a RecordUUID.
    snapshot['inputs'][9400]={snapshot['source_label']:amount}
    trace['numeric_value_origin']='actual_executed_owned_MC_input_object'
    trace['actual_MC_entry_key_hex']=state.source_key.hex()
    trace['owned_key_adapter_target']=snapshot['source_label']
    event=dict(reference=9400,source_field='L1',source_key_hex=state.source_key.hex(),
        graph_owned_copy_label=snapshot['source_label'],actual_amount=str(amount),
        actual_MC_object_reused=value is state.value,actual_resolved_leaf_reference_reused=value.rows[state.source_key]is leaf,
        graph_input_atom_is_actual_MC_leaf_Decimal_reference=snapshot['inputs'][9400][snapshot['source_label']]is leaf.coefficient,
        Error_checked_from_actual_MC=True,source_FV_attributes=current['FV_attributes'],
        native_row_UUID_equivalence=False,native_GetMultiCopyInputValue_executed=False)
    state.consumptions.append(event);snapshot['actual_MC_input_bridge']=event
    return snapshot
