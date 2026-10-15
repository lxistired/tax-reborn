"""Exact endpoint ratios for regular and US-only current bank interest.

All nonendpoint ratios remain unsupported. This adds no native source inventory,
fresh temporary total, physical target or scheduler claim.
"""
from decimal import Decimal
from finite_normal_adjustment_reference import NormalAdjustment,numeric


class BankAdjustment(NormalAdjustment):
    @staticmethod
    def apply(node,roles):
        if node['gist']=='Quotient':
            if node['configuration']or set(roles)!={'Numerator','Denominator'}or any(len(v)!=1 for v in roles.values()):
                raise ValueError('Exact unconfigured quotient role signature required')
            numerator=numeric(roles['Numerator'][0]);denominator=numeric(roles['Denominator'][0])
            if numerator is None or denominator is None:return None
            if denominator<=0 or numerator not in(Decimal(0),denominator):
                raise ValueError('Only exact zero or unit interest ratio is verified in this profile')
            return Decimal(0)if numerator==0 else Decimal(1)
        return NormalAdjustment.apply(node,roles)
