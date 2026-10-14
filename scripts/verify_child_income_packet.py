"""Read back an actual native-exported synthetic IRS TY2025 Form8814 packet.

This accepts only the built-in parent/child example with child interest2000.
It checks independently authored literal field amounts and real appearances.
"""
from pathlib import Path
import hashlib,io,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pypdf import PdfReader
import forms,official_forms,tax_engine


def verify(blob):
    reader=PdfReader(io.BytesIO(blob));fields=reader.get_fields();expected={}
    def one(suffix,prefix=''):
        names=[k for k in fields if k.startswith(prefix) and k.endswith(suffix)]
        if len(names)!=1:raise AssertionError('Missing/aliased independent field '+suffix)
        return names[0]
    base='topmostSubform[0].Page1[0].'
    # OriginalForm8814 printed fields, split decimal digits and realNo checkbox.
    amounts={3:'Synthetic Child',4:'111111111',5:'2000',6:'0',7:'1000',8:'600',9:'1000',10:'4000',12:'1300',13:'0',14:'150',15:'0',16:'250',17:'195',18:'325',19:'520',20:'780',22:'2650',23:'135'}
    for number,value in amounts.items():expected[one(base+'f1_'+str(number).zfill(2)+'[0]','f8814_0.')]=value
    expected[one(base+'Line15_ReadOrder[0].c1_2[0]','f8814_0.') ]='/1'
    expected[one('topmostSubform[0].Page2[0].c2_9[0]') ]='/1'
    for form_id,line_values in {'f1040s1':{'8z':780,'10':780},'f1040sb':{'6':195},'f1040sd':{'13':325,'15':325},'f8960':{'7':780,'8':1300,'17':49}}.items():
        for line,value in line_values.items():expected[one(official_forms.MAP[form_id]['line_fields'][line],form_id+'_')]=str(value)
    for name,value in expected.items():assert str(fields[name].get('/V',''))==value,(name,fields[name].get('/V'),value)
    actual=official_forms.verify_official_pdf(blob,expected)
    dpage=next(p for p in reader.pages if p.get('/TaxRebornForm')=='f1040sd')
    assert 'Form 8814 - $325' in dpage.extract_text()
    assert sum(p.get('/TaxRebornForm')=='f8814' for p in reader.pages)==1
    assert len(reader.pages)==12
    example=next(x['data'] for x in tax_engine.demo_returns() if x['name']=='Synthetic parent and child income')
    result=tax_engine.calculate_return(example)
    assert result['lines']['16']==37467 and result['lines']['24']==37516 and result['lines']['35a']==12484
    # Official1040fields/appearances validated in addition to the supporting copies.
    main=forms.verify_fields(blob,forms.filing_values({'data':example,'result':result}))
    return {'synthetic_only':True,'tax_year':2025,'pdf_bytes':len(blob),'pdf_sha256':hashlib.sha256(blob).hexdigest(),'pages':len(reader.pages),'child_allocations':{'qualified':195,'capital':325,'ordinary':780,'additional_tax':135},'parent_tax':37516,'parent_refund':12484,'literal_supporting_field_checks':len(expected),'supporting_verification':actual,'main_verification':main,'actual_saved_file_verified':True}

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: verify_child_income_packet.py actual-export.pdf')
    print(json.dumps(verify(Path(sys.argv[1]).read_bytes()),indent=2))
