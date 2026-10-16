"""Independent selected native FormUUID body, backed by original vtable Store.

Canonical lower-case36-character UUID only. No random generator, factory,
attachment callback or native validation fallback is simulated.
"""
import re
from .value_form_tail_reference import PersistentObject,UnsupportedTailProfile
from .persistent_value_bodies_reference import (proven_value_relocation_classes,
 UnsupportedBodyProfile)
NAME=b'zccPersistentFormUUID'
CANONICAL=re.compile(rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z')

def load_form_uuid_body(obj):
 if not isinstance(obj,PersistentObject) or obj.group!=0 or obj.class_name!=NAME:
  raise UnsupportedTailProfile('Selected FormUUID/form-object class only')
 wire=obj.opaque_payload
 if type(wire) is not bytes or len(wire)!=37 or wire[0]!=36 or not CANONICAL.fullmatch(wire[1:]):
  raise UnsupportedTailProfile('Canonical complete36-byte FormUUID body required')
 return wire[1:]

def store_form_uuid_body(uuid_bytes):
 if type(uuid_bytes) is not bytes or not CANONICAL.fullmatch(uuid_bytes):
  raise UnsupportedTailProfile('Canonical lower-case36-character UUID required')
 return b'\x24'+uuid_bytes

def proven_relocatable_classes(tail):
 found=False
 for group in tail.groups:
  for obj in group:
   if obj.class_name==NAME:
    load_form_uuid_body(obj);found=True
 try:value_names=proven_value_relocation_classes(tail)
 except UnsupportedBodyProfile as error:raise UnsupportedTailProfile(str(error)) from error
 return (frozenset((NAME,)) if found else frozenset())|value_names

def has_untyped_objects(tail):
 names=proven_relocatable_classes(tail)
 return any(obj.class_name not in names for group in tail.groups for obj in group)
