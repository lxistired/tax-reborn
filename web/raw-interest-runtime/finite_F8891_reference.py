"""Finite Canadian normal branch with a proved blank-value applicability cut.

The MFJ producer is unresolved. It is never assigned a Boolean. A nonblank
spouse amount demands that producer and is refused; blank amounts are invariant
under all three typed applicability states. No native dispatch is executed.
"""
from decimal import Decimal
import hashlib,json
from finite_normal_adjustment_reference import scalar,numeric

class CanadianInterest:
    def __init__(self,program,*,expected_sha256,inputs):
        if hashlib.sha256(json.dumps(program,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=expected_sha256:raise ValueError('Approved Canadian source program changed')
        if type(program)is not dict or set(program)!={'roots','nodes'}or program['roots']!=[14641,14643]or type(program['nodes'])is not list or len(program['nodes'])>64:raise ValueError('Finite explicit Canadian source program required')
        self.program=program;self.nodes={n['reference']:n for n in program['nodes']};self.inputs=inputs;self.cache={};self.active=set();self.trace=[];self.invariants=[];self.rounding=[]
        if len(self.nodes)!=len(program['nodes'])or self.nodes.get(12204)!={'reference':12204,'type':'unresolved_boolean'}:raise ValueError('Exact unclosed MFJ marker required, never a prepared Boolean')
        if type(inputs)is not dict or set(inputs)!={1633,1639,1642,1652,1653}or set(inputs)!={r for r,n in self.nodes.items()if n['type']=='input'}:raise ValueError('All five actually read Canadian current inputs required')
        domains=[set(v)for v in inputs.values()if type(v)is dict]
        if len(domains)!=5 or any(len(d)!=1 or d!=domains[0]for d in domains):raise ValueError('One identical existing Canadian form-copy domain required')
        for values in inputs.values():
            for v in values.values():scalar(v)
    def get(self,ref):
        if ref in self.cache:return self.cache[ref]
        if ref not in self.nodes or ref in self.active:raise ValueError('Unknown/cyclic Canadian dependency')
        self.active.add(ref);n=self.nodes[ref]
        if n['type']=='unresolved_boolean':raise ValueError('Actual fresh MFJ producer12204 remains unresolved; no stored or prepared Boolean is substituted')
        if n['type']=='input':
            if set(n)!={'reference','type'}:raise ValueError('Unknown current input protocol')
            value=self.inputs[ref]
        elif n['type']=='constant':
            if set(n)!={'reference','type','value_type','value'}:raise ValueError('Unknown constant protocol')
            if n['value_type']=='boolean'and type(n['value'])is bool:value=n['value']
            elif n['value_type']=='string'and type(n['value'])is str and n['value'].isascii():value=n['value'].encode()
            else:raise ValueError('Exact current Canadian Boolean/String constant required')
        elif n['type']=='calculated':
            if set(n)!={'reference','type','gist','inputs','iterated_inputs','configuration','assignment','round_precision','blank_condition'}or n['assignment']!={'kind':'none','condition':None}or n['blank_condition']is not None:raise ValueError('Unknown Canadian instruction, assignment or blank condition')
            ins=n['inputs'];ids=n['iterated_inputs'];name=n['gist'];precision=n['round_precision']
            if ref in(14639,14640):
                if name!='NumericCopyIfApplicable'or ins.get('ApplicableCondition')!=[12204]or set(ins)!={'Value','ApplicableCondition'}or len(ins['Value'])!=1 or ids or n['configuration']or precision!=0:raise ValueError('Exact original scalar applicability invariant signature required')
                source=numeric(self.get(ins['Value'][0]))
                if source is not None:self.get(12204)
                value=None;self.invariants.append(dict(reference=ref,unresolved_reference=12204,value_is_typed_blank=True,source_boolean_not_supplied=True,output_invariant_for_applicability=[False,True,None],native_source_evaluation_executed=False))
            else:
                domains=[self.get(d)for d in ids]
                if len(ids)!=len(set(ids))or any(type(v)is not dict for v in domains)or any(set(v)!=set(domains[0])for v in domains):raise ValueError('Current Canadian iterator domains differ')
                def calc(key=None):
                    roles={role:[self.get(d)[key]if d in ids else self.get(d)for d in ds]for role,ds in ins.items()}
                    return self.apply(n,roles)
                value={k:calc(k)for k in sorted(domains[0])}if ids else calc()
            if precision is not None:
                if precision!=0:raise ValueError('Only original dollar identity rounding is supported')
                numeric(value)
                if value is not None and value!=value.to_integral_value():raise ValueError('Nonidentity Canadian dollar rounding remains unsupported')
                self.rounding.append(dict(reference=ref,precision=0,identity_only=True))
        else:raise ValueError('Unknown Canadian source node')
        self.active.remove(ref);self.cache[ref]=value;self.trace.append(ref);return value
    @staticmethod
    def apply(n,roles):
        name=n['gist'];cfg=n['configuration']
        def need(names):
            if set(roles)!=set(names):raise ValueError('Unknown Canadian role')
        def one(role):
            if len(roles.get(role,()))!=1:raise ValueError('Exact Canadian operand count required')
            return roles[role][0]
        if name=='SimpleBooleanCaseSelector':
            if set(cfg)!={'selector'}or set(roles)!={'Result','Condition'}:raise ValueError('Exact source Boolean selector configuration required')
            values={ref:v for role,refs in n['inputs'].items()for ref,v in zip(refs,roles[role])};spec=cfg['selector']
            def match(kind,ref):
                if ref not in n['inputs']['Condition']:raise ValueError('Unknown selector condition')
                v=values[ref]
                if v is not None and type(v)is not bool:raise ValueError('Typed source selector Boolean required')
                tests={'True':v is True,'False':v is False,'FalseOrBlank':v is not True,'TrueOrBlank':v is not False,'Blank':v is None,'NotBlank':v is not None}
                if kind not in tests:raise ValueError('Unknown source selector predicate')
                return tests[kind]
            target=next((c['result']for c in spec['cases']if all(match(k,r)for k,r in c['predicates'])),spec['default']);v=values[target]
            if target not in n['inputs']['Result']or v is not None and type(v)is not bool:raise ValueError('Typed source Boolean selector result required')
            return v
        if cfg not in({}, {'SkipToIfCopied':True},{'source_boolean_not':True}):raise ValueError('Unknown source configuration')
        if name=='StringCopy':
            need(['Value']);v=one('Value')
            if cfg or v is not None and type(v)is not bytes:raise ValueError('Typed String copy required')
            return v
        if name=='BooleanCopy':
            need(['Value']);v=one('Value')
            if cfg or v is not None and type(v)is not bool:raise ValueError('Typed Boolean copy required')
            return v
        if name=='IsNotBlank':need(['Value']);return one('Value')is not None
        if name=='Not':
            need(['Value']);v=one('Value')
            if cfg!={'source_boolean_not':True}or type(v)is not bool:raise ValueError('Present Boolean source Not required')
            return not v
        if name=='Equals':
            need(['Value']);values=roles['Value']
            if len(values)!=2 or all(v is None for v in values):raise ValueError('Exact two typed source operands required')
            return all(v is not None and type(v)is type(values[0])and v==values[0]for v in values)
        if name=='BooleanCopyIfApplicable':
            need(['Value','ApplicableCondition']);v=one('Value');c=one('ApplicableCondition')
            if cfg!={'SkipToIfCopied':True}or(v is not None and type(v)is not bool)or(c is not None and type(c)is not bool):raise ValueError('Typed source Boolean applicability required')
            return v if c is True else None
        if name=='AllConditionsTrue':
            if not set(roles)<={'Condition','OppositeConditionTreatBlankAsFalse'}or cfg:raise ValueError('Exact Canadian condition roles required')
            if any(v is not None and type(v)is not bool for vs in roles.values()for v in vs):raise ValueError('Typed current Boolean conditions required')
            return all(v is True for v in roles.get('Condition',[]))and all(v is not True for v in roles.get('OppositeConditionTreatBlankAsFalse',[]))
        if name=='MultiCopyAccumulationWhenTrue':
            need(['Values','Conditions']);values=one('Values');conditions=one('Conditions')
            if cfg or type(values)is not dict or type(conditions)is not dict or set(values)!=set(conditions):raise ValueError('Same actual current numeric/Boolean collection domain required')
            if any(v is not None and type(v)is not bool for v in conditions.values()):raise ValueError('Typed source Boolean conditions required')
            vals=[numeric(v)for k,v in values.items()if conditions[k]is True];return None if all(v is None for v in vals)else numeric(sum((v for v in vals if v is not None),Decimal(0)))
        if name=='Accumulation':
            need(['Value']);values=[numeric(v)for v in roles['Value']]
            if cfg:raise ValueError('No Canadian accumulation configuration expected')
            return None if all(v is None for v in values)else numeric(sum((v for v in values if v is not None),Decimal(0)))
        raise ValueError('Unknown Canadian source gist')
    def run(self):return{r:self.get(r)for r in self.program['roots']}
