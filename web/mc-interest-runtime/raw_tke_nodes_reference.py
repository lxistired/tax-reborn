"""Independent bounded XPRF/protobuf wire decoder; no vendor descriptor/code.

Schema entries are factual wire field numbers/types. Caller supplies original
bytes and externally approved content identities. No tax program/table payload
is included. Indexing a node does not authorize or execute its instruction.
"""
from dataclasses import dataclass
import hashlib,struct
MAX_CARRIER=128*1024*1024
MAX_RESOURCE=64*1024*1024
# number -> (own field name, wire kind/message, repeated)
SCHEMAS={
 'Header':{1:('artifact_metadata','Artifact',False),2:('num_nodes','u32',False),3:('has_sort_data','bool',False)},
 'Artifact':{1:('version_info','Version',False)},'Version':{1:('version','u32',False),2:('min_supported_version','u32',False)},
 'Node':{1:('type','u32',False),2:('node_id','text',False),3:('node_reference','u32',False),4:('post_processing','Post',False),5:('calculated_node','Calculated',False),6:('error_check_node','ErrorCheck',False),7:('manipulated_node','Manipulated',False)},
 'Manipulated':{1:('manipulator_id','text',False)},
 'Calculated':{1:('flags','Flags',False),2:('gist','Gist',False),3:('inputs','Input',True),4:('assign_statement','Assignment',False),5:('iterator','Iterator',False),6:('blank_condition','Blank',False),7:('error_condition','Errors',False),8:('extra_values','Extra',True),9:('pertinent_data_rounders','NamedRounder',True),10:('manipulated_nodes','u32',True),11:('aliases','text',True)},
 'Flags':{1:('can_auto_iterate','bool',False),2:('can_optimize','bool',False),3:('explanation_only','bool',False),4:('has_manual_iteration','bool',False),5:('does_autoblanking','bool',False),6:('auto_iteration_version','u32',False)},
 'Input':{1:('role','text',False),2:('node_references','u32',True)},
 'Assignment':{1:('type','u32',False),2:('condition','u32',False),3:('condition_reference','u32',False),4:('reset_condition_reference','u32',False)},
 'Iterator':{1:('ignore_non_corresponding_list_size','bool',False),2:('iterated_inputs','u32',True),3:('optional_inputs','u32',True),4:('sub_iterator','Iterator',False)},
 'Blank':{1:('type','u32',False),2:('condition_reference','u32',False),3:('output_blank_values','bool',False)},
 'Extra':{1:('role','text',False),2:('node_reference','text',False),3:('rounder','Rounder',False)},
 'Gist':{1:('name','text',False),2:('configuration_values','Configuration',True)},
 'Configuration':{1:('name','text',False),2:('scalar_value','Scalar',False),3:('complex_value','Complex',False)},
 'Scalar':{1:('type','u32',False),2:('is_blank','bool',False),3:('numeric_value','Numeric',False),4:('boolean_value','bool',False),5:('string_value','text',False),7:('multicopy_value','MultiCopy',False)},
 'Numeric':{1:('number','i64',False),2:('exponent','u32',False),3:('precision','i32',False),4:('units','u32',False),5:('overflowed','bool',False)},
 'MultiCopy':{1:('values','NamedScalar',True)},'NamedScalar':{1:('key','text',False),2:('value','Scalar',False)},
 'Complex':{1:('elements','Configuration',True)},
 'ErrorCheck':{1:('calculated_node','Calculated',False),2:('metadata_entries','NamedErrorMetadata',True),3:('error_field_reference','u32',False)},
 'NamedErrorMetadata':{1:('key','text',False),2:('value','ErrorMetadata',False)},
 'ErrorMetadata':{1:('type','u32',False),2:('value','text',False),3:('node_reference','u32',False)},
 'Errors':{1:('items','ErrorItem',True)},'ErrorItem':{1:('type','u32',False),2:('condition_reference','u32',False)},
 'Post':{1:('rounder','Rounder',False),2:('flags','u32',False)},
 'Rounder':{1:('type','u32',False),2:('dec_precision','i32',False),3:('inner_rounder','Rounder',False),4:('struct_rounder','StructRounder',False)},
 'StructRounder':{1:('elements','NamedRounder',True)},'NamedRounder':{1:('key','text',False),2:('value','Rounder',False)},
 'SortNodes':{1:('sort_index_dependencies','SortEntry',True)},'SortEntry':{1:('key','u32',False),2:('value','SortDependencies',False)},'SortDependencies':{1:('node_references','u32',True)}
}

