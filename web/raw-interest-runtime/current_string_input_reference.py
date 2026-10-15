"""Actual selected form's current kind7 -> copied CString -> StringValue.

Only the IsNotBlank consumer is modeled. Immutable bytes represent the native
std::string payload without asserting an encoding. A present empty byte string
is present StringValue, because its string constructor clears isBlank.
No native global StringTable registry, borrowing or allocation executes.
"""
from interop.derived_form.string_wire_reference import read


def current_string_input(node,*,table,table_id):
    if node is None:return None
    attrs=node.specific_attributes
    if type(attrs)is not int or not 0<=attrs<=65535:raise ValueError('Current U16 FV attributes required')
    if not attrs&1:return None
    if attrs not in(1,3,9,11)or node.kind_byte!=7 or node.header or node.flag10 or node.flag11:
        raise ValueError('Only ordinary Used kind7/current-format0 CString input is supported')
    raw=node.raw
    if type(raw)is not int or not 0<=raw<1<<32 or type(table_id)is not int or not 0<=table_id<65535:
        raise ValueError('Finite same-form current StringTable payload required')
    if raw&65535!=table_id:raise ValueError('String handle does not belong to selected current form table')
    handle=(raw>>16)&65535
    if handle==65535:raise ValueError('Ordinary allocated string handle required; sentinel branch excluded')
    value=read(table,handle)
    if type(value)is not bytes or len(value)>4096 or b'\0'in value:
        raise ValueError('Finite CString snapshot required')
    return bytes(value)
