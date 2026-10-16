"""Independent finite keyed numeric graph interpreter, no resource I/O.

The caller authenticates the program separately. Content SHA binds an exact
caller model; it does not establish vendor origin. This interpreter executes
only flat explicit maps, ordinary numeric values and the listed operations.
"""
from decimal import Decimal
import hashlib,json


def _number(value):
    if value is not None and (type(value)is not Decimal or not value.is_finite()or abs(value)>Decimal('1e9')):
        raise ValueError('Finite Decimal or explicit blank required')
    return value


def _scalar(value):
    if value is not None and type(value)not in(Decimal,bool,str,bytes):
        raise ValueError('Flat typed scalar or explicit blank required')
    if type(value)is bytes and (len(value)>4096 or b'\0'in value):
        raise ValueError('Finite copied CString bytes required')
    if type(value)is Decimal:_number(value)
    return value


class Prefix:
    def __init__(self,program,*,expected_sha256,inputs,prior_values):
        digest=hashlib.sha256(json.dumps(program,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if digest!=expected_sha256:raise ValueError('Selected program content changed')
        if type(program)is not dict or set(program)!={'roots','nodes'}or type(program['nodes'])is not list:
            raise ValueError('Exact finite graph model required')
        self.nodes={};self.cache={};self.active=set();self.trace=[];self.assignments=[]
        for row in program['nodes']:
            if type(row)is not dict or type(row.get('reference'))is not int or row['reference']in self.nodes:
                raise ValueError('Unique integer node references required')
            self.nodes[row['reference']]=row
        required={r for r,n in self.nodes.items()if n.get('type')=='input'}
        if type(inputs)is not dict or set(inputs)!=required:
            raise ValueError('Every input requires an explicit current source fact; no blank defaults')
        for value in inputs.values():
            if type(value)is not dict or not value or len(value)>64 or any(type(k)is not str or not k or len(k)>128 for k in value):
                raise ValueError('Nonempty bounded explicit keyed copies required')
            for scalar in value.values():_scalar(scalar)
        assignments={r for r,n in self.nodes.items()if n.get('assignment')=='user_entered'}
        if type(prior_values)is not dict or set(prior_values)!=assignments:
            raise ValueError('All UserEntered targets require explicit current prior storage')
        self.program=program;self.inputs=inputs;self.prior=prior_values

    def get(self,reference):
        if reference in self.cache:return self.cache[reference]
        if reference in self.active or reference not in self.nodes:raise ValueError('Unknown or cyclic dependency')
        self.active.add(reference);node=self.nodes[reference];typ=node['type']
        if typ=='input':
            if set(node)!={'reference','type'}:raise ValueError('Unsupported input metadata')
            result=self.inputs[reference]
        elif typ=='constant':
            if set(node)!={'reference','type','value'}or type(node['value'])is not str:raise ValueError('Finite numeric constant required')
            result=_number(Decimal(node['value']))
        elif typ=='calculated':
            if set(node)!={'reference','type','gist','inputs','iterated_inputs','assignment'}:
                raise ValueError('Unknown configuration, postprocessing or instruction refused')
            roles={role:[self.get(dep)for dep in deps]for role,deps in node['inputs'].items()}
            iterated=node['iterated_inputs']
            if len(iterated)!=len(set(iterated)):raise ValueError('Duplicate iterator operand')
            if iterated:
                domains=[self.get(dep)for dep in iterated]
                if any(type(v)is not dict for v in domains)or any(set(v)!=set(domains[0])for v in domains):
                    raise ValueError('Required iterators need exact same copy domain')
                result={}
                for key in sorted(domains[0]):
                    local={role:[self.get(dep)[key]if dep in iterated else self.get(dep)for dep in deps]for role,deps in node['inputs'].items()}
                    result[key]=self.apply(node['gist'],local)
            else:result=self.apply(node['gist'],roles)
            if node['assignment']=='user_entered':
                prior=self.prior[reference]
                if type(result)is not dict or type(prior)is not dict or set(prior)!=set(result):
                    raise ValueError('Prior storage must match exact calculated copy domain')
                for key,computed in result.items():
                    entry=prior[key]
                    if type(entry)is not dict or set(entry)!={'value','computed','overridden','itemized'}or any(type(entry[k])is not bool for k in('computed','overridden','itemized')):
                        raise ValueError('Explicit prior value and typed flags required')
                    _number(entry['value'])
                    if entry['overridden']or entry['itemized']:raise ValueError('Exterior override/itemization assignment protocol is unclosed')
                    retained=computed is None and entry['value']is not None and not entry['computed']
                    result[key]=entry['value']if retained else computed
                    self.assignments.append(dict(reference=reference,key=key,computed_value=computed,retained=retained,result=result[key]))
            elif node['assignment']!='none':raise ValueError('Unknown assignment instruction')
        else:raise ValueError('Unknown node instruction')
        self.active.remove(reference);self.cache[reference]=result;self.trace.append(reference)
        return result

    @staticmethod
    def apply(name,roles):
        def one(role):
            value=roles.get(role)
            if type(value)is not list or len(value)!=1:raise ValueError('Exact single role operand required')
            return value[0]
        def require(names):
            if set(roles)!=set(names):raise ValueError('Unknown graph role')
        if name=='NumericCopy':require(['Value']);return _number(one('Value'))
        if name=='IsNotBlank':require(['Value']);return one('Value')is not None
        if name=='GreaterThan':
            require(['Value','Threshold']);left,right=_number(one('Value')),_number(one('Threshold'))
            # Only a freshly constructed typed numeric blank has payload zero.
            return (Decimal(0)if left is None else left)>(Decimal(0)if right is None else right)
        if name in('AllConditionsTrue','AtLeastOneConditionTrue'):
            require(['Condition']);values=roles['Condition']
            if any(v is not None and type(v)is not bool for v in values):raise ValueError('Typed Boolean conditions required')
            return all(v is True for v in values)if name=='AllConditionsTrue'else any(v is True for v in values)
        if name=='NumericCopyIfApplicable':
            require(['Value','ApplicableCondition']);value=_number(one('Value'));condition=one('ApplicableCondition')
            if condition is not None and type(condition)is not bool:raise ValueError('Typed applicability required')
            return value if condition is True else None
        if name=='MultiCopySelectCorrespondingNumeric':
            require(['MultiCopyToSelectFrom','CorrespondingKeys','Key'])
            values,keys,key=one('MultiCopyToSelectFrom'),one('CorrespondingKeys'),_number(one('Key'))
            if type(values)is not dict or type(keys)is not dict or set(values)!=set(keys):
                raise ValueError('Corresponding values and keys require the same explicit domain')
            for value in keys.values():_number(value)
            matches=[ident for ident,value in keys.items()if value==key]
            if len(matches)>1:raise ValueError('Duplicate corresponding numeric keys refused')
            return _number(values[matches[0]])if matches else None
        if name=='Accumulation':
            require(['Value']);values=roles['Value']
            for value in values:_number(value)
            return None if all(v is None for v in values)else sum((v for v in values if v is not None),Decimal(0))
        if name=='MultiCopyFilter':
            require(['MultiCopy','ValuesAndConditions']);values,conditions=one('MultiCopy'),one('ValuesAndConditions')
            if type(values)is not dict or type(conditions)is not dict or set(values)!=set(conditions):raise ValueError('Filter domains differ')
            if any(v is not None and type(v)is not bool for v in conditions.values()):raise ValueError('Typed filter condition required')
            return {key:values[key]for key,v in conditions.items()if v is True}
        raise ValueError('Unknown gist refused')

    def run(self):
        return {reference:self.get(reference)for reference in self.program['roots']}
