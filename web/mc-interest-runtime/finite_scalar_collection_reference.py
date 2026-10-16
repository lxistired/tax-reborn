"""Original scalar Boolean/Numeric configured maps and exact-domain filter."""
import hashlib,json
from finite_normal_adjustment_reference import numeric

class ScalarCollection:
    def __init__(self,program,*,expected_sha256,components):
        if hashlib.sha256(json.dumps(program,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=expected_sha256:raise ValueError('Approved scalar collection program changed')
        if type(program)is not dict or set(program)!={'roots','nodes'}or program['roots']!=[14724]or type(program['nodes'])is not list or len(program['nodes'])!=9:raise ValueError('Exact finite scalar collection source program required')
        self.program=program;self.nodes={n['reference']:n for n in program['nodes']};self.components=components;self.cache={};self.active=set();self.trace=[]
        if len(self.nodes)!=9 or type(components)is not dict or set(components)!={14631,14643,14719,10770,14641,14722}or set(components)!={r for r,n in self.nodes.items()if n['type']=='component'}:raise ValueError('All six actual internal source outputs required; missing never means blank')
    def get(self,ref):
        if ref in self.cache:return self.cache[ref]
        if ref not in self.nodes or ref in self.active:raise ValueError('Unknown/cyclic scalar collection dependency')
        self.active.add(ref);n=self.nodes[ref]
        if n['type']=='component':
            if set(n)!={'reference','type','value_type'}:raise ValueError('Unknown component protocol')
            value=self.components[ref]
            if n['value_type']=='numeric':numeric(value)
            elif n['value_type']=='boolean':
                if value is not None and type(value)is not bool:raise ValueError('Actual typed Boolean source output required')
            else:raise ValueError('Unknown source component type')
        elif n['type']=='calculated':
            if set(n)!={'reference','type','gist','inputs','configuration'}:raise ValueError('Unknown collection instruction/configuration')
            ins=n['inputs'];roles={role:[self.get(d)for d in ds]for role,ds in ins.items()};name=n['gist'];cfg=n['configuration']
            if name in('MultiCopyCreateFromBooleans','MultiCopyCreateFromNumerics'):
                if set(roles)!={'Value'}or type(cfg)is not list or len(cfg)!=len(ins['Value'])or len(cfg)!=3:raise ValueError('Exact original three configured scalar map inputs required')
                supplied=dict(zip(ins['Value'],roles['Value']));value={};mapped=set()
                if len(supplied)!=3:raise ValueError('Unique actual source Value IDs required')
                for entry in cfg:
                    if type(entry)is not dict or set(entry)!={'key','reference'}or type(entry['key'])is not str or not 1<=len(entry['key'])<=128 or '\0'in entry['key']or entry['key']in value or entry['reference']not in supplied or entry['reference']in mapped:raise ValueError('Unique exact source key-to-ValueID mapping required')
                    v=supplied[entry['reference']]
                    if name.endswith('Numerics'):numeric(v)
                    elif v is not None and type(v)is not bool:raise ValueError('Typed scalar Boolean map required')
                    value[entry['key']]=v;mapped.add(entry['reference'])
            elif name=='MultiCopyFilter':
                if cfg is not None or set(roles)!={'MultiCopy','ValuesAndConditions'}or any(len(v)!=1 for v in roles.values()):raise ValueError('Exact original collection filter signature required')
                values=roles['MultiCopy'][0];tests=roles['ValuesAndConditions'][0]
                if type(values)is not dict or type(tests)is not dict or set(values)!=set(tests)or any(c is not None and type(c)is not bool for c in tests.values()):raise ValueError('Same exact typed source map domain required')
                value={k:values[k]for k,c in tests.items()if c is True}
            else:raise ValueError('Unknown scalar collection gist')
        else:raise ValueError('Unknown scalar collection source node')
        self.active.remove(ref);self.cache[ref]=value;self.trace.append(ref);return value
    def run(self):return{r:self.get(r)for r in self.program['roots']}
