"""Fixed IRS2025 printed-row oracles; all addresses and people are synthetic."""
import io,json
from pypdf import PdfReader

CASES=[{'name':'germany','city':'Berlin','country':'Germany','province':'Berlin','postal':'10115'},
       {'name':'canada','city':'Ottawa','country':'Canada','province':'Ontario','postal':'K1A 0B1'}]

def apply_address(data,case):
    data['filing_details']['mailing_address_type']='foreign'
    data['identity'].update(city=case['city'],foreign_country=case['country'],
        foreign_province=case['province'],foreign_postal_code=case['postal'])
    return data

def verify_packet(raw,case,official_forms):
    reader=PdfReader(io.BytesIO(raw));fields=reader.get_fields();expected={}
    # These are the separately labelled address rows in the IRS2025 templates.
    for prefix,rows in [
        ('topmostSubform[0].Page1[0].Address_ReadOrder[0].',[(20,'100 Example Street'),(21,'2B'),(22,case['city']),(23,''),(24,''),(25,case['country']),(26,case['province']),(27,case['postal'])]),
        ('topmostSubform[0].Page1[0].',[(9,'100 Example Street'),(10,'2B'),(11,case['city']),(12,''),(13,''),(14,case['country']),(15,case['province']),(16,case['postal'])])]:
        for number,value in rows:
            key=prefix+f'f1_{number:02d}[0]' if 'Address_ReadOrder' in prefix else prefix+f'f1_{number}[0]'
            if 'Address_ReadOrder' not in prefix:
                matches=[name for name in fields if name.startswith('f1040v_') and name.endswith('.'+key)]
                assert len(matches)==1,(key,matches)
                key=matches[0]
            assert key in fields,key
            assert str(fields[key].get('/V',''))==value,(key,fields[key].get('/V'),value)
            if value:expected[key]=value
    expected['topmostSubform[0].Page2[0].f2_35[0]']='2435'
    amount_keys=[name for name in fields if name.startswith('f1040v_') and name.endswith('.topmostSubform[0].Page1[0].f1_3[0]')]
    assert len(amount_keys)==1
    expected[amount_keys[0]]='2435.00'
    verified=official_forms.verify_official_pdf(raw,expected)
    manifest=json.loads(reader.metadata['/TaxRebornPacketManifest'])
    pages=official_forms.verify_packet_pages(raw,manifest)
    assert not manifest['filing_packet_ready']
    return {'address_format':'foreign','country':case['country'],
        'canonical_and_widget_and_AP_fields':verified['verified_fields'],
        'blank_US_fields_verified':4,'pages':len(reader.pages),
        'page_identities_verified':pages['page_identities_verified'],
        'owed':2435,'amount':'2435.00','synthetic_only':True}
