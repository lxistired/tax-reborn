"""Independently owned form projections and the normal MC node builder.

These objects are created here. They are never accepted as request snapshots.
Source form UUID149 seeds only an owned child-form UUID; Record UUID and the
native FormSet list remain unknown. The caller selects the supported source
scope before using this finite implementation.
"""
from dataclasses import dataclass, field
import re

def _bytes(value, maximum=4096):
    if type(value) is not bytes or len(value)>maximum:
        raise ValueError('Bounded length-delimited bytes required')
    return value

@dataclass(eq=False)
class SourceFormProjection:
    owner: object
    form_id: bytes
    runtime_copy_number: int
    document_file_copy: int
    source_path: tuple
    parent: object = None
    saved_form_uuid: object = None

    def __post_init__(self):
        if (type(self.form_id) is not bytes or len(self.form_id)!=32
                or type(self.runtime_copy_number) is not int or not 0<=self.runtime_copy_number<=65535
                or type(self.document_file_copy) is not int or not 0<=self.document_file_copy<1<<32):
            raise ValueError('Exact source ID32/U16 runtime copy/U32 file copy required')
        if self.saved_form_uuid is not None:
            _bytes(self.saved_form_uuid)

def get_forms(inventory, form_id, component=None):
    """Native ID/optional-coordinate comparison on owned source objects only.

    This does not supply native list order or a missing UUID. Numeric syntax
    is deliberately limited to canonical decimal text; the native predicate
    admits more strings before a later string comparison.
    """
    if type(inventory) is not tuple or len(inventory)>256 or type(form_id) is not bytes or len(form_id)!=32:
        raise ValueError('Finite owned inventory and exact ID32 required')
    if component is not None:
        _bytes(component)
        if not component: component=None
    out=[]
    for item in inventory:
        if type(item) is not SourceFormProjection: raise ValueError('Owned source-form projection required')
        if item.form_id!=form_id: continue
        if component is None:
            out.append(item); continue
        if re.fullmatch(rb'(0|[1-9][0-9]{0,4})',component):
            # Original compares formatted word7C with the complete input text.
            if str(item.runtime_copy_number).encode()==component:out.append(item)
        elif re.fullmatch(rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',component):
            if item.saved_form_uuid is None:raise ValueError('Source form UUID not supplied; no default is allowed')
            if len(item.saved_form_uuid)==len(component) and item.saved_form_uuid==component:out.append(item)
        else:raise ValueError('Finite source coordinate classifier excludes this query')
    return tuple(out)

def get_child_forms(inventory,parent,form_id,component=None):
    return tuple(item for item in get_forms(inventory,form_id,component) if item.parent is parent and item.owner is parent.owner)

@dataclass(eq=False)
class MCNode:
    path: bytes
    children: dict = field(default_factory=dict)
    discarded_owned_duplicate: bool = False
    def __post_init__(self): _bytes(self.path)
    def get_child(self,path):return self.children.get(_bytes(path))
    def add_child(self,child):
        if child is None:return None
        if type(child) is not MCNode:raise ValueError('Owned MCNode pointer required')
        if child.path in self.children:
            # Original destroys the incoming duplicate; existing pointer wins.
            child.discarded_owned_duplicate=True
            return self.children[child.path]
        self.children[child.path]=child
        return child

def _MC_prefixes(path):
    _bytes(path)
    if not path or not path.startswith(b'/'):return ()
    if not path.isascii() or b'\0' in path or path.endswith(b'/') or b'//' in path:
        raise ValueError('Finite ordinary slash path only')
    parts=path[1:].split(b'/');prefixes=[];current=b''
    for part in parts:
        match=re.fullmatch(rb'[A-Za-z_][A-Za-z_0-9]*(?:\[([^\[\]/]+)\])?',part)
        if match is None:raise ValueError('Finite ordinary bracket grammar required')
        current+=b'/'+part
        if match[1] is not None:prefixes.append(current)
    return tuple(prefixes)

class OwnedMCNodeList:
    """Fresh owned vector: construction itself creates its empty state."""
    def __init__(self):self.roots=[]
    def update(self,path):
        parent=None;last=None
        for prefix in _MC_prefixes(path):
            if parent is None:
                node=next((n for n in self.roots if len(n.path)==len(prefix) and n.path==prefix),None)
                if node is None:node=MCNode(prefix);self.roots.append(node)
            else:
                node=parent.get_child(prefix)
                if node is None:node=parent.add_child(MCNode(prefix))
            parent=last=node
        return last
    def report(self):
        def row(node):
            return dict(path=node.path.decode('ascii'),children=[row(node.children[k]) for k in sorted(node.children)])
        return [row(node) for node in self.roots]

def source_inventory(document,selected_path,source_uuid):
    """Construct owner/parent identities from this one parsed source tree.

    The list is an app-owned DFS order. Only the selected UUID is seeded from
    its exact saved149 body; other unneeded UUIDs stay unknown, not empty.
    """
    path=tuple(selected_path)
    if len(path)!=3 or type(source_uuid) is not bytes:raise ValueError('Selected direct-child source scope required')
    owner=object();inventory=[]
    def walk(form,p,parent):
        item=SourceFormProjection(owner,form.header.identifier.ljust(32,b' '),form.header.word7c,
            form.header.file_copy,p,parent,source_uuid if p==path else None)
        inventory.append(item)
        for i,c in enumerate(form.children):walk(c,p+(i,),item)
    for i,form in enumerate(document.formsets[path[0]].forms):walk(form,(path[0],i),None)
    return tuple(inventory)

def project_selected(inventory,parent_path,child_path,uuid,tps_path,mef_path,leaf):
    """Execute selected-source comparisons and node creation, no native call.

    Fresh Mapping lookup is an owned dict created here. This is not restoration
    of a 14F cache, a native cache miss, a native FindInstances result or a full
    GetMultiCopyInputValue implementation. It supplies concrete owned objects
    for the next read-side implementation, without accepting prepared state.
    """
    parent_id=b'FSCHB'.ljust(32,b' ');child_id=b'F1099I'.ljust(32,b' ')
    parents=get_forms(inventory,parent_id)
    if len(parents)!=1 or parents[0].source_path!=tuple(parent_path):
        raise ValueError('One exact selected source summary owner required')
    children=get_child_forms(inventory,parents[0],child_id,uuid)
    if len(children)!=1 or children[0].source_path!=tuple(child_path):
        raise ValueError('One exact same-owner/source149 child required')
    mapping={}
    if tps_path in mapping:raise AssertionError('Fresh owned receiver unexpectedly populated')
    mapping[tps_path]=mef_path
    nodes=OwnedMCNodeList();node=nodes.update(mapping[tps_path])
    if node is None:raise ValueError('Source-produced MC instance prefix required')
    first=id(node);again=nodes.update(mapping[tps_path])
    if again is not node:raise AssertionError('Owned MC prefix identity was not reused')
    return dict(identity_kind='app_owned_selected_source_projection',
        owned_parent_path=list(parents[0].source_path),owned_child_path=list(children[0].source_path),
        owned_parent_pointer_identity_checked=True,owned_owner_pointer_identity_checked=True,
        child_runtime_copy_number=children[0].runtime_copy_number,child_document_file_copy=children[0].document_file_copy,
        child_saved_FormUUID=uuid.decode('ascii'),owned_query_TPS_path=tps_path.decode('ascii'),
        owned_Mapping_key=mef_path.decode('ascii'),owned_MC_nodes=nodes.report(),
        repeated_path_reuses_same_owned_node=(id(again)==first),
        source_direct_numeric_leaf=leaf,source_leaf_is_not_invented_zero=True,
        inventory_order='independent source-tree DFS; native list order unknown',
        unknown_other_form_UUIDs_defaulted=False,stored_14D_or_14F_restored=False,
        owned_selected_projection_executed=True,owned_full_FindInstances_executed=False,
        owned_full_GetMultiCopyInputValue_executed=False,
        native_active_inventory_verified=False,native_cache_miss_verified=False,
        native_Record_UUID=None,native_input_error_stage_executed=False,
        native_runtime=0,physical_TPS_writes=0,comparison_only=True,writeback_allowed=False)