def sha(data):return hashlib.sha256(data).hexdigest()
def identity(data,expected):
 if type(expected)is not str or len(expected)!=64 or any(c not in'0123456789abcdef'for c in expected)or sha(data)!=expected:raise ValueError('External approved original content identity required')

def read_xprf_directory(data,*,expected_sha256):
 if type(data)is not bytes or not 16<=len(data)<=MAX_CARRIER:raise ValueError('Bounded complete caller-owned XPRF bytes required')
 identity(data,expected_sha256)
 if data[:10]!=b'XPRF\0\1\x10\x0c\x0a\0':raise ValueError('Unsupported original XPRF profile')
 count=struct.unpack_from('<I',data,12)[0];end=16+12*count
 if not 1<=count<=100000 or end>len(data):raise ValueError('Complete bounded XPRF directory required')
 records={};spans=[]
 for i in range(count):
  typ,rid,offset,size=struct.unpack_from('<HHII',data,16+12*i)
  if(typ,rid)in records or size<10 or offset<end or offset+size>len(data):raise ValueError('XPRF duplicate/bounds violation')
  if struct.unpack_from('<IIH',data,offset)!=(size,size-10,0):raise ValueError('Unsupported resource record framing')
  records[typ,rid]=(offset,size);spans.append((offset,offset+size))
 spans.sort()
 if any(b>c for(a,b),(c,d)in zip(spans,spans[1:])):raise ValueError('Overlapping XPRF records refused')
 return records

def varint(data,position,end):
 start=position;value=0
 for shift in range(0,70,7):
  if position>=end:raise ValueError('Truncated protobuf varint')
  b=data[position];position+=1
  if shift==63 and b>1:raise ValueError('Protobuf uint64 overflow')
  value|=(b&127)<<shift
  if b<128:
   if position-start>1 and b==0:raise ValueError('Noncanonical protobuf varint refused')
   return value,position
 raise ValueError('Unterminated protobuf varint')

def fields(data,start=0,end=None):
 end=len(data)if end is None else end;position=start;count=0
 while position<end:
  count+=1
  if count>100000:raise ValueError('Finite protobuf field budget exceeded')
  at=position;tag,position=varint(data,position,end);number,wire=tag>>3,tag&7
  if not 1<=number<1<<29:raise ValueError('Invalid protobuf field number')
  if wire==0:value,position=varint(data,position,end)
  elif wire==2:
   size,position=varint(data,position,end)
   if size>end-position:raise ValueError('Truncated protobuf bytes')
   value=(position,position+size);position+=size
  elif wire in(1,5):
   size=8 if wire==1 else 4
   if size>end-position:raise ValueError('Truncated protobuf fixed field')
   value=(position,position+size);position+=size
  else:raise ValueError('Protobuf groups/unknown wire kind unsupported')
  yield number,wire,value,at,position

def decode_message(data,schema,*,start=0,end=None,depth=0):
 if schema not in SCHEMAS or depth>64:raise ValueError('Unknown/deep protobuf message refused')
 output={};unknown=[];seen=set();spec=SCHEMAS[schema]
 for number,wire,value,a,z in fields(data,start,end):
  if number not in spec:unknown.append(dict(field_number=number,wire_type=wire,hex=bytes(data[a:z]).hex()));continue
  name,kind,repeated=spec[number]
  if not repeated and number in seen:raise ValueError('Ambiguous duplicate singular protobuf field refused')
  seen.add(number);values=[]
  if repeated and kind in('u32','i32','i64','bool')and wire==2:
   p,stop=value
   while p<stop:
    v,p=varint(data,p,stop);values.append(v)
  else:values=[value]
  decoded=[]
  for value in values:
   if kind in('u32','i32','i64','bool'):
    if wire!=0 and not(repeated and wire==2):raise ValueError('Wrong scalar protobuf wire type')
    if kind=='u32':
     if value>0xffffffff:raise ValueError('Protobuf u32 overflow')
    elif kind=='bool':
     if value not in(0,1):raise ValueError('Canonical Boolean wire required')
     value=bool(value)
    elif kind=='i64':value=value-(1<<64)if value&(1<<63)else value
    else:
     signed=value-(1<<64)if value&(1<<63)else value
     if not-(1<<31)<=signed<(1<<31):raise ValueError('Protobuf i32 overflow')
     value=signed
   elif kind=='text':
    if wire!=2:raise ValueError('Wrong protobuf text wire type')
    a,z=value
    if z-a>MAX_RESOURCE:raise ValueError('Bounded protobuf text required')
    try:value=bytes(data[a:z]).decode('utf-8')
    except UnicodeError as error:raise ValueError('Invalid original protobuf UTF8')from error
   else:
    if wire!=2:raise ValueError('Wrong protobuf message wire type')
    a,z=value;value=decode_message(data,kind,start=a,end=z,depth=depth+1)
   decoded.append(value)
  if repeated:output.setdefault(name,[]).extend(decoded)
  else:output[name]=decoded[0]
 if unknown:output['uninterpreted_fields']=unknown
 return output

