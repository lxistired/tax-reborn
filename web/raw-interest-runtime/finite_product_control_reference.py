"""Finite source-authenticated Product identity/nominee control graph.

Inputs must be current-source bytes or same-source graph values, not supplied
claims about a brand. This pure module embeds no vendor constants or program.
"""
from decimal import Decimal
import hashlib,json
from finite_normal_adjustment_reference import NormalAdjustment,scalar
from finite_interest_prefix_reference import Prefix


class ProductControl:
    def __init__(self,program,*,expected_sha256,facts):
        if hashlib.sha256(json.dumps(program,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=expected_sha256:raise ValueError('Approved source control program changed')
        if type(program)is not dict or set(program)!={'roots','nodes'}or type(program['nodes'])is not list or not 1<=len(program['nodes'])<=64:raise ValueError('Finite explicit control graph required')
        self.nodes={n['reference']:n for n in program['nodes']};self.program=program;self.facts=facts;self.cache={};self.active=set();self.trace=[]
        if len(self.nodes)!=len(program['nodes']):raise ValueError('Unique source control references required')
        if type(facts)is not dict or set(facts)!={r for r,n in self.nodes.items()if n['type']=='source_fact'}:raise ValueError('Every current-source control fact required; no brand default')
        for value in facts.values():
            if type(value)is dict:
                if not value or len(value)>64:raise ValueError('Bounded source copy domain required')
                for k,v in value.items():
                    if type(k)is not str or not k or len(k)>128 or '\0'in k:raise ValueError('Exact comparison key required')
                    scalar(v)
            else:scalar(value)
    def get(self,ref):
        if ref in self.cache:return self.cache[ref]
        if ref in self.active or ref not in self.nodes:raise ValueError('Unknown/cyclic control dependency')
        self.active.add(ref);n=self.nodes[ref]
        if n['type']=='source_fact':
            if set(n)!={'reference','type'}:raise ValueError('Unknown source fact protocol')
            result=self.facts[ref]
        elif n['type']=='constant':
            if set(n)!={'reference','type','value'}or type(n['value'])not in(bool,str):raise ValueError('Explicit String/Boolean constant required')
            result=n['value'].encode('ascii')if type(n['value'])is str else n['value']
        elif n['type']=='calculated':
            if set(n)!={'reference','type','gist','inputs','iterated_inputs','configuration'}:raise ValueError('Unknown source instruction')
            roles={r:[self.get(d)for d in ds]for r,ds in n['inputs'].items()};ids=n['iterated_inputs'];maps=[self.get(d)for d in ids]
            if len(ids)!=len(set(ids))or any(type(v)is not dict for v in maps)or any(set(v)!=set(maps[0])for v in maps):raise ValueError('Control iterator domains differ')
            def calculate(key=None):
                local={r:[self.get(d)[key]if d in ids else self.get(d)for d in ds]for r,ds in n['inputs'].items()}if ids else roles
                name=n['gist'];config=n['configuration']
                if name=='Not':
                    if config!='source_boolean_not'or set(local)!={'Value'}or len(local['Value'])!=1 or type(local['Value'][0])is not bool:raise ValueError('Source Not only present Boolean profile')
                    return not local['Value'][0]
                if name=='BooleanChoiceBasedOnCondition':
                    if config!=['true','false','blank']or set(local)!={'Condition','ValueWhenTrue','ValueWhenFalse','ValueWhenBlank'}or any(len(v)!=1 for v in local.values()):raise ValueError('Exact source true/false/default role binding required')
                    condition=local['Condition'][0]
                    if condition is not None and type(condition)is not bool:raise ValueError('Typed source choice Boolean required')
                    selected=local['ValueWhenTrue'if condition is True else'ValueWhenFalse'if condition is False else'ValueWhenBlank'][0]
                    if selected is not None and type(selected)is not bool:raise ValueError('Typed Boolean result required')
                    return selected
                if config is not None:raise ValueError('Unknown source control configuration')
                if name=='Equals':return NormalAdjustment.apply(dict(gist=name,configuration={}),local)
                if name=='MultiCopyAccumulationWhenTrue':return NormalAdjustment.apply(dict(gist=name,configuration={}),local)
                return Prefix.apply(name,local)
            result={k:calculate(k)for k in sorted(maps[0])}if ids else calculate()
        else:raise ValueError('Unknown source control instruction')
        self.active.remove(ref);self.cache[ref]=result;self.trace.append(ref);return result
    def run(self):return{r:self.get(r)for r in self.program['roots']}
