"""Stable semantic readback for the ordinary modern Document codec.

Only source-established Store normalizations are ignored: allocation padding,
Common transient bytes, runtime flags/counters, active slot offsets, tombstone
records removed by StringTable.Pack, and final unused Hash allocation capacity.
Live records, free-chain state, every Node wire bit, references and opaque
serialized header additions remain observable. This is not native acceptance.
"""
from dataclasses import fields,is_dataclass
from .form_header_map_reference import store_header
from .value_hash_wire_reference import pack_node,validate as validate_hash
from .string_wire_reference import records,validate as validate_table
from .native_document_reference import Document,UnsupportedProfile

def _plain(value):
 if type(value) is bytes:return value.hex()
 if is_dataclass(value):return {f.name:_plain(getattr(value,f.name)) for f in fields(value)}
 if type(value) is tuple:return [_plain(v) for v in value]
 if value is None or type(value) in (str,int,bool):return value
 raise UnsupportedProfile('Typed scalar/header snapshot only')

def hash_semantic_snapshot(state):
 """Preserve each used node's original global index, all23serialized bytes."""
 validate_hash(state);base=0;nodes=[]
 for block in state.buffers:
  nodes.extend([base+i,pack_node(node).hex()] for i,node in enumerate(block.nodes))
  base+=block.capacity
 return {'wide':state.wide,'heads':list(state.heads),'indexed_used_nodes':nodes}

def string_table_semantic_snapshot(table):
 """Keep active handles/order, chunkIDs/capacities and exact free-list links."""
 validate_table(table);by_chunk=[records(c) for c in table.chunks];slots=[]
 import struct
 for handle in range(len(table.slots)//4):
  chunk,offset=struct.unpack_from('<2H',table.slots,handle*4)
  if chunk:slots.append(['active',chunk,by_chunk[chunk-1][offset][1].hex()])
  else:slots.append(['free',offset])
 chunks=[]
 for chunk,physical in zip(table.chunks,by_chunk):
  live=[[handle,text.hex()] for handle,text,_ in physical.values() if handle!=65535]
  chunks.append({'capacity':len(chunk.data),'active_physical_order':live})
 return {'config':list(table.config),'free_head':table.free_head,'slots':slots,'chunks':chunks}

def _header_wire(form):
 if form.metadata.get('source_header')==form.header:
  raw=form.metadata.get('source_header_wire')
  if type(raw) is not bytes:raise UnsupportedProfile('Source header bytes required')
  return raw.hex()
 raw,code=store_header(form.header)
 if code:raise UnsupportedProfile('Successful header store required')
 return raw.hex()

def _link(link):
 description=(link.form_id,link.file_copy,link.field_id,link.element_index)
 element=link.element_index
 if link.metadata.get('source_description')==description:
  element=link.metadata.get('source_element_u32',element)
 return {'form_id':link.form_id.hex(),'file_copy':link.file_copy,
         'field_id':link.field_id.hex(),'element_u32':element}

def document_semantic_snapshot(doc):
 """JSON-compatible whole-document readback; caller may allow selected edits."""
 if not isinstance(doc,Document):raise UnsupportedProfile('Explicit Document')
 def form(f):
  return {'header':_plain(f.header),'serialized_header_wire':_header_wire(f),
   'table_id':f.table_id,'hash':hash_semantic_snapshot(f.hash_state),
   'strings':string_table_semantic_snapshot(f.string_table),
   'tables':[{'identifier':t.identifier.hex(),'word28':t.word28,'word2a':t.word2a,
              'table_kind':t.table_kind,'last_used_record_index':t.last_used_record_index} for t in f.tables],
   'children':[form(ch) for ch in f.children],'links':[_link(l) for l in f.links]}
 return {'entity_header':_plain(doc.entity_header),
  'formsets':[{'header':_plain(fs.header),'forms':[form(f) for f in fs.forms]} for fs in doc.formsets]}
