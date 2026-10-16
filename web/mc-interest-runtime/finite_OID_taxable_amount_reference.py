"""Typed BOID amount/filter consumer, preserving the existing OID refusals."""
from finite_OID_adjustment_reference import OIDAdjustment
from finite_normal_adjustment_reference import scalar


class OIDTaxableAmount(OIDAdjustment):
    @staticmethod
    def apply(node,roles):
        name=node['gist']
        if name=='MultiCopyCopy':
            if node['configuration']or set(roles)!={'Value'}or len(roles['Value'])!=1:raise ValueError('Exact original MC copy signature required')
            value=roles['Value'][0]
            if type(value)is not dict or len(value)>64:raise ValueError('Finite explicit original collection required')
            for key,item in value.items():
                if type(key)is not str or not key or len(key)>128 or '\0'in key:raise ValueError('Finite comparison key required')
                scalar(item)
            return dict(value)
        if name=='Not':
            if node['configuration']!={'source_boolean_not':True}or set(roles)!={'Value'}or len(roles['Value'])!=1 or type(roles['Value'][0])is not bool:raise ValueError('Source present Boolean Not required')
            return not roles['Value'][0]
        return OIDAdjustment.apply(node,roles)
