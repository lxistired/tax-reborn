"""Keep calculation-record templates separate from official paper-form facts.

The frozen tax formulas and their schema functions are unchanged. This adapter
repairs UI template-name collisions at the application boundary.
"""
from copy import deepcopy
import tax_engine
import tax_extended
import tax_credits
import tax_additional
import tax_longtail
import tax_filing


def capabilities():
    result = tax_engine.capabilities()
    rows = deepcopy(result['row_templates'])
    fact_schema = tax_filing.fact_schema()
    facts = fact_schema['row_templates']
    core = deepcopy(tax_engine.ROW_DEFAULTS)
    core.update(tax_extended.ui_schema().get('row_templates', {}))
    for module in (tax_credits, tax_additional, tax_longtail):
        core.update(module.row_templates())
    for name, template in facts.items():
        rows.pop(name, None)
        rows['filing_details.official_form_facts.' + name] = deepcopy(template)
        if name in core:
            rows[name] = deepcopy(core[name])
    result['row_templates'] = rows
    fields = deepcopy(result['ui_fields'])
    core_fields = deepcopy(tax_extended.ui_schema().get('ui_fields', {}))
    core_fields.update(tax_credits.ui_fields())
    core_fields.update(tax_additional.ui_schema()['ui_fields'])
    core_fields.update(tax_longtail.ui_schema()['ui_fields'])
    for name, description in fact_schema['ui_fields'].items():
        fields.pop(name, None)
        fields['filing_details.official_form_facts.' + name] = deepcopy(description)
        if name in core_fields:
            fields[name] = deepcopy(core_fields[name])
    result['ui_fields'] = fields
    return result
