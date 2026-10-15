"""Selected encrypt=false PersistenceContainer item envelope.

The actual constructor defaults encrypt=true. The caller must explicitly select
the cleartext profile; no key material, decryptor or native crypto is included.
Native types/names are metadata. Payload editing requires its separate source
validator; this layer validates the complete outer container and preserves all
unselected member data and original manifest bytes.
"""
from dataclasses import dataclass
import xml.etree.ElementTree as ET
import re
from .raw_zip_reference import Archive,load_archive,replace_payloads,UnsupportedProfile

NS='http://schemas.intuit.com/LocalCfpContainer.xsd'
TYPES=('/tax/income/individual/taxreturn/taxml','/tax/income/individual/taxreturn/po',
 '/tax/income/individual/taxreturn/efile','/tax/income/individual/taxreturn/experience/turbotax/xml',
 '/tax/income/individual/aca/exemptionreturn')
MANIFEST=b'manifest.xml'
MAX_MANIFEST=1024*1024

@dataclass(frozen=True)
class Document:
 entity_type:str
 entity_type_code:object
 entity_key:str
 member_name:bytes
 payload:bytes

@dataclass(frozen=True)
class ClearContainer:
 archive:Archive
 manifest_xml:bytes
 documents:tuple
 unreferenced_members:tuple
 encryption_mode:str
 native_current_model_verified:bool=False
 payload_semantics_validated:bool=False

def _need(condition,message):
 if not condition:raise UnsupportedProfile(message)

def _named(parent,name):return tuple(child for child in parent if child.tag=='{'+NS+'}'+name)

def _leaf(parent,name):
 found=_named(parent,name);_need(len(found)==1,'One exact Manifest document '+name)
 node=found[0];_need(not len(node),'Finite leaf Manifest '+name)
 value=node.text or'';_need(bool(value)and'\0'not in value,'Nonempty exact Manifest '+name)
 return value

def load_clear_container(wire,*,encryption_mode):
 _need(encryption_mode=='cleartext'and type(encryption_mode)is str,'Explicit selected encrypt=false container profile; native default is encrypted')
 archive=load_archive(wire);members={m.name:m for m in archive.members}
 _need(len({name.lower()for name in members})==len(members),'Finite unambiguous ASCII case-folded ZIP names; native lookup alternatives are not guessed')
 _need(MANIFEST in members,'Exact manifest.xml member, not signature-only container validity')
 manifest=members[MANIFEST].payload
 _need(0<len(manifest)<=MAX_MANIFEST,'Bounded complete clear manifest.xml')
 try:text=manifest.decode('utf-8',errors='strict')
 except UnicodeError as e:raise UnsupportedProfile('Exact UTF8 clear manifest.xml; other encodings outside profile')from e
 _need('\0'not in text,'NUL bytes are outside the UTF8 manifest profile')
 _need('<!DOCTYPE'not in text.upper()and'<!ENTITY'not in text.upper(),'DTD/entity manifest syntax outside finite cleartext profile')
 declaration=re.match(r'\ufeff?\s*<\?xml\s+.*?\?>',text,re.DOTALL|re.IGNORECASE)
 if declaration:
  encoding=re.search(r'encoding\s*=\s*([\'"])(.*?)\1',declaration.group(),re.IGNORECASE)
  _need(not encoding or encoding.group(2).lower()in('utf-8','utf8'),'Declared UTF8 manifest encoding only')
 try:root=ET.fromstring(text)
 except ET.ParseError as e:raise UnsupportedProfile('Clear manifest.xml must parse; encrypted/default vendor containers are not decoded')from e
 _need(root.tag=='{'+NS+'}Manifest','Actual Manifest root and namespace')
 for name in('intuitIdentity','cfpIntuitIdentity'):
  values=_named(root,name);_need(len(values)<=1,'Finite single Manifest '+name)
  if values:_need(not len(values[0])and not(values[0].text or'').strip(),'Nonempty account identity is outside selected owner-unbound cleartext profile')
 security=_named(root,'security');_need(len(security)<=1,'Finite single security block')
 if security:_need(not len(security[0])and not security[0].attrib and not(security[0].text or'').strip(),'Nonempty security metadata is outside the selected cleartext profile')
 groups=_named(root,'documents');_need(len(groups)==1,'One actual Manifest documents collection')
 docs=[];keys=set();referenced={MANIFEST}
 for node in _named(groups[0],'document'):
  typ=_leaf(node,'entityType');key=_leaf(node,'entityKey')
  try:name=key.encode('utf-8')
  except UnicodeError as e:raise UnsupportedProfile('Exact UTF8 Manifest entityKey')from e
  _need(all(32<c<127 for c in name),'Finite printable ASCII document keys; original UTF8 lookup generality not claimed')
  _need(name!=MANIFEST and name in members and name not in keys,'Unique Manifest entityKey resolves to an exact ZIP member')
  # Native entityTypeForString is indexOfObject; unknown types are retained as
  # metadata and never silently assigned type0 or granted edit permission.
  code=TYPES.index(typ)if typ in TYPES else None
  docs.append(Document(typ,code,key,name,members[name].payload));keys.add(name);referenced.add(name)
 _need(bool(docs),'At least one exact stored Manifest document in this finite profile')
 return ClearContainer(archive,manifest,tuple(docs),tuple(m.name for m in archive.members if m.name not in referenced),'cleartext')

def document_by_key(container,key):
 _need(isinstance(container,ClearContainer)and type(key)is str,'Exact loaded container and complete entityKey')
 matches=tuple(d for d in container.documents if d.entity_key==key)
 _need(len(matches)==1,'One exact stored document key')
 return matches[0]

def document_by_type(container,entity_type):
 _need(isinstance(container,ClearContainer)and type(entity_type)is str,'Exact stored document type')
 matches=tuple(d for d in container.documents if d.entity_type==entity_type)
 _need(len(matches)==1,'Type-based selection requires exactly one document, without guessing first duplicate')
 return matches[0]

def replace_document_payload(container,key,payload,*,expected_entity_type):
 _need(isinstance(container,ClearContainer)and load_clear_container(container.archive.source,encryption_mode=container.encryption_mode)==container,'Unmodified complete container source state')
 _need(type(payload)is bytes and type(expected_entity_type)is str,'Exact replacement payload and explicit type binding')
 selected=document_by_key(container,key)
 _need(selected.entity_type==expected_entity_type and selected.entity_type_code is not None,'Selected existing Manifest type must match; unknown types remain stored only')
 wire=replace_payloads(container.archive,{selected.member_name:payload})
 read=load_clear_container(wire,encryption_mode='cleartext')
 _need(read.manifest_xml==container.manifest_xml and read.unreferenced_members==container.unreferenced_members,'Preserve original manifest/inventory')
 before={m.name:m for m in container.archive.members};after={m.name:m for m in read.archive.members}
 for name,m in before.items():
  if name!=selected.member_name:_need(after[name].local==m.local,'Every unselected local ZIP record remains byte-identical')
 _need(tuple((d.entity_type,d.entity_key,d.member_name)for d in read.documents)==tuple((d.entity_type,d.entity_key,d.member_name)for d in container.documents),'Preserve all document type/key bindings')
 return wire

def preserve_clear_container(container):
 _need(isinstance(container,ClearContainer)and load_clear_container(container.archive.source,encryption_mode=container.encryption_mode)==container,'Unmodified complete cleartext container')
 return container.archive.source
