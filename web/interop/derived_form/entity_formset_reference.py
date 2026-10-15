"""Independent C0/DC header/context and finiteoneFormSet/oneForm Entity bytes.

Source snapshot currentSchema18/release100/platform7. Release is an internal
formatnumber, not taxyear. ExplicitBEscalars/rawLE/swapfalse requiresplatform7
and FormSetflag0. Changed-platform/flag1branches retained as refusedprofiles.
No actual.taxfixture/nativeexecution; selectedEntitybytes not universal.tax.
"""
from dataclasses import dataclass,replace
import struct
from .selected_form_record_reference import store_selected_form_record,load_selected_form_record,UnsupportedProfile
from .form_header_map_reference import new_map,store_map,append_position,get_position,load_map
CURRENT_SCHEMA=18
CURRENT_RELEASE=100
ENDIANNESS=(0,1,1,1,1,0,0)
@dataclass(frozen=True)
class EntityHeader:
 kind:int=0x45
 platform:int=7
 release:int=100
 schema:int=18
 serial:int=0
 producer:bytes=b'Tax Reborn independent'
 legacy_hash_size:int=127
 format_word3e:int=0
@dataclass(frozen=True)
class EntityHeaderLoad:
 header:EntityHeader
 code:int
 consumed:int
 recognized_C0:bool

def matches_platform(platform):return type(platform) is int and 0<=platform<8 and bool((0xc2>>platform)&1)
def get_endianness(platform):return ENDIANNESS[platform-1] if type(platform) is int and 1<=platform<=7 else 1

def store_entity_header(h):
 if not isinstance(h,EntityHeader) or type(h.producer) is not bytes or len(h.producer)>255:raise UnsupportedProfile('ExplicitEntityHeader/independentproducer255guard')
 if not 16<=h.schema<=CURRENT_SCHEMA:raise UnsupportedProfile('ModernStorealwayswriteslegacyhashword; oldschema<16loader grammarseparate')
 return bytes([0xc0,h.kind,h.platform,h.release,h.schema])+struct.pack('>I',h.serial)+bytes([len(h.producer)])+h.producer+struct.pack('>2H',h.legacy_hash_size,h.format_word3e)

def load_entity_header(wire,old=EntityHeader(),*,initial_error=0):
 if type(wire) is not bytes:raise UnsupportedProfile('Explicitfinitebinary')
 h=replace(old,kind=0,platform=0,release=0,schema=0,serial=0,producer=b'',format_word3e=0)
 if initial_error:return EntityHeaderLoad(h,initial_error,0,False)
 if not wire:raise UnsupportedProfile('CompleteC0tag')
 if wire[0]!=0xc0:return EntityHeaderLoad(h,0,1,False) # Actual no fabricatednativeerror.
 if len(wire)<10:raise UnsupportedProfile('CompleteC0fixedheader')
 kind,platform,release,schema=wire[1:5];serial=struct.unpack_from('>I',wire,5)[0];n=wire[9];p=10
 if p+n+(4 if schema>=16 else 2)>len(wire):raise UnsupportedProfile('CompleteC0producer/words')
 producer=wire[p:p+n];p+=n
 if schema<16:legacy=64
 else:legacy=struct.unpack_from('>H',wire,p)[0];p+=2
 word=struct.unpack_from('>H',wire,p)[0];p+=2
 h=EntityHeader(kind,platform,release,schema,serial,producer,legacy,word)
 code=0
 if kind!=0x45 or platform not in (1,3,4,5,6,7):code=0x1fb
 elif release<95:code=0x1ff
 elif schema>CURRENT_SCHEMA or release>CURRENT_RELEASE:code=0x224
 elif schema<=9:code=0x1ff
 return EntityHeaderLoad(h,code,p,True)

@dataclass(frozen=True)
class FormSetHeader:
 identifier:bytes=b'TAX2025'
 endian_flag:bool=False
 reserved_byte:int=0
 boolean64:bool=False
 serial0:int=0
 serial1:int=0
 serial2:int=0
 flags:int=0
 template_version:int=0
 schema:int=18
 field20:int=0
 reserved_words:tuple=(0,)*9
