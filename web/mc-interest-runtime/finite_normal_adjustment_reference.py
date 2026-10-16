"""Finite typed regular-bank adjustment graph, with exact arithmetic only.

The caller supplies an authenticated normalized program and current storage.
Content hashes do not authenticate origin. No vendor resources, UUID generator,
native scheduler or physical write implementation is included here.
"""
from decimal import Decimal
import hashlib,json
from finite_interest_prefix_reference import Prefix


def scalar(value):
    if value is None or type(value)is bool:return value
    if type(value)is str and value and value.isascii()and '\0'not in value and len(value)<=128:return value
    if type(value)is bytes:
        if len(value)>4096 or b'\0'in value:raise ValueError('Finite copied CString required')
        return value
    if type(value)is Decimal and value.is_finite()and abs(value)<=Decimal('1e9'):
        return value
    raise ValueError('Explicit finite Numeric, Boolean, String bytes or typed blank required')


def numeric(value):
    scalar(value)
    if value is not None and type(value)is not Decimal:raise ValueError('Typed numeric required')
    return value


class NormalAdjustment:
    def __init__(self,program,*,expected_sha256,inputs,prior_values):
        if hashlib.sha256(json.dumps(program,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=expected_sha256:
            raise ValueError('Approved graph content changed')
        if type(program)is not dict or set(program)!={'roots','nodes'}or type(program['nodes'])is not list or not 1<=len(program['nodes'])<=256:
            raise ValueError('Finite explicit graph required')
        self.program=program;self.nodes={};self.inputs=inputs;self.priors=prior_values
        self.cache={};self.active=set();self.trace=[];self.assignments=[];self.blank_trace=[];self.rounding=[]
        for n in program['nodes']:
            if type(n)is not dict or type(n.get('reference'))is not int or n['reference']in self.nodes:raise ValueError('Unique node references required')
            self.nodes[n['reference']]=n
        leaves={r for r,n in self.nodes.items()if n.get('type')=='input'}
        assignments={r for r,n in self.nodes.items()if n.get('assignment')=='user_entered'}
        if type(inputs)is not dict or set(inputs)!=leaves:raise ValueError('Every current input required; no blank defaults')
        if type(prior_values)is not dict or set(prior_values)!=assignments:raise ValueError('Every UserEntered target needs actual current prior storage')
        for values in inputs.values():
            if type(values)is not dict or not values or len(values)>64 or any(type(k)is not str or not k or len(k)>128 or '\0'in k for k in values):
                raise ValueError('Complete finite keyed input required')
            for value in values.values():scalar(value)

    def get(self,ref):
        if ref in self.cache:return self.cache[ref]
        if ref not in self.nodes or ref in self.active:raise ValueError('Unknown/cyclic dependency')
        self.active.add(ref);n=self.nodes[ref];typ=n['type']
        if typ=='input':
            if set(n)!={'reference','type'}:raise ValueError('Unknown input instruction')
            value=self.inputs[ref]
        elif typ=='constant':
            if set(n)!={'reference','type','value_type','value'}:raise ValueError('Exact caller constant protocol required')
            tag=n['value_type'];raw=n['value']
            if tag=='numeric'and type(raw)is str:value=numeric(Decimal(raw))
            elif tag=='string'and type(raw)is str and raw.isascii():value=scalar(raw.encode('ascii'))
            elif tag=='string_blank'and raw is None:value=None
            elif tag=='string_map'and type(raw)is dict and raw and len(raw)<=64:
                if any(type(k)is not str or not k or not k.isascii()or type(v)is not str or not v.isascii()for k,v in raw.items()):raise ValueError('Exact ASCII constant-map profile required')
                value={k:scalar(v.encode('ascii'))for k,v in raw.items()}
            else:raise ValueError('Unknown constant type')
        elif typ=='calculated':
            if set(n)!={'reference','type','gist','inputs','iterated_inputs','assignment','round_precision','configuration','blank_condition'}:
                raise ValueError('Unknown configuration, instruction or postprocessing')
            deps=n['inputs'];iterated=n['iterated_inputs'];domains=[self.get(d)for d in iterated]
            if len(iterated)!=len(set(iterated))or any(type(v)is not dict for v in domains)or any(set(v)!=set(domains[0])for v in domains):
                raise ValueError('Required iterator domains differ')
            roles={role:[self.get(d)for d in ds]for role,ds in deps.items()}
            def calculate(key=None):
                local={role:[self.get(d)[key]if d in iterated else self.get(d)for d in ds]for role,ds in deps.items()}if iterated else roles
                result=self.apply(n,local)
                blank=n['blank_condition']
                if blank is not None:
                    if n['gist']!='Product'or type(blank)is not dict or set(blank)!={'type','reference','output_blank_values'}or blank['type']!=3 or len(local.get('Product',()))<2:
                        raise ValueError('Only source-bound multi-operand Product blank condition supported')
                    if deps.get('BlankIfFalseOrBlank')!=[blank['reference']]:raise ValueError('Blank condition input differs')
                    cond=local['BlankIfFalseOrBlank'][0]
                    if cond is not None and type(cond)is not bool:raise ValueError('Typed Boolean condition required')
                    # Each multiply constructs fresh Value(C2), byte+9=0;
                    # Numeric assignment and the final copy preserve that byte.
                    applies=cond is not True
                    self.blank_trace.append(dict(reference=ref,key=key,condition=cond,Product_IsUserInput=False,
                        flag_source='native_fresh_multiply_then_assign_then_copy',applies=applies))
                    if applies:result=None
                precision=n['round_precision']
                if precision is not None:
                    if precision not in(2,8):raise ValueError('Unknown rounding precision')
                    numeric(result)
                    if result is not None and result*(Decimal(10)**precision)!=(result*(Decimal(10)**precision)).to_integral_value():
                        raise ValueError('Nonidentity native rounding is outside this exact finite profile')
                    self.rounding.append(dict(reference=ref,key=key,precision=precision,identity_only=True))
                return result
            value={key:calculate(key)for key in sorted(domains[0])}if iterated else calculate()
            if n['assignment']=='user_entered':
                prior=self.priors[ref]
                if type(value)is not dict or type(prior)is not dict or set(value)!=set(prior):raise ValueError('Exact prior copy domain required')
                for key,computed in list(value.items()):
                    old=prior[key]
                    if type(old)is not dict or set(old)!={'value','computed','overridden','itemized'}or any(type(old[k])is not bool for k in('computed','overridden','itemized')):raise ValueError('Exact current prior protocol required')
                    scalar(old['value'])
                    if old['overridden']or old['itemized']:raise ValueError('Exterior Override/itemization protocol unclosed')
                    if n['gist']=='MultiCopySelectStringByID':
                        if old['value']is not None and type(old['value'])is not bytes:raise ValueError('Current String prior required')
                    else:numeric(old['value'])
                    keep=computed is None and old['value']is not None and not old['computed']
                    value[key]=old['value']if keep else computed
                    self.assignments.append(dict(reference=ref,key=key,computed_value=computed,result=value[key],retained=keep))
            elif n['assignment']!='none':raise ValueError('Unknown assignment')
        else:raise ValueError('Unknown instruction')
        self.active.remove(ref);self.cache[ref]=value;self.trace.append(ref);return value

    @staticmethod
    def apply(n,roles):
        name=n['gist'];configuration=n['configuration']
        allowed=({'SkipToInputIfOnlyOneSet':True,'Type':'generatedName'}if name=='Accumulation'and configuration else
            {'SkipToIfCopied':True}if name=='NumericCopyIfApplicable'and configuration else{})
        if configuration!=allowed:raise ValueError('Unrecognized source configuration')
        def need(names):
            if set(roles)!=set(names):raise ValueError('Unknown role')
        def one(role):
            if len(roles[role])!=1:raise ValueError('Exact single operand required')
            return roles[role][0]
        if name=='NotEqualsTreatBlankAsZero':
            need(['Left','Right']);a=numeric(one('Left'));b=numeric(one('Right'))
            return (Decimal(0)if a is None else a)!=(Decimal(0)if b is None else b)
        if name=='NotEqualsIfNotBlank':
            need(['Left','Right']);a=numeric(one('Left'));b=numeric(one('Right'))
            return None if a is None or b is None else a!=b
        if name=='Equals':
            need(['Value']);values=roles['Value']
            if not values or all(v is None for v in values):raise ValueError('Unknown two-blank types refused')
            for v in values:scalar(v)
            return all(v is not None and type(v)is type(values[0])and v==values[0]for v in values)
        if name=='MultiCopySelectStringByID':
            need(['MultiCopy','Default','ID']);values=one('MultiCopy');key=one('ID');default=one('Default')
            if type(values)is not dict or any(type(k)is not str or not k.isascii()or type(v)is not bytes for k,v in values.items()):raise ValueError('Exact string constant map required')
            if key is not None and type(key)is not str:raise ValueError('Source ValueMapping enum ID required')
            if default is not None and type(default)is not bytes:raise ValueError('Typed default String required')
            return values.get(''if key is None else key,default)
        if name=='Quotient':
            need(['Numerator','Denominator']);a=numeric(one('Numerator'));b=numeric(one('Denominator'))
            if a is None or b is None:return None
            if a<=0 or a!=b:raise ValueError('Only positive exact unit interest ratio is source-verified in this profile')
            return Decimal(1)
        if name=='Product':
            need(['Product','BlankIfFalseOrBlank']);values=roles['Product']
            if len(values)!=2:raise ValueError('Two-operand source Product required')
            for v in values:numeric(v)
            if any(v is None for v in values):return None
            if values[1]!=1:raise ValueError('Exact unit-ratio Product required')
            return numeric(values[0])
        if name=='MultiCopyAccumulationWhenTrue':
            need(['Values','Conditions']);values=one('Values');conditions=one('Conditions')
            if type(values)is not dict or type(conditions)is not dict or set(values)!=set(conditions):raise ValueError('Equal MultiCopy structure required')
            if any(c is not None and type(c)is not bool for c in conditions.values()):raise ValueError('Typed Boolean map required')
            kept=[numeric(v)for k,v in values.items()if conditions[k]is True]
            return numeric(None if all(v is None for v in kept)else sum((v for v in kept if v is not None),Decimal(0)))
        return Prefix.apply(name,roles)

    def run(self):
        if type(self.program['roots'])is not list or not self.program['roots']:raise ValueError('Explicit roots required')
        return{r:self.get(r)for r in self.program['roots']}
