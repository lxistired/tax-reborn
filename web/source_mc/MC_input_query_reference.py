"""Fresh source-schema query producers, independent of active native caches."""

def query_from_schema(schema, policy):
    node_id=policy['node_id']
    if type(node_id)is not str or not node_id.isascii()or not node_id.startswith('/Return/')or any(t in node_id for t in ('[',']','@','FieldAttributes','TKEMetaData')):
        raise ValueError('Ordinary exact source amount XPath without instance/metadata syntax required')
    components=node_id.split('/')[1:]
    if schema.tag!=components[0]:raise ValueError('Exact source schema root required')
    cursor=schema;path='/'+schema.tag;parents=[]
    for name in components[1:]:
        matches=cursor.findall(name)
        if len(matches)!=1:raise ValueError('Unique same-schema node ancestry required')
        cursor=matches[0];path+='/'+name
        if cursor.get('multiCopy')=='true':parents.append((path,cursor))
    if cursor.get('multiCopy')=='true'or len(parents)!=1 or parents[0][0]!='/Return/ReturnData/PP1099Int':
        raise ValueError('Finite ordinary field with exactly one actual PP1099Int MC ancestor required')
    ancestor,parent=parents[0]
    # The original GetMultiCopyElements walks parent+18, checks exact+5D==1,
    # reverses to outer-first. GetNodeMultiCopyInfo begins substring offset1.
    relative=(ancestor[1:],)
    full=tuple('/'+x for x in relative)
    # Fresh schema extra data starts0; LoadElement only assigns SortKey for a
    # direct MultiCopyLogicalKey/SortOrder firstchild. No caller Boolean here.
    if parent.find('MultiCopyLogicalKey')is not None:
        raise ValueError('Sort-configured source ancestor outside this finite producer')
    if list(parent.iter('SortOrder')):
        raise ValueError('Unexpected nested source sort metadata refused')
    return dict(raw_node_id=node_id,source_schema_MC_ancestors=[ancestor],
        NodeMultiCopyInfo_relative_segments=list(relative),GetFullAncestorsInnerFirst=list(full),
        conditional_fresh_schema_sort_enum=0,conditional_fresh_schema_SortKeyPresent=False,
        conditional_same_schema_logical_key_extra_paths=[],
        typed_input_cache_198_key=node_id,standardized_Instance_cache_120_key=node_id,
        field_MC_nodes_cache_168_key=node_id,ancestor_MC_list_cache_180_key=''.join(full),
        source_derived_query_keys=True,no_supplied_ancestors_or_sort_flags=True,
        native_active_metadata_or_cache_verified=False,native_MC_inventory_verified=False,
        actual_GetMultiCopyInputValue_result=None,
        normal_fresh_schema_registration_required=True)

class OwnedInstanceCaches:
    """Explicit independent test receiver for the original MC lookup consumer.

    Ctor creates owned empty maps. It is not a native cache snapshot. Populated
    values/MC nodes must be produced by independent execution; the public
    request API never accepts such maps or turns storedPO absence into misses.
    """
    def __init__(self):self.instances={};self.MC_nodes={}
    def query(self,base,extras,*,need_MC_nodes):
        if type(base)is not bytes or type(extras)is not tuple or any(type(x)is not bytes for x in extras)or type(need_MC_nodes)is not bool:
            raise ValueError('Explicit finite byte cache query required')
        if base not in self.instances:return dict(hit=False,values=(),MC_nodes=None,cleared_after_missing_MC_nodes=False)
        values=tuple(self.instances[base]);nodes=None
        if need_MC_nodes:
            if base not in self.MC_nodes:return dict(hit=False,values=(),MC_nodes=None,cleared_after_missing_MC_nodes=True)
            nodes=self.MC_nodes[base]
        # Missing extra paths are ignored; existing extra vectors append in
        # declaration order, including repeated extra keys. No dedup here.
        for key in extras:
            if key in self.instances:values+=tuple(self.instances[key])
        return dict(hit=True,values=values,MC_nodes=nodes,cleared_after_missing_MC_nodes=False)
