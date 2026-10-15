"""Finite source-program numeric tail; upstream cut points remain explicit.

No filesystem/native I/O, resources, schema or vendor bytecode is embedded here.
A content digest binds the exact supplied model, never authenticates its origin.
"""
from decimal import Decimal
import hashlib,json


def numeric(value):
    if value is not None and(type(value)is not Decimal or not value.is_finite()or abs(value)>Decimal('1e9')or value*100!=(value*100).to_integral_value()):
        raise ValueError('Finite exact cents Decimal or explicit blank required')
    return value

def collection(value):
    if type(value)is not dict or len(value)>64 or any(type(k)is not str or not k or len(k)>128 or '\0'in k for k in value):
        raise ValueError('Complete bounded explicit flat numeric collection required')
    for v in value.values():numeric(v)
    return value

def add(values):
    for v in values:numeric(v)
    return numeric(None if all(v is None for v in values)else sum((v for v in values if v is not None),Decimal(0)))


class TotalTail:
    def __init__(self,program,*,expected_sha256,inputs,scalar_priors,uniform_amt_prior):
        if hashlib.sha256(json.dumps(program,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=expected_sha256:
            raise ValueError('Exact approved program content changed')
        if type(program)is not dict or set(program)!={'roots','nodes'}or type(program['nodes'])is not list or not 1<=len(program['nodes'])<=64:
            raise ValueError('Exact finite graph model required')
        self.program=program;self.nodes={};self.inputs=inputs;self.priors=scalar_priors;self.uniform=uniform_amt_prior
        self.cache={};self.active=set();self.trace=[];self.assignments=[]
        for n in program['nodes']:
            if type(n)is not dict or type(n.get('reference'))is not int or n['reference']in self.nodes:raise ValueError('Unique source node references required')
            self.nodes[n['reference']]=n
        leaves={r for r,n in self.nodes.items()if n.get('type')=='supplied'}
        priors={r for r,n in self.nodes.items()if n.get('assignment')=='scalar_user_entered'}
        if type(inputs)is not dict or set(inputs)!=leaves:raise ValueError('Every upstream cut point must be explicit; no blank defaults')
        if type(scalar_priors)is not dict or set(scalar_priors)!=priors:raise ValueError('Every scalar UserEntered target needs current prior storage')
        if type(uniform_amt_prior)is not dict or uniform_amt_prior.get('all_saved_AMT_priors_absent')is not True:
            raise ValueError('Same-snapshot uniformly absent saved AMT prior required')
        for ref in leaves:
            kind=self.nodes[ref]['supply_kind'];value=inputs[ref]
            if kind=='numeric':numeric(value)
            elif kind=='numeric_collection':collection(value)
            elif kind=='boolean':
                if type(value)is not bool:raise ValueError('This finite tail needs an explicit present Boolean, not guessed blank')
            else:raise ValueError('Unknown typed upstream supply refused')
    def get(self,ref):
        if ref in self.cache:return self.cache[ref]
        if ref in self.active or ref not in self.nodes:raise ValueError('Unknown/cyclic dependency refused')
        self.active.add(ref);n=self.nodes[ref];typ=n['type']
        if typ=='supplied':
            if set(n)!={'reference','type','supply_kind'}:raise ValueError('Unknown supplied-node protocol')
            value=self.inputs[ref]
        elif typ=='constant':
            if set(n)!={'reference','type','value'}or n['value']is not None and type(n['value'])is not str:raise ValueError('Unknown constant protocol')
            value=numeric(Decimal(n['value'])if n['value']is not None else None)
        elif typ=='calculated':
            if set(n)!={'reference','type','gist','inputs','assignment','selector'}:raise ValueError('Unknown configuration/iterator/postprocessing refused')
            roles={role:[self.get(dep)for dep in refs]for role,refs in n['inputs'].items()}
            value=self.apply(n,roles)
            if n['assignment']=='uniform_absent_user_entered':
                value=dict(collection(value));self.assignments.append(dict(reference=ref,computed_value=dict(value),result=dict(value),retained=False,
                    conditional_all_saved_priors_absent=True,physical_row_identity_verified=False))
            elif n['assignment']=='scalar_user_entered':
                numeric(value);prior=self.priors[ref]
                if type(prior)is not dict or set(prior)!={'value','computed','overridden','itemized'}or any(type(prior[k])is not bool for k in('computed','overridden','itemized')):
                    raise ValueError('Explicit ordinary typed prior protocol required')
                numeric(prior['value'])
                if prior['overridden']or prior['itemized']:raise ValueError('Exterior override/itemization assignment protocol is unclosed')
                keep=value is None and prior['value']is not None and not prior['computed'];computed=value
                if keep:value=prior['value']
                self.assignments.append(dict(reference=ref,computed_value=computed,result=value,retained=keep))
            elif n['assignment']!='none':raise ValueError('Unknown assignment protocol')
        else:raise ValueError('Unknown instruction')
        self.active.remove(ref);self.cache[ref]=value;self.trace.append(ref);return value
    def apply(self,n,roles):
        name=n['gist']
        def need(names):
            if set(roles)!=set(names):raise ValueError('Exact role signature required')
        def one(role):
            rows=roles[role]
            if len(rows)!=1:raise ValueError('Exact single role operand required')
            return rows[0]
        if name!='SimpleNumericCaseSelector'and n['selector']is not None:raise ValueError('Unknown nonselector configuration')
        if name=='MultiCopyCopy':need(['Value']);return dict(collection(one('Value')))
        if name=='MultiCopyAccumulation':need(['Value']);return add(list(collection(one('Value')).values()))
        if name=='Accumulation':need(['Value']);return add(roles['Value'])
        if name=='SimpleNumericCaseSelector':
            need(['Result','Condition']);selector=n['selector']
            if type(selector)is not dict or set(selector)!={'condition','when_true','default'}:raise ValueError('One source-bound selector case/default required')
            condition=self.get(selector['condition'])
            if type(condition)is not bool:raise ValueError('Explicit typed present selector Boolean required')
            target=selector['when_true']if condition else selector['default']
            if selector['condition']not in n['inputs']['Condition']or target not in n['inputs']['Result']:raise ValueError('Selector graph references differ')
            return numeric(self.get(target))
        if name=='IsNotBlank':need(['Value']);return one('Value')is not None
        if name=='Not':
            need(['Value']);value=one('Value')
            if type(value)is not bool:raise ValueError('Explicit present Boolean required')
            return not value
        if name=='NumericCopyIfApplicable':
            need(['Value','ApplicableCondition']);value=numeric(one('Value'));condition=one('ApplicableCondition')
            if type(condition)is not bool:raise ValueError('Typed present applicability required')
            return value if condition else None
        if name=='Difference':
            need(['Left','Right']);left=numeric(one('Left'));right=numeric(one('Right'))
            return None if left is None and right is None else numeric((Decimal(0)if left is None else left)-(Decimal(0)if right is None else right))
        if name=='MaximumTreatBlankAsZero':
            need(['Value']);values=roles['Value']
            for value in values:numeric(value)
            return None if all(v is None for v in values)else numeric(max(Decimal(0)if v is None else v for v in values))
        raise ValueError('Unknown gist refused')
    def run(self):
        if type(self.program['roots'])is not list or not self.program['roots']:raise ValueError('Finite roots required')
        return{ref:self.get(ref)for ref in self.program['roots']}
