"""Finite original H/UH temporary scalar totals, without row/key output writes."""
from decimal import Decimal
import hashlib,json
from finite_normal_adjustment_reference import numeric

class OtherScalar:
    def __init__(self,program,*,expected_sha256,components,prior_values):
        if hashlib.sha256(json.dumps(program,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=expected_sha256:raise ValueError('Approved scalar program content changed')
        if type(program)is not dict or set(program)!={'roots','nodes'}or program['roots']!=[14719,14722]or type(program['nodes'])is not list or not 1<=len(program['nodes'])<=32:raise ValueError('Finite actual scalar branch program required')
        self.nodes={n['reference']:n for n in program['nodes']};self.program=program;self.components=components;self.priors=prior_values;self.cache={};self.active=set();self.trace=[];self.assignments=[]
        if len(self.nodes)!=len(program['nodes']):raise ValueError('Unique scalar references required')
        if type(components)is not dict or set(components)!={14664,14704,14692,14715}or set(components)!={r for r,n in self.nodes.items()if n['type']=='component'}:raise ValueError('All four actually recomputed source contributions required')
        if type(prior_values)is not dict or set(prior_values)!={14694,14717}or set(prior_values)!={r for r,n in self.nodes.items()if n.get('assignment')=='user_entered'}:raise ValueError('Both actual current H/UH target priors required')
        for v in components.values():numeric(v)
    def get(self,ref):
        if ref in self.cache:return self.cache[ref]
        if ref not in self.nodes or ref in self.active:raise ValueError('Unknown/cyclic scalar source dependency')
        self.active.add(ref);n=self.nodes[ref];typ=n['type']
        if typ=='component':
            if set(n)!={'reference','type'}:raise ValueError('Unknown component protocol')
            value=self.components[ref]
        elif typ=='constant':
            if set(n)!={'reference','type','value'}or n['value']!='0':raise ValueError('Exact source numeric zero required')
            value=Decimal(0)
        elif typ=='calculated':
            if set(n)!={'reference','type','gist','inputs','assignment'}:raise ValueError('Unknown scalar instruction/configuration')
            roles={role:[self.get(d)for d in ds]for role,ds in n['inputs'].items()};name=n['gist']
            def need(names):
                if set(roles)!=set(names):raise ValueError('Unknown scalar role')
            def one(role):
                if len(roles.get(role,()))!=1:raise ValueError('Exact scalar role cardinality required')
                return roles[role][0]
            if name=='Accumulation':
                need(['Value']);values=[numeric(v)for v in roles['Value']];value=numeric(None if all(v is None for v in values)else sum((v for v in values if v is not None),Decimal(0)))
            elif name=='NumericCopy':need(['Value']);value=numeric(one('Value'))
            elif name=='NegativeOfValue':
                need(['Value']);v=numeric(one('Value'));value=numeric(None if v is None else-v)
            elif name=='NotEqualsTreatBlankAsZero':
                need(['Left','Right']);a=numeric(one('Left'));b=numeric(one('Right'));value=(Decimal(0)if a is None else a)!=(Decimal(0)if b is None else b)
            elif name=='AtLeastOneConditionTrue':
                need(['Condition'])
                if any(v is not None and type(v)is not bool for v in roles['Condition']):raise ValueError('Typed Boolean source conditions required')
                value=any(v is True for v in roles['Condition'])
            else:raise ValueError('Unknown scalar source gist')
            if n['assignment']=='user_entered':
                old=self.priors[ref]
                if type(old)is not dict or set(old)!={'value','computed','overridden','itemized'}or any(type(old[k])is not bool for k in('computed','overridden','itemized')):raise ValueError('Actual current scalar storage required')
                if old['overridden']or old['itemized']:raise ValueError('Exterior H/UH Override or itemization protocol remains unclosed')
                numeric(old['value']);numeric(value);computed=value;keep=value is None and old['value']is not None and not old['computed']
                if keep:value=old['value']
                self.assignments.append(dict(reference=ref,computed_value=computed,result=value,retained_existing_Used=keep))
            elif n['assignment']!='none':raise ValueError('Unknown scalar assignment')
        else:raise ValueError('Unknown scalar instruction type')
        self.active.remove(ref);self.cache[ref]=value;self.trace.append(ref);return value
    def run(self):return{r:self.get(r)for r in self.program['roots']}
