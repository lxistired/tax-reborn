"""Owned current-source MC receiver: one actually resolved stored input.

The external request entry supplies the source facts. This receiver constructs
its own maps and cache and never restores14F or accepts a native snapshot.
"""
from dataclasses import dataclass
from decimal import Decimal
import re,struct

class SourceInputOutsideProfile(ValueError):pass

def map_constructor(rows):
    from .postcopy_cache_reference import NumericState,FlatNumericMC,_numeric
    if type(rows)is not dict or len(rows)>64:
        raise SourceInputOutsideProfile('At most64 resolved scalar map entries required')
    for key,value in rows.items():
        if type(key)is not bytes or len(key)>4096:raise SourceInputOutsideProfile('Exact length-delimited key required')
        _numeric(value)
    # C1(map) calls ValueC2; then clears blank+08 and key-user-byte+30.
    # It copies the map's shared_ptr entries; this is not a deep Value clone.
    return FlatNumericMC(dict(sorted(rows.items())),bytearray(16),0)

def current_leaf_from_result(current):
    from .numeric_current_input_reference import StoredCents
    from .current_numeric_leaf_reference import _construct,leaf_report
    field=current['current_field'];instance=current['raw_current_instance']
    if field['source_storage']!='stored' or field['kind']!=11:
        raise SourceInputOutsideProfile('Existing actual kind11 source FV required')
    if not instance['has_value']or not(field['FV_attributes']&1):
        raise SourceInputOutsideProfile('Selected bounded MC path requires actual Used1; Unused/absent is not numeric zero or an invented MC shape')
    if instance['error68']or field['value_header']!=0 or field['format_flag10']!=0:
        raise SourceInputOutsideProfile('Ordinary actual source protocol required; no supplied Error success')
    record=StoredCents(field['kind'],int(field['raw64']),field['FV_attributes'],field['value_header'],
        field['format_flag10'],field['flag11'],field['packed_exponent'])
    leaf,protocol=_construct(record)
    if protocol!=instance or leaf_report(leaf)!=current['direct_numeric_leaf']:
        raise SourceInputOutsideProfile('Same-source current FV conversion mismatch')
    return leaf

@dataclass(frozen=True)
class SourceInstance:
    tps_path:bytes
    mef_path:bytes
    leaf:object

class OwnedCurrentMCReceiver:
    """Fresh own caches supplied only by actual independent execution.

    One supported current source child fills the complete selected-owner
    vector. This is not the native GetValuesHelper or a native event context.
    """
    def __init__(self,node_id,ancestor,instance):
        from .owned_MC_nodes_reference import OwnedMCNodeList
        from .MC_input_query_reference import OwnedInstanceCaches
        if(type(node_id)is not bytes or type(ancestor)is not bytes
                or type(instance)is not SourceInstance):
            raise SourceInputOutsideProfile('Internally derived finite source identities required')
        self.node_id=node_id;self.ancestor=ancestor;self.instance=instance
        self.typed_values={};self.instances=OwnedInstanceCaches();self.nodes=OwnedMCNodeList()
        self.source_enumerations=0;self.typed_cache_hits=0;self.cache_misses=0
    def get_value(self):
        from .owned_MC_nodes_reference import OwnedMCNodeList
        from .MC_input_query_reference import OwnedInstanceCaches
        from .MC_leaf_selection_reference import LeafInstance,select_leaf
        if self.node_id in self.typed_values:
            self.typed_cache_hits+=1;return self.typed_values[self.node_id]
        self.cache_misses+=1
        first=self.instances.query(self.node_id,(),need_MC_nodes=True)
        if first['hit']:raise AssertionError('Unpopulated owned receiver unexpectedly had an instance cache hit')
        # The request adapter has enumerated every matching source child and
        # required exactly one, so this vector is complete for this OWN scope.
        self.source_enumerations+=1
        source=self.instance
        vector=(LeafInstance(source.mef_path,source.leaf),)
        node=self.nodes.update(source.mef_path)
        if node is None or len(self.nodes.roots)!=1 or node.children:
            raise SourceInputOutsideProfile('Exact one-level source MC prefix required')
        self.instances.instances[self.node_id]=vector
        self.instances.MC_nodes[self.node_id]=self.nodes
        supplied=self.instances.query(self.node_id,(),need_MC_nodes=True)
        if not supplied['hit']or supplied['MC_nodes']is not self.nodes:
            raise AssertionError('Owned instance/node cache producer failed')
        match=re.fullmatch(re.escape(self.ancestor)+rb'\[([^\[\]/]+)\]',node.path)
        if match is None:raise SourceInputOutsideProfile('Source-produced MC prefix/component mismatch')
        selected=select_leaf(supplied['values'],source.mef_path)
        if selected is None or selected.payload is not source.leaf:
            raise SourceInputOutsideProfile('Exactly one actual source leaf required after native prefix/dedup semantics')
        value=map_constructor({match[1]:selected.payload})
        self.typed_values[self.node_id]=value
        return value

def value_report(value):
    from .postcopy_cache_reference import _mc
    from .current_numeric_leaf_reference import leaf_report
    from .MC_leaf_selection_reference import ErrorScalar,ErrorMC,get_error
    _mc(value)
    own_word=struct.unpack_from('<Q',value.base_8_17,8)[0]
    error_tree=ErrorMC(own_word,tuple(ErrorScalar(struct.unpack_from('<Q',v.base_8_17,8)[0])for v in value.rows.values()))
    return dict(type='MC',top_blank=bool(value.base_8_17[0]),top_UserInput=bool(value.base_8_17[1]),
        top_flag_word=str(own_word),user_entered_key_byte=value.user_entered_key_byte,
        entries=[dict(key_hex=k.hex(),key=k.decode('ascii')if k.isascii()else None,value=leaf_report(v))for k,v in sorted(value.rows.items())],
        Error=get_error(error_tree),source_precision=2,Decimal_values_not_whole_dollar_rounding=True)
