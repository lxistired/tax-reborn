"""Bounded original seller-financed POR cone; one nonempty concatenate vector.

All country literals come from caller-authenticated local source, not this file.
ST/ZIP used values remain unsupported by the current source adapter.
"""
from decimal import Decimal
from finite_OID_adjustment_reference import OIDAdjustment
from finite_normal_adjustment_reference import numeric,scalar

ROLES=('First','Second','Third','Fourth','Fifth','Sixth','Seventh','Eighth','Ninth','Tenth','Eleventh','Twelveth','Thirteenth','Fourteenth','Fifteenth','Sixteenth','Seventeenth','Eighteenth','Nineteenth','Twentieth')

class SellerInterest(OIDAdjustment):
    def get(self,ref):
        if ref in self.cache:return self.cache[ref]
        n=self.nodes.get(ref)
        if n is None:raise ValueError('Unknown seller-financed source dependency')
        if ref==10770:
            if n!={'reference':10770,'type':'input'}or len(self.inputs[ref])!=1:raise ValueError('Original scalar INPUT10770 current source required')
            value=numeric(next(iter(self.inputs[ref].values())));self.cache[ref]=value;self.trace.append(ref);return value
        if n.get('type')=='constant'and n.get('value_type')=='string_map':
            if set(n)!={'reference','type','value_type','value'}or ref!=2 or type(n['value'])is not dict or len(n['value'])!=279:raise ValueError('Exact complete original country map required')
            if any(type(k)is not str or not k or not k.isascii()or type(v)is not str or not v.isascii()for k,v in n['value'].items()):raise ValueError('Exact source ASCII country key/value map required')
            value={k:scalar(v.encode())for k,v in n['value'].items()};self.cache[ref]=value;self.trace.append(ref);return value
        return super().get(ref)
    @staticmethod
    def apply(n,roles):
        name=n['gist'];cfg=n['configuration']
        def need(names):
            if set(roles)!=set(names):raise ValueError('Unknown seller-financed role')
        def one(role):
            if len(roles.get(role,()))!=1:raise ValueError('Exact seller-financed operand cardinality required')
            return roles[role][0]
        if name=='StringConcat':
            if cfg or not set(roles)<=set(ROLES)or not roles or any(len(v)!=1 for v in roles.values()):raise ValueError('Unconfigured original ordered StringConcat roles required')
            values=[one(role)for role in ROLES if role in roles]
            if any(v is not None and type(v)is not bytes for v in values):raise ValueError('Typed String or blank concatenate operands required')
            for v in values:scalar(v)
            return scalar(b''.join(v for v in values if v is not None))
        if name=='MultiCopyConcatenate':
            need(['Value'])
            if cfg or not roles['Value']or any(type(v)is not dict or len(v)>64 for v in roles['Value']):raise ValueError('All original concatenate input vectors must be explicit')
            retained=[]
            for values in roles['Value']:
                for k,v in values.items():
                    if type(k)is not str or not k or len(k)>128 or '\0'in k:raise ValueError('Finite owned comparison key required')
                    scalar(v)
                if values:retained.append(values)
            if len(retained)>1:raise ValueError('Multiple nonempty concatenate sources remain unclosed')
            # Native first-vector copy calls payload Clone. Independent immutable
            # scalar representation retains value/blank, not native pointer identity.
            return dict(retained[0])if retained else{}
        if name=='MultiCopyAtLeastOneConditionTrue':
            need(['Value']);values=one('Value')
            if cfg or type(values)is not dict or any(v is not None and type(v)is not bool for v in values.values()):raise ValueError('Explicit source Boolean collection required')
            return any(v is True for v in values.values())
        if name=='NotEquals':
            need(['Value']);values=roles['Value']
            if cfg or len(values)!=2 or any(type(v)is not Decimal for v in values):raise ValueError('Only two present Numeric NotEquals operands are verified')
            return numeric(values[0])!=numeric(values[1])
        if name=='MultiCopySelectStringByID':
            need(['MultiCopy','Default','ID']);key=one('ID');table=one('MultiCopy');default=one('Default')
            if cfg or type(table)is not dict or len(table)!=279 or default is not None and type(default)is not bytes:raise ValueError('Complete original country map and typed blank default required')
            if key is not None:
                if type(key)is not bytes or not 1<=len(key)<=32 or not key.isascii()or b'\0'in key:raise ValueError('Finite actual country ID string required')
                key=key.decode('ascii')
            return table.get(''if key is None else key,default)
        return OIDAdjustment.apply(n,roles)
