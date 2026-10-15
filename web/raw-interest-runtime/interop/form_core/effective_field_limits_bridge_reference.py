"""Same verified effective registry report -> explicit selected2160 lists.

No resource byte, selector, home order or permission is accepted from an App
request. The caller has already built this report from the complete validated
resource maps. Missing2160 is retained as unknown, not source-invalid.
"""
from types import MappingProxyType
from .effective_field_limits_reference import LimitHome,select_field_limits_from_homes
from .field_template_reference import UnsupportedProfile


def selected_field_limits(report,ordered_complete_maps,templates):
    resources=MappingProxyType({identity.encode():MappingProxyType(dict(rows))for identity,rows in ordered_complete_maps})
    forms={}
    for fs in report['membership']:
        for form in fs['forms']:
            forms[fs['formset_id'],form['form_id']]=form
    result={}
    for template in templates:
        key=template.formset_id,template.form_id
        form=forms.get(key)
        if form is None or form['primary'] is None or (form['primary']['carrier_sha256'],form['primary']['resource_id'])!=(template.carrier_sha256,template.resource_id):
            raise UnsupportedProfile('Limits owner differs from this selected effective template')
        homes=tuple(LimitHome(row['carrier_sha256'].encode(),row['resource_id'],row['metadata_type'])for row in form['homes'])
        selection=select_field_limits_from_homes(homes,resources,form_identity=template)
        ordinals={field.ordinal for field in template.fields}
        if any(entry.current_field_index not in ordinals for entry in selection.entries):
            raise UnsupportedProfile('Saved limits refer to an absent current template field')
        result[key]=selection
    return MappingProxyType(result)
