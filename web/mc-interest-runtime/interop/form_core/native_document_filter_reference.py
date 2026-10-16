"""Actual selected native filter return profiles; no callback/native execution.

The source method named SkipDebugInfo returns true for both concrete classes.
The reached FieldNameReader branch emits field/elem when that actual slot is
true. The branch is retained literally instead of being inferred from its name.
"""
from dataclasses import dataclass

from .field_template_reference import UnsupportedProfile

@dataclass(frozen=True)
class FilterProfile:
    name:str
    skip_persistent:bool
    skip_calc:bool
    skip_semantic:bool
    debug_slot_return:bool
    original_runtime_executed:bool=False
    native_factory_acceptance:bool=False

NORMAL=FilterProfile('controller_filter',True,False,False,True)
SANITIZER=FilterProfile('sanitizer_filter',True,True,True,True)

def selected_filter(name):
    if type(name)is not str:raise UnsupportedProfile('Explicit source-bound filter profile name required')
    if name=='null_filter':return None
    if name=='controller_filter':return NORMAL
    if name=='sanitizer_filter':return SANITIZER
    raise UnsupportedProfile('Unknown filter implementation; callback result cannot be supplied')

def controller_filter_name(skip_persistent_object):
    if type(skip_persistent_object)is not bool:raise UnsupportedProfile('Exact caller-selected controller boolean required')
    return 'controller_filter'if skip_persistent_object else'null_filter'

def value_handler_includes(specific_attributes,*,form_type8=False,filter_profile='null_filter'):
    if type(specific_attributes)is not int or not 0<=specific_attributes<=65535 or type(form_type8)is not bool:
        raise UnsupportedProfile('Exact U16 FV flags and explicit runtime type8 comparison')
    policy=selected_filter(filter_profile)
    if not form_type8 and policy is not None and policy.skip_calc:
        if specific_attributes&2 and not specific_attributes&8 and not specific_attributes&0x10:return False
    return True
