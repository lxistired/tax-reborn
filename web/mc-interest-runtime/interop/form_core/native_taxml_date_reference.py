"""Selected kind4/5/6, header0/valueformat0/currentformat0 date branches.

Native TaxML FormatValue has a dedicated date path, distinct from ordinary
ConvertToString. Currentformat0 is taintable, so valid existing date text is
retained through GetString, not silently converted into ISO. The finite normal
input here is exact MM/DD/YYYY, years1900..9999. Kind5 normal internal text is
MM/DD (sentinel year1984), kind6 is MM/YYYY (day1). Their TaxML output is MM-DD
and YYYY-MM. Wire-text validation is separate from native inbound loading.
Two-digit/current-year prompts, invalid text retrieval and native handles remain
pending. No native setter/factory is executed.
"""
from dataclasses import dataclass
import re
from .field_template_reference import UnsupportedProfile
_RX=re.compile(r'([0-9]{2})/([0-9]{2})/([0-9]{4})\Z')
_DAY=re.compile(r'([0-9]{2})/([0-9]{2})\Z')
_MONTH=re.compile(r'([0-9]{2})/([0-9]{4})\Z')
@dataclass(frozen=True)
class DateText:
    month:int
    day:int
    year:int
    text:str
    input_format:int=173
    modeled_conversion_status:int=0
    taxml_taintable:bool=True
    tainted:bool=False
    output_is_raw_source_text:bool=True
    native_execution:bool=False
    kind:int=4
    native_string_text:str=''

@dataclass(frozen=True)
class DateControlPlan:
    kind:int
    prepared_conversion_status:int
    taxml_taintable:bool
    next_operation:str
    first_tainted:bool
    second_diagnostic:bool
    third_precision:bool
    serialized_output_attributes:tuple
    calendar_format:str|None
    native_execution:bool=False

def _ordinary(kind,compiled_format,value_format,header):
    if type(kind)is not int or kind not in (4,5,6) or any(type(v)is not int or v!=0 for v in(compiled_format,value_format,header)):
        raise UnsupportedProfile('Only selected ordinary kind4/5/6/currentformat0/FVformat0/header0 date text')

def _valid(m,d,y):
    if not 1900<=y<=9999 or not 1<=m<=12:
        raise UnsupportedProfile('Selected calendar years1900..9999 and month1..12 required')
    leap=y%4==0 and(y%100!=0 or y%400==0)
    days=(31,29 if leap else 28,31,30,31,30,31,31,30,31,30,31)
    if not 1<=d<=days[m-1]:raise UnsupportedProfile('Invalid day for selected calendar month/year')

def prepare_date_control_flow(kind,prepared_conversion_status,*,string_handle_missing=False,compiled_format=0,value_format=0,header=0):
    """Branch selection only; supplied status is not native execution.

    Any GetString result/status and actual zpDate object remain pending. Only
    the first bool is serialized as isTainted by CoreCopyValueReader.Value.
    """
    _ordinary(kind,compiled_format,value_format,header)
    if type(prepared_conversion_status)is not int or not -32768<=prepared_conversion_status<=65535 or type(string_handle_missing)is not bool:
        raise UnsupportedProfile('Explicit prepared U16/error status and handle-state bool required')
    taintable=kind==4
    first=taintable and prepared_conversion_status==1
    second=not taintable and(prepared_conversion_status!=0 or string_handle_missing)
    raw=taintable or second
    fmt=None if raw else {4:'%04d-%02d-%02d',5:'%02d-%02d',6:'%04d-%02d'}[kind]
    return DateControlPlan(kind,prepared_conversion_status,taintable,'pending_GetString'if raw else'format_prepared_calendar_components',first,second,False,(('isTainted','true'),)if first else(),fmt)

def project_native_date_string(kind,text,*,compiled_format=0,value_format=0,header=0):
    """Finite normal projection of caller-owned internal string, not LoadValue.

    Native parsing admits more forms than this canonical profile. Calendar
    validation computes a modeled zero status; no callback supplies a native
    success, current StringTable handle or form inventory.
    """
    _ordinary(kind,compiled_format,value_format,header)
    if kind==4:return parse_date_text(text)
    rx=_DAY if kind==5 else _MONTH
    if type(text)is not str or not(match:=rx.fullmatch(text)):
        raise UnsupportedProfile('Exact internal MM/DD day or MM/YYYY month text required')
    if kind==5:m,d=map(int,match.groups());y=1984;fmt=172;out=f'{m:02d}-{d:02d}'
    else:m,y=map(int,match.groups());d=1;fmt=164;out=f'{y:04d}-{m:02d}'
    _valid(m,d,y)
    return DateText(m,d,y,out,fmt,taxml_taintable=False,output_is_raw_source_text=False,kind=kind,native_string_text=text)

def parse_date_wire_text(text,*,kind=4):
    """Validate serialized date text; native inbound conversion stays pending."""
    _ordinary(kind,0,0,0)
    if kind==4:return parse_date_text(text)
    if type(text)is not str:raise UnsupportedProfile('Exact date wire string required')
    if kind==5 and re.fullmatch(r'[0-9]{2}-[0-9]{2}',text):native=text.replace('-','/')
    elif kind==6 and re.fullmatch(r'[0-9]{4}-[0-9]{2}',text):native=text[5:7]+'/'+text[:4]
    else:raise UnsupportedProfile('Exact MM-DD day or YYYY-MM month wire text required')
    result=project_native_date_string(kind,native)
    if result.text!=text:raise UnsupportedProfile('Noncanonical date wire text')
    return result

def parse_date_text(text,*,kind=4,compiled_format=0,value_format=0,header=0):
    if any(type(v)is not int or v!=expected for v,expected in((kind,4),(compiled_format,0),(value_format,0),(header,0))):
        raise UnsupportedProfile('Only selected ordinary kind4/currentformat0/FVformat0/header0 date text')
    if type(text)is not str or not(match:=_RX.fullmatch(text)):
        raise UnsupportedProfile('Exact MM/DD/YYYY date text required; no implicit date normalization')
    m,d,y=map(int,match.groups())
    _valid(m,d,y)
    return DateText(m,d,y,text,native_string_text=text)

def patch_date_document(document,key,new_text):
    from .native_mac_taxml_money_reference import MoneyDocument,load_money_document
    import hashlib
    if type(document)is not MoneyDocument:raise UnsupportedProfile('Loaded complete selected date source required')
    if hashlib.sha256(document.source_bytes).hexdigest()!=document.source_sha256:
        raise UnsupportedProfile('Changed complete source identity')
    checked=load_money_document(document.source_bytes,document.registry,document.contexts,filter_profile=document.filter_profile)
    matches=[f for f in checked.fields if f.key==key]
    if len(matches)!=1 or matches[0].kind not in (4,5,6) or not matches[0].can_edit:
        raise UnsupportedProfile('One existing Used1 full-identity ordinary date required')
    field=matches[0];parse_date_wire_text(new_text,kind=field.kind)
    wire=checked.source_bytes[:field.text_start]+new_text.encode('ascii')+checked.source_bytes[field.text_end:]
    reopened=load_money_document(wire,document.registry,document.contexts,filter_profile=document.filter_profile)
    before=[(f.key,new_text if f.key==key else f.text,f.kind,f.attributes,f.value_attributes)for f in checked.fields]
    after=[(f.key,f.text,f.kind,f.attributes,f.value_attributes)for f in reopened.fields]
    if before!=after:raise UnsupportedProfile('Complete source date readback differs outside selected text')
    return wire,reopened
