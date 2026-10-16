"""Read one source-proven saved FormUUID; never substitute it for a RecordUUID."""
import hashlib
from interop.derived_form.value_form_tail_reference import ValueFormTail
from interop.derived_form.persistent_uuid_body_reference import NAME,load_form_uuid_body

class OutsideFiniteProfile(ValueError):pass

def source_child_form_uuid(tail):
    if not isinstance(tail,ValueFormTail):
        raise OutsideFiniteProfile('Actual loaded ValueForm tail required')
    matches=[obj for group in tail.groups for obj in group if obj.class_name==NAME]
    # Native FindFirst is order-sensitive. This helper deliberately rejects
    # duplicate matching objects instead of asserting a restored list order.
    if len(matches)!=1:
        raise OutsideFiniteProfile('One unambiguous canonical source FormUUID149 required')
    try:uuid=load_form_uuid_body(matches[0])
    except ValueError as error:raise OutsideFiniteProfile(str(error)) from error
    return dict(identity_kind='saved_form_UUID149',source_form_uuid=uuid.decode('ascii'),
        source_body_sha256=hashlib.sha256(matches[0].opaque_payload).hexdigest(),
        source_UUID_body_verified=True,
        static_member_path='UUIDBase.Load object+30 -> refreshUUID -> FormBase+8',
        native_load_refresh_executed=False,native_current_copy_lookup_verified=False,
        native_record_inventory_verified=False,record_uuid=None,
        Record_UUID_association_verified=False,comparison_only=True,
        source_writeback_allowed=False,
        refresh_preconditions=['supported native load branch','PersistLoader success',
            'compiled form present','native isMultipleCopy true','actual149 attached to this form'])
