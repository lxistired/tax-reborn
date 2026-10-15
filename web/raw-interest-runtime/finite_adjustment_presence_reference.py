"""Finite nine current temporary totals -> actual adjustment presence predicate.

The caller authenticates the source program. Upstream values are complete source
graph results. Missing components are refused, including branches that appear
empty. This module performs no current-field commit or native dispatch.
"""
from decimal import Decimal
import hashlib,json
from finite_normal_adjustment_reference import numeric


class AdjustmentPresence:
    def __init__(self,program,*,expected_sha256,components,prior_values):
        if hashlib.sha256(json.dumps(program,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=expected_sha256:raise ValueError('Approved presence program content changed')
        if type(program)is not dict or set(program)!={'roots','nodes'}or type(program['nodes'])is not list or not 1<=len(program['nodes'])<=128:raise ValueError('Exact finite source presence model required')
        self.program=program;self.nodes={n['reference']:n for n in program['nodes']};self.components=components;self.priors=prior_values
        self.cache={};self.active=set();self.trace=[];self.assignments=[]
        if len(self.nodes)!=len(program['nodes']):raise ValueError('Unique references required')
        if type(components)is not dict or set(components)!={r for r,n in self.nodes.items()if n['type']=='component'}:raise ValueError('Every source component must be computed explicitly; missing never means blank')
        if type(prior_values)is not dict or set(prior_values)!={r for r,n in self.nodes.items()if n.get('assignment')=='user_entered'}:raise ValueError('All nine actual current temporary target priors required')
        for value in components.values():numeric(value)
    def get(self,ref):
        if ref in self.cache:return self.cache[ref]
        if ref not in self.nodes or ref in self.active:raise ValueError('Unknown/cyclic presence dependency')
        self.active.add(ref);n=self.nodes[ref]
        if n['type']=='component':
            if set(n)!={'reference','type'}:raise ValueError('Unknown component protocol')
            value=self.components[ref]
        elif n['type']=='constant':
            if set(n)!={'reference','type','value'}or n['value']!='0':raise ValueError('Source numeric zero required')
            value=Decimal(0)
        elif n['type']=='calculated':
            if set(n)!={'reference','type','gist','inputs','assignment','configuration'}:raise ValueError('Unknown presence instruction')
            inputs=n['inputs'];roles={role:[self.get(d)for d in ds]for role,ds in inputs.items()};name=n['gist'];config=n['configuration']
            def one(role):
                if len(roles.get(role,()))!=1:raise ValueError('Exact source operand cardinality required')
                return roles[role][0]
            def need(names):
                if set(roles)!=set(names):raise ValueError('Unknown presence role')
            if name!='MultiCopyCreateFromBooleans'and config is not None:raise ValueError('Unknown non-map configuration')
            if name=='Accumulation':
                need(['Value']);values=roles['Value']
                for v in values:numeric(v)
                value=numeric(None if all(v is None for v in values)else sum((v for v in values if v is not None),Decimal(0)))
            elif name=='NumericCopy':need(['Value']);value=numeric(one('Value'))
            elif name=='NegativeOfValue':
                need(['Value']);v=numeric(one('Value'));value=numeric(-v if v is not None else None)
            elif name=='NotEqualsTreatBlankAsZero':
                need(['Left','Right']);a=numeric(one('Left'));b=numeric(one('Right'));value=(Decimal(0)if a is None else a)!=(Decimal(0)if b is None else b)
            elif name=='MultiCopyCreateFromBooleans':
                need(['Value']);supplied=dict(zip(inputs['Value'],roles['Value']))
                if type(config)is not list or len(config)!=len(supplied)or any(v is not None and type(v)is not bool for v in supplied.values()):raise ValueError('Source scalar Boolean map required')
                value={};seen=set()
                for entry in config:
                    if type(entry)is not dict or set(entry)!={'key','reference'}or entry['reference']not in supplied or entry['reference']in seen or type(entry['key'])is not str or not entry['key']or entry['key']in value:raise ValueError('Unique exact source map key/reference binding required')
                    value[entry['key']]=supplied[entry['reference']];seen.add(entry['reference'])
            elif name=='MultiCopyCountTrue':
                need(['MultiCopy']);items=one('MultiCopy')
                if type(items)is not dict or any(v is not None and type(v)is not bool for v in items.values()):raise ValueError('Explicit typed Boolean MultiCopy required')
                value=Decimal(sum(v is True for v in items.values()))
            elif name=='AboveThreshold':
                need(['Value','Threshold']);a=numeric(one('Value'));b=numeric(one('Threshold'));value=None if b is None else(Decimal(0)if a is None else a)>b
            else:raise ValueError('Unknown source gist')
            if n['assignment']=='user_entered':
                prior=self.priors[ref]
                if type(prior)is not dict or set(prior)!={'value','computed','overridden','itemized'}or any(type(prior[k])is not bool for k in('computed','overridden','itemized')):raise ValueError('Explicit source current temporary storage required')
                if prior['overridden']or prior['itemized']:raise ValueError('Exterior temporary override/itemization protocol unclosed')
                numeric(prior['value']);numeric(value);computed=value;keep=value is None and prior['value']is not None and not prior['computed']
                if keep:value=prior['value']
                self.assignments.append(dict(reference=ref,computed_value=computed,result=value,retained_existing_Used=keep))
            elif n['assignment']!='none':raise ValueError('Unknown presence assignment')
        else:raise ValueError('Unknown presence node type')
        self.active.remove(ref);self.cache[ref]=value;self.trace.append(ref);return value
    def run(self):return{r:self.get(r)for r in self.program['roots']}