@dataclass(frozen=True)
class FormSetHeaderLoad:
 header:FormSetHeader
 code:int
 consumed:int
 marker:int
 values_were_streamed:bool=False

def store_formset_header(h):
 if not isinstance(h,FormSetHeader) or type(h.identifier) is not bytes or not 1<=len(h.identifier)<=32 or any(b==0 or b>127 for b in h.identifier):raise UnsupportedProfile('PreparedASCIIFormSetID1..32; strongerindependentprofile')
 if len(h.reserved_words)!=9:raise UnsupportedProfile('ModernDC9reservedwords')
 # Actualordinarynullstorecontext clearsflagsbit10, leavesotherbits.
 flags=h.flags&~0x10
 return b'\xdc'+struct.pack('>H',len(h.identifier))+h.identifier+bytes([bool(h.endian_flag),0,bool(h.boolean64)])+struct.pack('>3IHIH10I',h.serial0,h.serial1,h.serial2,flags,h.template_version,CURRENT_SCHEMA,h.field20,*((0,)*9))

def load_formset_header(wire):
 if type(wire) is not bytes or not wire:raise UnsupportedProfile('Completeformsettag')
 marker=wire[0]
 if marker not in (0xda,0xdc):return FormSetHeaderLoad(FormSetHeader(),0x200,1,marker)
 if len(wire)<3:raise UnsupportedProfile('CompleteFormSetIDlength')
 n=struct.unpack_from('>H',wire,1)[0];p=3
 if n>32:raise UnsupportedProfile('IndependentpreparedFormSetID32bound; nativeAssignpolicy separate')
 size=23+(40 if marker==0xdc else 0)
 if p+n+size>len(wire):raise UnsupportedProfile('CompleteDC/DAheader')
 name=wire[p:p+n].split(b'\0',1)[0];p+=n
 endian,reserved,boolean=wire[p:p+3];p+=3
 s0,s1,s2,flags,tv,schema=struct.unpack_from('>3IHIH',wire,p);p+=20
 field20=0;words=(0,)*9
 if marker==0xdc:
  values=struct.unpack_from('>10I',wire,p);p+=40;field20,*words=values
 h=FormSetHeader(name,bool(endian),reserved,bool(boolean),s0,s1,s2,flags,tv,schema,field20,tuple(words))
 return FormSetHeaderLoad(h,0,p,marker,bool(flags&0x10))

def formset_swap_after(*,current_swap,entity_schema,formset_endian_flag):
 if any(type(x) is not bool for x in (current_swap,formset_endian_flag)):raise UnsupportedProfile('Explicitprocessorflag/sourceheaderboolean')
 # Native only setsTRUE here; falseformsetflagdoesnotclearinheritedTRUE.
 return current_swap or (entity_schema>13 and formset_endian_flag)

@dataclass(frozen=True)
class SelectedEntity:
 wire:bytes
 entity_header:EntityHeader
 formset_header:FormSetHeader
 entity_map:object
 form_map:object
 form_record:object
 entire_selected_entity_emitted:bool=True
 whole_tax_compatibility:bool=False
 native_execution_count:int=0
@dataclass(frozen=True)
class SelectedEntityLoad:
 entity_header:object
 formset_header:object
 form_record:object
 code:object
 consumed:int
 entity_initial_swap:object=None
 formset_resulting_swap:object=None
 entire_selected_entity_consumed:bool=False
 whole_tax_compatibility:bool=False
 native_execution_count:int=0

def _index(marker,base,start,end):
 m=store_map(new_map(marker,2),base).mapping;m=append_position(m,start).mapping;m=append_position(m,end).mapping
 return m,store_map(m,base).wire

