"""Exact bounded CS24 declaration decoder; native queries/transaction not run."""
import hashlib,struct
OPS={7,0x51,0x52,0x56,0x66,0x6d,0x88,0x89,0x9d,0x9f,0xa1,0xa2}
def decode(body,expected_sha256):
 if type(body)is not bytes or hashlib.sha256(body).hexdigest()!=expected_sha256 or len(body)!=3294 or struct.unpack_from('<HHHHBH',body)!=(15,3279,4,0,0,0)or body[11:15]!=b'\x0a'*4:raise ValueError('Host-approved exact CS24 complete body required')
 rows=[];pc=15
 while pc<len(body):
  at=pc;op=body[pc];pc+=1
  if op not in OPS:raise ValueError('Unknown actual CS24 instruction refused')
  if op in(0x56,0x88,0x89,0x9f,0xa2):n=2
  elif op==0x52:n=4
  elif op==0x6d:n=9
  elif op==0xa1:n=34 if body[pc]==255 else body[pc]+2 if body[pc]<9 else 9
  elif op==0x51:
   try:n=body.index(0,pc)+1-pc
   except ValueError:raise ValueError('Unterminated original CS24 literal')
  else:n=0
  if pc+n>len(body):raise ValueError('Truncated original CS24 instruction')
  raw=body[at:pc+n];rows.append(dict(pc=at,opcode=op,payload_hex=body[pc:pc+n].hex(),raw_sha256=hashlib.sha256(raw).hexdigest()));pc+=n
 if len(rows)!=507 or sum(r['opcode']==0x9d for r in rows)!=1 or any(r['opcode']==0x58 for r in rows):raise ValueError('Exact no-read query locals/one declaration transaction required')
 mark=next(i for i,r in enumerate(rows)if r['opcode']==0x9d)
 if [bytes.fromhex(r['payload_hex'])for r in rows[mark-2:mark]]!=[b'Calc\0',b'CompleteGraph\0']:raise ValueError('Exact CALC mark service required')
 outputs=[]
 for i in range(mark+1,len(rows),4):
  group=rows[i:i+4]
  if len(group)!=4 or [r['opcode']for r in group]!=[0x89,0x52,0x52,0x9f]or group[0]['payload_hex']!='0000'or group[2]['payload_hex']!='00000000'or group[3]['payload_hex']!='0100':raise ValueError('Exact current scalar output declarations required')
  outputs.append(dict(declaration_pc=group[-1]['pc'],current_field_ordinal=struct.unpack('<i',bytes.fromhex(group[1]['payload_hex']))[0],element_operand=0,native_TPS_commit_executed=False))
 if len(outputs)!=39:raise ValueError('Complete original CS24 output set required')
 return dict(body_sha256=expected_sha256,instructions=rows,output_declarations=outputs,query_local_results_are_dead=True,native_query_and_transaction_executed=False)
