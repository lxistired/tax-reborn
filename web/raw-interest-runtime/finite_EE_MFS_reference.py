"""Independent finite MFS EE output reduction, with unresolved values untouched.

Normal-return output invariants do not execute native eager dependencies,
allocations, exceptions or explanations. An unresolved producer is never a
Boolean/amount placeholder and cannot be read as one.
"""
from decimal import Decimal
import hashlib,json

class EEMFS:
 def __init__(self,program,*,expected_sha256,inputs):
  if hashlib.sha256(json.dumps(program,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=expected_sha256:raise ValueError('Approved EE source program changed')
  if type(program)is not dict or set(program)!={'roots','nodes'}or program['roots']!=[11746,15102,15111,15122,15166,15167]or type(program['nodes'])is not list or len(program['nodes'])!=32:raise ValueError('Exact finite source EE program required')
  self.nodes={n['reference']:n for n in program['nodes']};self.program=program;self.cache={};self.trace=[];self.proofs=[];self.active=set();self.inputs=inputs
  if len(self.nodes)!=32 or type(inputs)is not dict or set(inputs)!={9723,9803,9847}or type(inputs.get(9723))is not bool or inputs!={9723:False,9803:b'Married',9847:b'3'}:raise ValueError('Actual source-selected MFS and Married canonical current values required')
  self.unresolved={r:'boolean'for r in(11664,11667,11672,11726,11727,11739,11740,15110,15121,15120)};self.unresolved.update({11743:'string',15165:'numeric'})
  for r,n in self.nodes.items():
   if r in self.unresolved:
    if n!={'reference':r,'type':'unresolved_'+self.unresolved[r]}:raise ValueError('Unresolved source marker cannot be supplied/retyped')
   elif n['type']=='input':
    if n!={'reference':r,'type':'input'}or r not in inputs:raise ValueError('Unknown current EE input protocol')
   elif n['type']=='constant':
    if set(n)!={'reference','type','value_type','value'}or n['value_type']not in('boolean','string','numeric'):raise ValueError('Unknown current EE constant protocol')
   elif n['type']=='calculated':
    if set(n)!={'reference','type','gist','inputs','configuration','round_precision'}or n['gist']not in('Equals','AtLeastOneConditionTrue','Opposite','MFJMFSQualifier','BooleanChoice','StringChoice','StringCopy','AllConditionsTrue','SimpleNumericCaseSelector','NumericCopyIfApplicable')or n['round_precision']not in(None,0):raise ValueError('Unsupported EE instruction or postprocessing')
   else:raise ValueError('Unsupported source EE node type')
 def proof(self,r,kind,unread,**kw):self.proofs.append(dict(reference=r,kind=kind,unread_references=unread,normal_return_value_invariant=True,native_dependency_schedule_executed=False,**kw))
 def get(self,r):
  if r in self.cache:return self.cache[r]
  if r not in self.nodes or r in self.active:raise ValueError('Unknown/cyclic source EE dependency')
  n=self.nodes[r];self.active.add(r)
  if r in self.unresolved:raise ValueError('Unclosed source EE producer remains unread; no prepared replacement')
  if n['type']=='input':v=self.inputs[r]
  elif n['type']=='constant':
   if n['value_type']=='boolean'and type(n['value'])is bool:v=n['value']
   elif n['value_type']=='string'and type(n['value'])is str and n['value'].isascii():v=n['value'].encode()
   elif n['value_type']=='numeric'and type(n['value'])is str:v=Decimal(n['value'])
   else:raise ValueError('Typed source EE constant required')
  else:
   name=n['gist'];ins=n['inputs'];cfg=n['configuration']
   def sig(roles,config={}):
    if ins!=roles or cfg!=config:raise ValueError('Original EE role/configuration signature differs')
   if r==11673:
    sig({'Condition':[11664,11665,11667,11672]})
    if self.get(11665)is not True:raise ValueError('Married source OR invariant unavailable')
    v=True;self.proof(r,'true operand fixes OR result',[11664,11667,11672],known_true_reference=11665)
   elif name=='Equals':
    if cfg or set(ins)!={'Value'}or len(ins['Value'])!=2:raise ValueError('Two typed EE equality values required')
    a,b=map(self.get,ins['Value'])
    if type(a)is not bytes or type(b)is not bytes:raise ValueError('Present source string EE equality required')
    v=a==b
   elif name=='Opposite':
    sig({'Value':[9723]});a=self.get(9723)
    if type(a)is not bool:raise ValueError('Present EE Boolean Opposite required')
    v=not a
   elif name=='MFJMFSQualifier':
    sig({'FinalFilingStatus':[9723],'MaritalStatus':[9803],'ConsideredMarried':[11673],'WantToFileJoint':[11675]});a,b=self.get(11673),self.get(11675)
    if type(a)is not bool or type(b)is not bool:raise ValueError('Typed mapped qualifier conditions required')
    v=a and b
   elif name in('BooleanChoice','StringChoice'):
    if set(ins)!={'Possibility','Choice'}or len(ins['Choice'])!=1 or set(cfg)!={'choice'}:raise ValueError('Exact source Choice protocol required')
    c=self.get(ins['Choice'][0]);text=b'true'if c is True else b'false'if c is False else c
    if type(text)is not bytes:raise ValueError('Present typed source Choice required')
    spec=cfg['choice'];opts=spec.get('options',[])
    if set(spec)!={'options','default'}or not opts or any(set(o)!={'value','reference','no_other_option'}or type(o['value'])is not str or not o['value'].isascii()or o['no_other_option']is not True for o in opts):raise ValueError('Exact literal source Choice options required')
    hits=[o for o in opts if o['value'].encode()==text]
    if len(hits)!=1:raise ValueError('Finite EE requires one exact selected option; no fallback is inferred')
    target=hits[0]['reference']
    if target not in ins['Possibility']:raise ValueError('Unknown EE selected source possibility')
    v=self.get(target)
    if name=='BooleanChoice'and type(v)is not bool or name=='StringChoice'and type(v)is not bytes:raise ValueError('Exact selected source Choice type required')
    self.proof(r,'selected literal option fixes returned possibility',[x for x in ins['Possibility']if x!=target],selected_reference=target,choice_text_hex=text.hex())
   elif name=='StringCopy':
    sig({'Value':[11745]});v=self.get(11745)
    if type(v)is not bytes:raise ValueError('Present source final status string required')
   elif r==15111:
    sig({'Condition':[15110],'OppositeCondition':[15102]})
    if self.get(15102)is not True:raise ValueError('Source MFS exclusion invariant unavailable')
    v=False;self.proof(r,'true opposite operand fixes AND result',[15110],known_true_opposite_reference=15102)
   elif r==15122:
    sig({'Condition':[15121,15111]})
    if self.get(15111)is not False:raise ValueError('Source false eligibility invariant unavailable')
    v=False;self.proof(r,'false operand fixes AND result',[15121],known_false_reference=15111)
   elif r==15166:
    if name!='SimpleNumericCaseSelector'or ins!={'Result':[1591,15165],'Condition':[15120,15122,15102]}or set(cfg)!={'selector'}:raise ValueError('Exact source EE numeric selector required')
    expected={'cases':[{'result':15165,'predicates':[['True',15122],['False',15120],['False',15102]]},{'result':1591,'predicates':[['True',15102]]}],'default':1591}
    if cfg['selector']!=expected or self.get(15122)is not False or self.get(15102)is not True:raise ValueError('Exact source MFS numeric selector branch unavailable')
    v=self.get(1591);self.proof(r,'first case disproved; second case selects original zero',[15120,15165],selected_reference=1591)
   elif name=='NumericCopyIfApplicable':
    sig({'Value':[15166],'ApplicableCondition':[15122]});a=self.get(15166);condition=self.get(15122)
    if type(a)is not Decimal or type(condition)is not bool:raise ValueError('Typed source EE amount and applicability required')
    v=a if condition else None
   else:raise ValueError('Unsupported source EE execution branch')
   if n['round_precision']is not None and(v is not None and(type(v)is not Decimal or v!=v.to_integral_value())):raise ValueError('Nonidentity EE dollar rounding unsupported')
  self.active.remove(r);self.cache[r]=v;self.trace.append(r);return v
 def run(self):return{r:self.get(r)for r in self.program['roots']}
