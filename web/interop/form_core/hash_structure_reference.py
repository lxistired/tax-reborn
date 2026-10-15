"""Strict finite Hash topology guard before any current-value interpretation.

Allocated storage is not presence and is not proof of bucket reachability.
Every represented used allocation slot must appear once in its correct complete
bucket chain. This independent profile rejects inconsistent sources; it never
repairs or drops nodes. No native acceptance or tax calculation is implied.
"""
NULL=0xffffffff

def validate_hash_structure(state):
    if type(state.heads) is not tuple or not 1<=len(state.heads)<=16000 or type(state.buffers) is not tuple:
        raise ValueError('Source hash requires a supported explicit head vector and buffers.')
    nodes={};keys=set();base=0
    for block in state.buffers:
        if (type(block.capacity) is not int or not 0<=len(block.nodes)<=block.capacity<=2700
                or type(block.nodes) is not tuple):
            raise ValueError('Source hash buffer has inconsistent allocation bounds.')
        for i,node in enumerate(block.nodes):
            key=node.field_index,node.element_index
            if any(type(v) is not int or not 0<=v<=65535 for v in key) or key in keys:
                raise ValueError('Source hash has invalid or duplicate field/element keys.')
            keys.add(key);nodes[base+i]=node
        base+=block.capacity
    visited=set();nonempty=0
    for bucket,head in enumerate(state.heads):
        index=head;local=set()
        if head!=NULL:nonempty+=1
        while index!=NULL:
            if type(index) is not int or not 0<=index<NULL or index not in nodes:
                raise ValueError('Source hash has a dangling or out-of-range head/next reference.')
            if index in local:
                raise ValueError('Source hash has a cycle, including a matching node with a cyclic next link.')
            if index in visited:
                raise ValueError('Source hash repeats a node across buckets or chains.')
            node=nodes[index]
            if (node.field_index*3+node.element_index*5)%len(state.heads)!=bucket:
                raise ValueError('Source hash stores a node in the wrong bucket.')
            local.add(index);visited.add(index);index=node.next_index
    if visited!=set(nodes):
        raise ValueError('Source hash has unreachable allocated storage; current values and corrections are blocked.')
    return dict(valid=True,buckets=len(state.heads),nonempty_buckets=nonempty,
                allocated_nodes=len(nodes),reachable_nodes=len(visited),complete_chains_checked=True)

def validate_document_hashes(document):
    rows=[]
    def walk(forms,prefix):
        for index,form in enumerate(forms):
            path=prefix+(index,)
            rows.append(dict(path=list(path),**validate_hash_structure(form.hash_state)))
            walk(form.children,path)
    for index,formset in enumerate(document.formsets):walk(formset.forms,(index,))
    return rows
