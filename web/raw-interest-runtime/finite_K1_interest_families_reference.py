"""Three finite source family filters, preserving source keys and blank values."""
from finite_interest_prefix_reference import Prefix


class K1InterestFamilies(Prefix):
    @staticmethod
    def apply(name,roles):
        if name=='MultiCopyCopy':
            if set(roles)!={'Value'}or len(roles['Value'])!=1 or type(roles['Value'][0])is not dict or len(roles['Value'][0])>64:raise ValueError('Exact finite source collection copy required')
            return dict(roles['Value'][0])
        return Prefix.apply(name,roles)