def store_selected_entity(entity,formset,header,hash_state,string_table,buffers,*,table_id=2):
 if entity.platform!=7 or entity.schema!=18 or entity.kind!=0x45 or not 95<=entity.release<=CURRENT_RELEASE:
  raise UnsupportedProfile('Selectedsourceplatform7/modern18/supportedrelease')
 if formset.endian_flag or formset.flags&0x10:raise UnsupportedProfile('Selectedunstreamed/swapfalse; notsilentlywrapped')
 eh=store_entity_header(entity);fh=store_formset_header(formset)
 entitybase=len(eh);formsetbase=entitybase+13;formsbase=formsetbase+len(fh);formbase=formsbase+13
 record=store_selected_form_record(header,hash_state,string_table,buffers,table_id=table_id,base_position=formbase,version=entity.schema)
 end=formbase+len(record.wire);fm,fw=_index(0xc8,formsbase,formbase,end);em,ew=_index(0xc7,entitybase,formsetbase,end)
 return SelectedEntity(eh+ew+fh+fw+record.wire,entity,formset,em,fm,record)

def load_selected_entity(wire,buffers,*,current_table_id=3,prepared_parents=(),prepared_template_version=0):
 eh=load_entity_header(wire)
 if eh.code:return SelectedEntityLoad(eh.header,None,None,eh.code,eh.consumed)
 if not eh.recognized_C0:raise UnsupportedProfile('IndependentC0eligibility; nativewrongtagreturns0afterclearingheader')
 initial_swap=not matches_platform(eh.header.platform)
 if eh.header.platform!=7 or eh.header.schema!=18 or initial_swap:raise UnsupportedProfile('Selectedplatform7/18/EntityMatchesPlatformswapfalse only')
 p=eh.consumed;em=load_map(wire[p:],0xc7,p)
 if em.code:return SelectedEntityLoad(eh.header,None,None,em.code,p+em.consumed,initial_swap)
 if em.mapping.capacity!=2 or em.mapping.used!=2 or em.mapping.offsets[0]!=13:raise UnsupportedProfile('IndependentoneFormSetindexprofile')
 start=get_position(em.mapping,0);end=get_position(em.mapping,1)
 if start!=p+em.consumed or not start<end<=len(wire):raise UnsupportedProfile('IndependentorderedEntitysectionbounds')
 fh=load_formset_header(wire[start:end])
 if fh.code:return SelectedEntityLoad(eh.header,fh.header,None,fh.code,start+fh.consumed,initial_swap)
 changed_swap=formset_swap_after(current_swap=initial_swap,entity_schema=eh.header.schema,formset_endian_flag=fh.header.endian_flag)
 if changed_swap or fh.values_were_streamed:raise UnsupportedProfile('ActualFormSetSwap/streamedvalues branch requiresothercodec, refused')
 if prepared_template_version!=fh.header.template_version:raise UnsupportedProfile('Preparedmatchingtemplateprovider only; nativemismatchmarksfilechanged/mutatescounters')
 p=start+fh.consumed;fm=load_map(wire[p:end],0xc8,p)
 if fm.code:return SelectedEntityLoad(eh.header,fh.header,None,fm.code,p+fm.consumed,initial_swap,changed_swap)
 if fm.mapping.capacity!=2 or fm.mapping.used!=2 or fm.mapping.offsets[0]!=13:raise UnsupportedProfile('IndependentoneordinaryFormindexprofile')
 formstart=get_position(fm.mapping,0);formend=get_position(fm.mapping,1)
 if formstart!=p+fm.consumed or formend!=end:raise UnsupportedProfile('IndependentFormSetsectionbounds')
 form=load_selected_form_record(wire[formstart:formend],buffers,base_position=formstart,current_table_id=current_table_id,prepared_parents=prepared_parents,version=eh.header.schema)
 if form.code:return SelectedEntityLoad(eh.header,fh.header,form,form.code,formstart+form.consumed,initial_swap,changed_swap)
 if end!=len(wire):raise UnsupportedProfile('ExactselectedEntityend; otherouterwrappers/trailingdata outsideprofile')
 return SelectedEntityLoad(eh.header,fh.header,form,0,end,initial_swap,changed_swap,True)
