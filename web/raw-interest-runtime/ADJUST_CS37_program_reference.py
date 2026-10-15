"""Exact original CS37 decoder; normal-value VM will retain native-call cuts."""
import struct,hashlib
from dataclasses import dataclass
from decimal import Decimal as D

SOURCE_OPS={1,3,4,7,8,9,0xf,0x10,0x11,0x13,0x15,0x20,0x51,0x52,0x56,0x57,0x58,0x59,0x6d,0x71,0x72,0x83,0x84,0x85}

def decode(body,expected_sha256):
 if type(body)is not bytes or hashlib.sha256(body).hexdigest()!=expected_sha256:raise ValueError('Host-approved exact original CS37 body required')
 if len(body)!=701 or struct.unpack_from('<HHHHBH',body)!=(31,670,8,2,0,0):raise ValueError('Exact CS37 header required')
 types=tuple(body[11:19]);arrays=tuple(struct.unpack_from('<HHH',body,19+6*i)for i in range(2))
 if types!=(10,10,10,10,10,11,11,7)or arrays!=((6,7,0),(7,7,0)):raise ValueError('Actual local/array types and capacity required')
 rows=[];pc=31
 while pc<len(body):
  at=pc;op=body[pc];pc+=1
  if op not in SOURCE_OPS:raise ValueError('Unknown CS37 opcode refused')
  if op in(1,3,4,0x20,0x56,0x57,0x58,0x59):size=2
  elif op in(0x83,0x84,0x85):size=3
  elif op==0x52:size=4
  elif op==0x6d:size=9
  elif op==0x51:
   try:size=body.index(0,pc)+1-pc
   except ValueError:raise ValueError('Unterminated original String literal')
  else:size=0
  if pc+size>len(body):raise ValueError('Truncated CS37 instruction')
  rows.append(dict(pc=at,opcode=op,payload_hex=body[pc:pc+size].hex(),raw_sha256=hashlib.sha256(body[at:pc+size]).hexdigest()));pc+=size
 boundaries={r['pc']for r in rows}|{len(body)}
 if any(struct.unpack('<H',bytes.fromhex(r['payload_hex']))[0]not in boundaries for r in rows if r['opcode']in(1,3,4)):raise ValueError('Original jump must target an instruction boundary')
 if any(r['opcode']==0x58 and r['payload_hex']=='0400'for r in rows):raise ValueError('LastIndex INT result is no longer dead; finite source assumption changed')
 return dict(local_types=types,array_meta=arrays,instructions=rows,body_sha256=expected_sha256,dead_INT_LastIndex_result_local=4,normal_INT_query_success_remains_required=True)