@dataclass(frozen=True)
class NodeFrame:
 reference:int
 node_id:str
 node_type:int
 start:int
 end:int
 sha256:str
@dataclass(frozen=True)
class NodeTable:
 carrier:bytes
 carrier_sha256:str
 resource_offset:int
 resource_size:int
 payload_start:int
 payload_end:int
 payload_sha256:str
 header:dict
 header_frame:tuple
 sort_frame:tuple
 frames:dict
 def decode(self,reference):
  if type(reference)is not int or reference not in self.frames:raise ValueError('Existing source node reference required')
  f=self.frames[reference];return decode_message(self.carrier,'Node',start=f.start,end=f.end)

def read_node_table(carrier,*,approved_carrier_sha256,approved_payload_sha256,resource_type=5036,resource_id=1):
 if type(resource_type)is not int or type(resource_id)is not int or(resource_type,resource_id)!=(5036,1):raise ValueError('Finite original TKE graph resource profile required')
 directory=read_xprf_directory(carrier,expected_sha256=approved_carrier_sha256)
 if(resource_type,resource_id)not in directory:raise ValueError('Required original TKE graph resource absent')
 offset,size=directory[resource_type,resource_id];start=offset+10;end=offset+size;payload=memoryview(carrier)[start:end];identity(payload,approved_payload_sha256)
 if not 4<=len(payload)<=MAX_RESOURCE or struct.unpack_from('<I',payload)[0]!=len(payload)-4:raise ValueError('Complete graph length frame required')
 p=start+4;framed=[]
 while p<end:
  length,begin=varint(carrier,p,end);finish=begin+length
  if not 0<length<=MAX_RESOURCE or finish>end or len(framed)>100002:raise ValueError('Bounded complete graph frames required')
  framed.append((begin,finish));p=finish
 if len(framed)<2:raise ValueError('Header and sort trailer graph frames required')
 header=decode_message(carrier,'Header',start=framed[0][0],end=framed[0][1]);count=header.get('num_nodes',0)
 if type(count)is not int or not 0<count<=100000 or len(framed)!=count+2 or header.get('uninterpreted_fields'):raise ValueError('Graph complete declared node count required')
 if header!={'artifact_metadata':{'version_info':{'version':2,'min_supported_version':1}},'num_nodes':count,'has_sort_data':True}:raise ValueError('Only exact reviewed graph header/version2 profile supported')
 nodes={};ids=set()
 for a,z in framed[1:-1]:
  # Index only identity fields; active nested instructions decode on demand.
  base={}
  for number,wire,value,at,stop in fields(carrier,a,z):
   if number not in(1,2,3):continue
   if number in base:raise ValueError('Duplicate original graph node identity field')
   if number==2:
    if wire!=2:raise ValueError('Node ID text wire required')
    x,y=value
    try:value=carrier[x:y].decode('utf-8')
    except UnicodeError as error:raise ValueError('Node ID UTF8 required')from error
   elif wire!=0 or value>0xffffffff:raise ValueError('Node identity unsigned32 wire required')
   base[number]=value
  ref,nodeid,typ=base.get(3,0),base.get(2,''),base.get(1,0)
  if not ref or not nodeid or '\0'in nodeid or ref in nodes or nodeid in ids or not 0<=typ<=7:raise ValueError('Unique nonempty original graph identities required')
  nodes[ref]=NodeFrame(ref,nodeid,typ,a,z,sha(memoryview(carrier)[a:z]));ids.add(nodeid)
 # Structural interpretation is separate from source provenance and execution.
 decode_message(carrier,'SortNodes',start=framed[-1][0],end=framed[-1][1])
 return NodeTable(carrier,approved_carrier_sha256,offset,size,start,end,approved_payload_sha256,header,framed[0],framed[-1],nodes)
