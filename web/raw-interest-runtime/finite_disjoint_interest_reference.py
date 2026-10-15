"""Finite flat numeric disjoint-key MC concatenate; no UUID or storage I/O.

All eight source vectors must be explicitly produced. Empty vectors are actual
producer results. Numeric blank/zero/negative members are retained. Collisions
and nested values require other original Merge branches and are refused.
"""
from decimal import Decimal
import hashlib,json
FAMILIES=(14484,14545,14557,14564,14572,14580,14581,14724)

def disjoint_numeric_concatenate(vectors):
 if type(vectors)is not list or len(vectors)!=8:raise ValueError('All eight actually produced source MC vectors required')
 result={};origins={}
 for index,vector in enumerate(vectors):
  if type(vector)is not dict or len(vector)>64:raise ValueError('Explicit bounded flat source MC required; missing is not empty')
  for key,value in vector.items():
   if type(key)is not str or not key.isascii()or not 0<len(key)<=128 or '\0'in key:raise ValueError('Finite owned ASCII comparison labels required')
   if value is not None and(type(value)is not Decimal or not value.is_finite()or abs(value)>Decimal('1e9')):raise ValueError('Only flat finite numeric values or typedblank supported')
   if key in result:raise ValueError('Cross-source key collision requires other native Merge branches; it is not overwritten or renamed')
   result[key]=value;origins[key]=FAMILIES[index]
 if len(result)>128:raise ValueError('Finite merged source domain exceeded')
 return {k:result[k]for k in sorted(result)},origins

class SourceCollection:
 def __init__(self,program,*,expected_sha256,components):
  if hashlib.sha256(json.dumps(program,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=expected_sha256:raise ValueError('Approved combined source program changed')
  expected=dict(roots=[14725],nodes=[dict(reference=r,type='component')for r in FAMILIES]+[dict(reference=14725,type='calculated',gist='MultiCopyConcatenate',inputs={'Value':list(FAMILIES)})])
  if program!=expected:raise ValueError('Exact original eight-family MC concatenation instruction required')
  if type(components)is not dict or set(components)!=set(FAMILIES):raise ValueError('All eight source families must actually be calculated')
  self.components=components;self.origins={};self.trace=[]
 def run(self):
  values,self.origins=disjoint_numeric_concatenate([self.components[r]for r in FAMILIES]);self.trace=list(FAMILIES)+[14725];return{14725:values}
