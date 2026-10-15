"""Private fixed-reader JSON API: caller resources -> L4 -> proposed F1040.L8A.

Trusted content authority is host-owned. Requests contain original document and
local file bytes, not programs or intermediate amounts. Source.carriers supplies
the same complete F1040 carrier used by its current metadata and13100 section.
"""
import base64,hashlib,json
from pathlib import Path
from dataclasses import asdict,is_dataclass
from decimal import Decimal
import binary_tax
from raw_L4_F1040_reference import project_raw_L4_into_F1040

_AUTHORITY=json.loads(Path(__file__).with_name('raw-interest-authority.json').read_text())
_AUTHORITY['resource']['payload_sha256']={int(k):v for k,v in _AUTHORITY['resource']['payload_sha256'].items()}
_AUTHORITY['L8A_field']['records']={int(k):v for k,v in _AUTHORITY['L8A_field']['records'].items()}
KEYS={'source','expected_source_sha256','summary_path','source_formset_index','row_number','field_id','need_native_row_uuid','local_resource'}

def _json(value):
 if is_dataclass(value):return _json(asdict(value))
 if isinstance(value,Decimal):return str(value)
 if type(value)is bytes:return dict(encoding='hex',bytes=value.hex())
 if type(value)is dict:return{str(k):_json(v)for k,v in value.items()}
 if type(value)in(list,tuple):return[_json(v)for v in value]
 if value is None or type(value)in(str,int,bool,float):return value
 raise ValueError('Unsupported audit value type')


def _bytes(resource,expected):
 if type(resource)is not dict or set(resource)!={'base64','sha256'}or resource['sha256']!=expected:raise ValueError('Choose the exact host-approved local original resource')
 if type(resource['base64'])is not str or len(resource['base64'])>48*1024*1024:raise ValueError('Bounded complete local resource encoding required')
 try:wire=base64.b64decode(resource['base64'],validate=True)
 except Exception as error:raise ValueError('Invalid caller-local resource encoding')from error
 if hashlib.sha256(wire).hexdigest()!=expected:raise ValueError('Caller-local resource content differs from approved identity')
 return wire


def calculate_request(request):
 if type(request)is not dict or set(request)!=KEYS:raise ValueError('Exact current-source request with one caller-local resource required; no programs or authority upload')
 wire=_bytes(request['local_resource'],_AUTHORITY['resource']['carrier_sha256'])
 source=request['source']
 if type(source)is not dict or type(source.get('carriers'))is not list:raise ValueError('Complete current source carrier binding required')
 matching=[c for c in source['carriers']if type(c)is dict and c.get('sha256')==_AUTHORITY['L8A_field']['carrier_sha256']]
 if len(matching)!=1:raise ValueError('One same-source host-approved F1040 section carrier required')
 field_wire=_bytes(matching[0],_AUTHORITY['L8A_field']['carrier_sha256'])
 current={k:v for k,v in request.items()if k!='local_resource'}
 context_calls=0
 def fixed_loader(source_request):
  nonlocal context_calls
  context_calls+=1
  return binary_tax._context(source_request)
 joined=project_raw_L4_into_F1040(current,binary_loader=fixed_loader,authorities=_AUTHORITY['fields'],caller_resource=wire,resource_authority=_AUTHORITY['resource'],field_carrier=field_wire,field_authority=_AUTHORITY['L8A_field'])
 if context_calls!=1:raise ValueError('One exact current binary snapshot required')
 output=joined['raw_L4_projection'];output['F1040_L8A_projection']={k:v for k,v in joined.items()if k!='raw_L4_projection'}
 output['request_api']=dict(pinned_public_binary_tax_context=True,source_source_sha256=current['expected_source_sha256'],resource_sha256=_AUTHORITY['resource']['carrier_sha256'],consumer_resource_sha256=_AUTHORITY['L8A_field']['carrier_sha256'],consumer_resource_origin='same exact source.carriers complete file',no_program_argument=True,no_intermediate_L4_argument=True,host_authority_outside_request=True,binary_context_calls=context_calls)
 return _json(output)
