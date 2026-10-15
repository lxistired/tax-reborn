"""Experimental single-form core I/O; never a complete .tax return reader.

Use only the explicit modern wide-index, BE-scalar/LE-node profile. The
application's supported TaxML import and federal tax core are separate.
"""
from .value_hash_wire_reference import (
    Node, Buffer, Hash, Header, FormCore, CoreLoad, hash_for_nodes, find_value,
    store_form_core, load_form_core_bytes, UnsupportedProfile,
)
from .selected_form_record_reference import (
    store_selected_form_record, load_selected_form_record,
)
