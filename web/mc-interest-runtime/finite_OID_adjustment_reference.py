"""Finite original-source OID contribution graph, with explicit refusal gates.

Only exact 0/1 ratios and identity rounding are supported. Both Default targets
must be unused current storage. Non-Product unknown UserInput flags are never
assumed false: execution refuses if that flag could alter a nonblank value.
"""
from decimal import Decimal
import hashlib,json
from finite_interest_prefix_reference import Prefix
from finite_normal_adjustment_reference import NormalAdjustment,numeric,scalar


class OIDAdjustment:
    def __init__(self,program,*,expected_sha256,inputs,prior_values):
        if hashlib.sha256(json.dumps(program,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=expected_sha256:raise ValueError('Approved OID program content changed')
        if type(program)is not dict or set(program)!={'roots','nodes'}or type(program['nodes'])is not list or not 1<=len(program['nodes'])<=256:raise ValueError('Bounded explicit OID program required')
        self.program=program;self.nodes={n['reference']:n for n in program['nodes']};self.inputs=inputs;self.priors=prior_values
        self.cache={};self.active=set();self.trace=[];self.assignments=[];self.blank_trace=[];self.rounding=[]
        if len(self.nodes)!=len(program['nodes']):raise ValueError('Unique OID node references required')
        if type(inputs)is not dict or set(inputs)!={r for r,n in self.nodes.items()if n['type']=='input'}:raise ValueError('Every OID input requires actual current source, without blank defaults')
        targets={r for r,n in self.nodes.items()if n.get('assignment',{}).get('kind')in('user_entered','fresh_default')}
        if type(prior_values)is not dict or set(prior_values)!=targets:raise ValueError('Every OID target current storage required')
        for value in inputs.values():
            if type(value)is not dict or not value or len(value)>64:raise ValueError('Explicit nonempty OID copy domain required')
            for key,item in value.items():
                if type(key)is not str or not key or len(key)>128 or '\0'in key:raise ValueError('Finite source comparison key required')
                scalar(item)
    def get(self,ref):
        if ref in self.cache:return self.cache[ref]
        if ref not in self.nodes or ref in self.active:raise ValueError('Unknown/cyclic OID dependency')
        self.active.add(ref);n=self.nodes[ref];typ=n['type']
        if typ=='input':
            if set(n)!={'reference','type'}:raise ValueError('Unknown input protocol')
            result=self.inputs[ref]
        elif typ=='constant':
            if set(n)!={'reference','type','value_type','value'}:raise ValueError('Exact typed constant protocol required')
            tag,value=n['value_type'],n['value']
            if value is None:result=None
            elif tag=='boolean'and type(value)is bool:result=value
            elif tag=='numeric'and type(value)is str:result=numeric(Decimal(value))
            elif tag=='string'and type(value)is str and value.isascii():result=scalar(value.encode('ascii'))
            elif tag=='string_map'and type(value)is dict and 1<=len(value)<=64:
                if any(type(k)is not str or not k or not k.isascii()or type(v)is not str or not v.isascii()for k,v in value.items()):raise ValueError('Exact finite String constants required')
                result={k:scalar(v.encode('ascii'))for k,v in value.items()}
            else:raise ValueError('Unknown constant type')
        elif typ=='calculated':
            if set(n)!={'reference','type','gist','inputs','iterated_inputs','configuration','assignment','round_precision','blank_condition'}:raise ValueError('Unknown OID instruction/configuration')
            inputs=n['inputs'];ids=n['iterated_inputs'];domains=[self.get(d)for d in ids]
            if len(ids)!=len(set(ids))or any(type(d)is not dict for d in domains)or any(set(d)!=set(domains[0])for d in domains):raise ValueError('Required OID iterator domains differ')
            roles={role:[self.get(d)for d in ds]for role,ds in inputs.items()}
            def calculate(key=None):
                local={role:[self.get(d)[key]if d in ids else self.get(d)for d in ds]for role,ds in inputs.items()}if ids else roles
                value=self.apply(n,local);blank=n['blank_condition']
                if blank is not None:
                    if type(blank)is not dict or set(blank)!={'type','reference','output_blank_values'}or blank['type']not in(2,3):raise ValueError('Unknown blank condition')
                    role='BlankIfFalseNotBlank'if blank['type']==2 else'BlankIfFalseOrBlank'
                    if inputs.get(role)!=[blank['reference']]:raise ValueError('Exact blank condition source reference required')
                    condition=local[role][0]
                    if condition is not None and type(condition)is not bool:raise ValueError('Typed Boolean blank condition required')
                    wants=condition is False if blank['type']==2 else condition is not True
                    proof='Product_fresh_multiply_IsUserInput_false'if n['gist']=='Product'else'value_invariant_without_flag'
                    if wants:
                        if n['gist']=='Product'or blank['output_blank_values']:value=None
                        elif value is not None:raise ValueError('Non-Product BlankCondition needs actual IsUserInput supplier when it could change a nonblank value')
                    self.blank_trace.append(dict(reference=ref,key=key,condition=condition,condition_requests_blank=wants,
                        IsUserInput=False if n['gist']=='Product'else None,flag_proof=proof,
                        nonProduct_flag_not_assumed_false=n['gist']!='Product'))
                precision=n['round_precision']
                if precision is not None:
                    if precision not in(2,5,8):raise ValueError('Unknown OID rounding precision')
                    numeric(value)
                    if value is not None and value*(Decimal(10)**precision)!=(value*(Decimal(10)**precision)).to_integral_value():raise ValueError('Native nonidentity rounding remains unsupported')
                    self.rounding.append(dict(reference=ref,key=key,precision=precision,identity_only=True))
                return value
            result={key:calculate(key)for key in sorted(domains[0])}if ids else calculate()
            assignment=n['assignment']
            if type(assignment)is not dict or set(assignment)!={'kind','condition'}:raise ValueError('Exact assignment protocol required')
            kind=assignment['kind']
            if kind in('user_entered','fresh_default'):
                prior=self.priors[ref]
                if type(result)is not dict or type(prior)is not dict or set(prior)!=set(result):raise ValueError('Target prior copy domain differs')
                for key,value in list(result.items()):
                    old=prior[key]
                    if type(old)is not dict or set(old)!={'value','computed','overridden','itemized','assign_statement'}or any(type(old[k])is not bool for k in('computed','overridden','itemized')):raise ValueError('Explicit OID source prior flags required')
                    if old['overridden']or old['itemized']:raise ValueError('Exterior OID override/itemization protocol remains unclosed')
                    keep=False;computed=value;condition=None
                    if kind=='user_entered':
                        numeric(old['value']);numeric(value)
                        if old['assign_statement']['type']!=3 or old['assign_statement']['condition']!=1:raise ValueError('Original ordinary UserEntered protocol required')
                        keep=value is None and old['value']is not None and not old['computed']
                        if keep:result[key]=old['value']
                    else:
                        if old['value']is not None:raise ValueError('Both current OID Default targets must be absent/Unused; stored Used empty is not blank')
                        if old['assign_statement']['type']!=2:raise ValueError('Original Default assignment protocol required')
                        if assignment['condition']is not None:
                            refcond=assignment['condition'];condition=self.get(refcond)
                            if type(condition)is dict:
                                if set(condition)!=set(result):raise ValueError('Default condition domain differs')
                                condition=condition[key]
                            if condition is not None and type(condition)is not bool:raise ValueError('Typed Default condition required')
                        # Original Default ASSIGN and IfTrueElseNormal both
                        # choose computed payload when the prior is blank.
                        if value is not None and type(value)is not bytes:raise ValueError('Typed String Default result required')
                    self.assignments.append(dict(reference=ref,key=key,assignment=kind,computed_value=computed,result=result[key],retained=keep,
                        current_Default_prior_required_unused=kind=='fresh_default',assignment_condition=condition,native_flag_mutations_executed=False))
            elif kind!='none'or assignment['condition']is not None:raise ValueError('Unknown OID assignment')
        else:raise ValueError('Unknown OID node')
        self.active.remove(ref);self.cache[ref]=result;self.trace.append(ref);return result
    @staticmethod
    def apply(n,roles):
        name=n['gist'];config=n['configuration']
        blank_roles={'BlankIfFalseNotBlank','BlankIfFalseOrBlank'};roles={k:v for k,v in roles.items()if k not in blank_roles}
        def one(role):
            if len(roles.get(role,()))!=1:raise ValueError('Exact role cardinality required')
            return roles[role][0]
        def need(names):
            if set(roles)!=set(names):raise ValueError('Unknown OID role')
        if name in('StringCaseSelector','SimpleStringCaseSelector','SimpleBooleanCaseSelector'):
            if set(config)!={'selector'}or set(roles)not in({'Result','Condition'},{'Result','Condition','AssignIfTrueElseNormal'}):raise ValueError('Exact source selector signature required')
            spec=config['selector'];values={r:v for role,refs in n['inputs'].items()for r,v in zip(refs,roles[role])};conditions=set(n['inputs']['Condition']);results=set(n['inputs']['Result'])
            def matches(kind,ref):
                if ref not in conditions:raise ValueError('Selector predicate lacks source Boolean input')
                value=values[ref]
                if value is not None and type(value)is not bool:raise ValueError('Typed selector predicate required')
                tests={'True':value is True,'False':value is False,'Blank':value is None,'TrueOrBlank':value is not False,'FalseOrBlank':value is not True,'NotBlank':value is not None}
                if kind not in tests:raise ValueError('Unknown selector predicate')
                return tests[kind]
            target=next((c['result']for c in spec['cases']if all(matches(k,r)for k,r in c['predicates'])),spec['default'])
            if target not in results:raise ValueError('Selector result lacks source Result role')
            value=values[target];expected=bool if spec['value_type']=='boolean'else bytes if spec['value_type']=='string'else None
            if expected is None or value is not None and type(value)is not expected:raise ValueError('Selector result type differs')
            return value
        if config and config not in({'SkipToIfCopied':True},{'SkipToInputIfOnlyOneFalse':True}):raise ValueError('Unknown nonselector configuration')
        if name=='AllConditionsTrue':
            if not set(roles)<={'Condition','OppositeCondition'}:raise ValueError('Unknown Boolean role')
            if any(x is not None and type(x)is not bool for vs in roles.values()for x in vs):raise ValueError('Typed Boolean vector required')
            return all(v is True for v in roles.get('Condition',[]))and all(v is False for v in roles.get('OppositeCondition',[]))
        if name=='IsBlank':need(['Value']);return one('Value')is None
        if name=='AboveThreshold':
            need(['Value','Threshold']);a=numeric(one('Value'));b=numeric(one('Threshold'))
            return None if b is None else(Decimal(0)if a is None else a)>b
        if name in('MultiCopySelectCorrespondingBoolean','MultiCopySelectCorrespondingString'):
            need(['MultiCopyToSelectFrom','CorrespondingKeys','Key']);values=one('MultiCopyToSelectFrom');keys=one('CorrespondingKeys');key=numeric(one('Key'))
            if type(values)is not dict or type(keys)is not dict or set(values)!=set(keys):raise ValueError('Corresponding OID structures differ')
            for value in keys.values():numeric(value)
            found=[k for k,value in keys.items()if value==key]
            if len(found)>1:raise ValueError('Duplicate corresponding numeric key')
            result=values[found[0]]if found else None;expected=bool if name.endswith('Boolean')else bytes
            if result is not None and type(result)is not expected:raise ValueError('Corresponding result type differs')
            return result
        if name=='Quotient':
            need(['Numerator','Denominator']);a=numeric(one('Numerator'));b=numeric(one('Denominator'))
            if a is None or b is None:return None
            if b<=0 or a not in(Decimal(0),b):raise ValueError('Only exact zero/unit OID ratios supported')
            return Decimal(0)if a==0 else Decimal(1)
        if name=='Product':
            need(['Product']);values=roles['Product']
            if len(values)!=2:raise ValueError('Original two-operand Product required')
            a,b=map(numeric,values)
            if a is None or b is None:return None
            if b not in(Decimal(0),Decimal(1))or abs(a)>Decimal('1e6'):raise ValueError('Finite exact endpoint Product bounded to one million required')
            return numeric(a*b)
        if name=='MultiCopyAccumulation':
            need(['Value']);values=one('Value')
            if type(values)is not dict:raise ValueError('Explicit numeric collection required')
            for value in values.values():numeric(value)
            return numeric(None if all(v is None for v in values.values())else sum((v for v in values.values()if v is not None),Decimal(0)))
        if name in('Equals','NotEqualsIfNotBlank','NotEqualsTreatBlankAsZero','MultiCopySelectStringByID','MultiCopyAccumulationWhenTrue'):
            return NormalAdjustment.apply(dict(gist=name,configuration={}),roles)
        return Prefix.apply(name,roles)
    def run(self):return{r:self.get(r)for r in self.program['roots']}
