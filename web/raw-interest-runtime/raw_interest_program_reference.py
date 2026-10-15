"""Compile a bounded current-interest comparison plan from caller-owned resources.

Only the owned phase boundaries and supported instruction vocabulary are fixed
here. Instructions, dependency order, literals, selectors and assignments come
from the validated original resource bytes. This does not run a native scheduler
or accept an external normalized vendor program as input.
"""
import copy,hashlib,json,re
from dataclasses import dataclass
from raw_tke_nodes_reference import read_node_table,read_xprf_directory
from raw_tke_xml_reference import read_xml_resource


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def require(condition,message):
 if not condition:raise ValueError(message)

@dataclass(frozen=True)
class Phase:
 path:tuple
 mode:str
 roots:tuple
 cuts:tuple=()

# These are independently selected execution boundaries, not serialized vendor
# instructions. A cut is supplied by another same-source phase/current reader;
# unresolved cuts retain the existing finite normal-return branch restrictions.
PHASES=(
 Phase(('all_sources','prefix'),'prefix',(14484,14649)),
 Phase(('all_sources','OIDtaxable'),'normal',(14545,)),
 Phase(('all_sources','K1'),'prefix',(14564,14572,14580)),
 Phase(('all_sources','STKBASIS'),'prefix',(14581,)),
 Phase(('all_sources','F6252'),'normal',(14557,)),
 Phase(('all_sources','scalar','other','bank'),'bank',(14664,14704)),
 Phase(('all_sources','scalar','other','OID'),'normal',(14692,14715)),
 Phase(('all_sources','scalar','other','scalar'),'flat',(14719,14722),tuple((r,'component',None)for r in(14664,14692,14704,14715))),
 Phase(('all_sources','scalar','seller'),'normal',(14631,10770)),
 Phase(('all_sources','scalar','Canadian'),'normal',(14641,14643),((12204,'unresolved_boolean',None),)),
 Phase(('all_sources','scalar','collection'),'scalar_collection',(14724,),tuple((r,'component',kind)for r,kind in((10770,'numeric'),(14631,'boolean'),(14641,'numeric'),(14643,'boolean'),(14719,'boolean'),(14722,'numeric')))),
 Phase(('all_sources','collection'),'collection',(14725,),tuple((r,'component',None)for r in(14484,14545,14557,14564,14572,14580,14581,14724))),
 Phase(('all_sources','EE'),'EE',(11746,15102,15111,15122,15166,15167),tuple((r,'unresolved_boolean',None)for r in(11664,11667,11672,11726,11727,11739,11740,15110,15121,15120))+((11743,'unresolved_string',None),(15165,'unresolved_numeric',None))),
 Phase(('presence','bank'),'bank',(14664,14732,14758,14773,14808,14833,14743,14799,14819,14844,14859)),
 Phase(('presence','OID'),'normal',(14737,14747,14757,14765,14770,14778,14792,14796,14813,14823,14838,14849,14866)),
 Phase(('presence','product'),'product',(14788,),tuple((r,'source_fact',None)for r in(9388,9398,10922,14651,14659))),
 Phase(('presence','presence'),'presence',(14873,),tuple((r,'component',None)for r in(14732,14758,14773,14743,14799,14808,14819,14833,14844,14859,14788,14737,14747,14757,14765,14770,14778,14792,14796,14813,14823,14838,14849,14866))),
 Phase(('tail',),'tail',(14727,14880,15174),tuple((r,'supplied',kind)for r,kind in((4263,'numeric_collection'),(9801,'boolean'),(14725,'numeric_collection'),(14873,'boolean'),(15167,'numeric')))),
)
SUPPORTED_GISTS=frozenset(('AboveThreshold','Accumulation','AllConditionsTrue','AtLeastOneConditionTrue','BooleanChoice','BooleanChoiceBasedOnCondition','BooleanCopy','BooleanCopyIfApplicable','Difference','Equals','GreaterThan','IsBlank','IsNotBlank','MFJMFSQualifier','MaximumTreatBlankAsZero','MultiCopyAccumulation','MultiCopyAccumulationWhenTrue','MultiCopyAtLeastOneConditionTrue','MultiCopyConcatenate','MultiCopyCopy','MultiCopyCountTrue','MultiCopyCreateFromBooleans','MultiCopyCreateFromNumerics','MultiCopyFilter','MultiCopySelectCorrespondingBoolean','MultiCopySelectCorrespondingNumeric','MultiCopySelectCorrespondingString','MultiCopySelectStringByID','NegativeOfValue','Not','NotEquals','NotEqualsIfNotBlank','NotEqualsTreatBlankAsZero','NumericCopy','NumericCopyIfApplicable','Opposite','Product','Quotient','SimpleBooleanCaseSelector','SimpleNumericCaseSelector','SimpleStringCaseSelector','StringCaseSelector','StringConcat','StringCopy','StringChoice'))
PREDICATES=frozenset(('True','False','Blank','TrueOrBlank','FalseOrBlank','NotBlank'))

# Accepted parameter signatures of the independently implemented finite gists.
ROLE_SIGNATURES={}
for _g in ('BooleanCopy','IsBlank','IsNotBlank','MaximumTreatBlankAsZero','MultiCopyAccumulation','MultiCopyAtLeastOneConditionTrue','MultiCopyConcatenate','MultiCopyCopy','MultiCopyCreateFromBooleans','MultiCopyCreateFromNumerics','NegativeOfValue','Not','NumericCopy','Opposite','StringCopy','Equals','NotEquals'):
 ROLE_SIGNATURES[_g]=(frozenset(('Value',)),)
for _g in ('AboveThreshold','GreaterThan'):ROLE_SIGNATURES[_g]=(frozenset(('Threshold','Value')),)
for _g in ('Difference','NotEqualsIfNotBlank','NotEqualsTreatBlankAsZero'):ROLE_SIGNATURES[_g]=(frozenset(('Left','Right')),)
for _g in ('SimpleBooleanCaseSelector','SimpleNumericCaseSelector','SimpleStringCaseSelector','StringCaseSelector'):ROLE_SIGNATURES[_g]=(frozenset(('Condition','Result')),frozenset(('Condition','Result','AssignIfTrueElseNormal')))
for _g in ('MultiCopySelectCorrespondingBoolean','MultiCopySelectCorrespondingNumeric','MultiCopySelectCorrespondingString'):ROLE_SIGNATURES[_g]=(frozenset(('CorrespondingKeys','Key','MultiCopyToSelectFrom')),)
for _g in ('BooleanChoice','StringChoice'):ROLE_SIGNATURES[_g]=(frozenset(('Choice','Possibility')),)
ROLE_SIGNATURES.update({
 'Accumulation':(frozenset(('Value',)),frozenset(('Value','BlankIfFalseOrBlank'))),
 'AllConditionsTrue':tuple(frozenset(x)for x in(('Condition',),('OppositeCondition',),('Condition','OppositeCondition'),('Condition','OppositeConditionTreatBlankAsFalse'))),
 'AtLeastOneConditionTrue':(frozenset(('Condition',)),),
 'BooleanChoiceBasedOnCondition':(frozenset(('Condition','ValueWhenBlank','ValueWhenFalse','ValueWhenTrue')),),
 'BooleanCopyIfApplicable':(frozenset(('ApplicableCondition','Value')),),
 'MFJMFSQualifier':(frozenset(('ConsideredMarried','FinalFilingStatus','MaritalStatus','WantToFileJoint')),),
 'MultiCopyAccumulationWhenTrue':(frozenset(('Conditions','Values')),),
 'MultiCopyCountTrue':(frozenset(('MultiCopy',)),),
 'MultiCopyFilter':(frozenset(('MultiCopy','ValuesAndConditions')),),
 'MultiCopySelectStringByID':(frozenset(('Default','ID','MultiCopy')),frozenset(('BlankIfFalseNotBlank','Default','ID','MultiCopy'))),
 'NumericCopyIfApplicable':(frozenset(('ApplicableCondition','Value')),frozenset(('ApplicableCondition','BlankIfFalseOrBlank','Value'))),
 'Product':(frozenset(('Product',)),frozenset(('BlankIfFalseOrBlank','Product'))),
 'Quotient':(frozenset(('Denominator','Numerator')),),
 'StringConcat':(frozenset(('First','Second','Third')),frozenset(('First','Second','Third','Fourth','Fifth'))),
})


def no_unknown(value):
 if type(value)is dict:
  require('uninterpreted_fields'not in value,'Unknown active protobuf facts refused')
  for x in value.values():no_unknown(x)
 elif type(value)is list:
  for x in value:no_unknown(x)


def children(value):
 require(set(value)=={'name','complex_value'}and set(value['complex_value'])=={'elements'},'Exact bounded complex configuration required')
 return value['complex_value']['elements']


def scalar(value):
 require(set(value)=={'name','scalar_value'},'Exact scalar configuration required');s=value['scalar_value'];kind=s.get('type',0)
 require(set(s)<=({'type','string_value'}if kind==3 else{'type','boolean_value'})and kind in(1,3),'Only original text/Boolean configuration supported')
 result=s.get('string_value','')if kind==3 else s.get('boolean_value',False)
 require(type(result)is(str if kind==3 else bool),'Configuration scalar type differs')
 return result


def named(values):
 result={}
 for value in values:
  key=value.get('name');require(type(key)is str and key and key not in result,'Duplicate/empty configuration names refused');result[key]=value
 return result


class Compiler:
 def __init__(self,table,constants,schema,derived,mapping=None):
  self.table=table;self.constants=constants;self.schema=schema;self.derived=derived;self.byid={f.node_id:r for r,f in table.frames.items()};self.cache={};self.rows=[];self.mapping={}
  if mapping is not None:
   require(mapping.tag=='{http://schemas.intuit.com/ctg/mapping}MappingRuntime','Original mapping XML root required')
   for m in mapping.iter('{http://schemas.intuit.com/ctg/mapping}Mapping'):
    mef=m.get('mef')
    if mef:self.mapping.setdefault(re.sub(r'\[[^]]*\]','',mef),[]).append(dict(attributes=dict(m.attrib),transforms=[dict(v.attrib)for v in m]))
  require(constants.tag=='Constants'and schema.tag=='Return','Original Constants/Return XML roots required')
 def node(self,ref):
  if ref not in self.cache:
   n=self.table.decode(ref);no_unknown(n);require(set(n)<={'type','node_id','node_reference','calculated_node','post_processing'},'Unsupported original node family refused');self.cache[ref]=n
  return self.cache[ref]
 def ref(self,nodeid):
  require(type(nodeid)is str and nodeid in self.byid,'Original configured node ID is absent');return self.byid[nodeid]
 def constant(self,n,mode):
  path=n['node_id'];require(path.startswith('/Constants/'),'Constant source namespace differs');elements=self.constants.findall(path[len('/Constants/'):]);require(len(elements)==1,'Unique original XML constant required');e=elements[0];kind=e.get('baseType');value=e.get('fixed');tag=None
  if e.get('isBlank')=='true':
   require(kind in('xsd:boolean','xsd:string','xsd:integer','xsd:decimal'),'Unsupported blank constant kind');tag='boolean'if kind=='xsd:boolean'else('string_blank'if mode=='bank'else'string');value=None
  elif kind=='xsd:boolean':require(value in('true','false'),'Boolean constant text required');tag='boolean';value=value=='true'
  elif kind in('xsd:integer','xsd:decimal'):
   require(type(value)is str and re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?',value)is not None and len(value)<=64,'Finite exact decimal constant required');tag='numeric'
  elif kind=='xsd:string':require(type(value)is str and value.isascii(),'Finite original ASCII literal required');tag='string'
  elif kind=='xsd:complexType':
   require(0<len(e)<=512,'Bounded original string map required');value={}
   for item in e:
    require(item.tag=='Element'and len(item)==2 and[item[0].tag,item[1].tag]==['ID','Value']and item[1].get('baseType')=='xsd:string','Exact original string-map entry required');key=item.findtext('ID');text=item.findtext('Value');require(type(key)is str and type(text)is str and key not in value,'Unique original string-map keys required');value[key]=text
   tag='string_map'
  else:raise ValueError('Unsupported source constant type')
  row=dict(reference=n['node_reference'],type='constant',value=value)
  if mode in('normal','bank','EE'):row['value_type']=tag
  return row
 def assignment(self,c,inputs):
  a=c.get('assign_statement',{});typ=a.get('type',0)
  if typ==0:require(not a,'Explicit/extended nonassignment refused');return dict(kind='none',condition=None)
  if typ==3:require(a=={'type':3,'condition':1},'Only normal UserEntered assignment supported');return dict(kind='user_entered',condition=None)
  require(typ==2 and set(a)<={'type','condition','condition_reference'}and a.get('condition')in(1,4),'Unsupported Default assignment condition')
  condition=a.get('condition_reference')if a['condition']==4 else None
  require((condition is None and set(a)=={'type','condition'})or(inputs.get('AssignIfTrueElseNormal')==[condition]and type(condition)is int),'Default conditional input differs')
  return dict(kind='fresh_default',condition=condition)
 def precision(self,n):
  p=n.get('post_processing',{})
  if not p:return None
  require(set(p)=={'rounder'},'Postprocessing flags/extra behavior unsupported');r=p['rounder'];typ=r.get('type',0)
  require(set(r)<={'type','dec_precision'}and typ in(2,3,4),'Unsupported active post-rounder')
  precision=0 if typ==2 else 2 if typ==3 else r.get('dec_precision',0)
  require(precision in(0,2,5,8),'Unimplemented precision refused');return precision
 def selector(self,cfg,inputs,*,value_type=None):
  require(set(cfg)=={'ResultGroups','ResultGroupToResultsMapping','Selector'}and scalar(cfg['ResultGroups'])=='Selected','Unsupported selector groups')
  results=set(inputs.get('Result',()));conditions=set(inputs.get('Condition',()));mapped=[]
  for entry in children(cfg['ResultGroupToResultsMapping']):
   require(entry['name']=='Mapping','Unsupported selector mapping');group=[]
   for part in children(entry):
    if part['name']=='ResultNodeID':mapped.append(self.ref(scalar(part)))
    else:require(part['name']=='ResultGroupName'and scalar(part)=='Selected','Selector result group differs');group.append(part)
   require(len(group)==1,'Unique selector group required')
  require(set(mapped)==results and len(mapped)==len(results),'Selector results differ from actual inputs')
  cases=[];default=None;ids=set()
  for case in children(cfg['Selector']):
   parts=children(case);idparts=[p for p in parts if p['name']=='ID'];targets=[p for p in parts if p['name']=='Result'];require(len(idparts)==len(targets)==1,'One selector case ID/result required');name=scalar(idparts[0]);target=self.ref(scalar(targets[0]));require(name not in ids and target in results,'Unique selector IDs and actual result required');ids.add(name);predicates=[]
   for p in parts:
    if p['name']in('ID','Result'):continue
    require(p['name']in PREDICATES,'Unknown selector predicate');ref=self.ref(scalar(p));require(ref in conditions,'Selector predicate is not an input');predicates.append([p['name'],ref])
   if case['name']=='DefaultCase':require(default is None and not predicates,'Unique unconditional default required');default=target
   else:require(case['name']=='Case'and predicates,'Nonempty selector case required');cases.append(dict(result=target,predicates=predicates))
  require(default is not None,'Explicit selector default required');out=dict(cases=cases,default=default)
  if value_type is not None:out['value_type']=value_type
  return out
 def choice(self,cfg):
  require(set(cfg)=={'ChoiceMapping'},'Exact ChoiceMapping required');options=[];default=None
  for option in children(cfg['ChoiceMapping']):
   fields={k:scalar(v)for k,v in named(children(option)).items()};require(fields.get('NoOtherOption')is True,'Only no-other-option choice profile supported');ref=self.ref(fields.get('ID'))
   if option['name']=='Option':require(set(fields)=={'ID','Value','NoOtherOption'},'Exact choice option required');options.append(dict(value=fields['Value'],reference=ref,no_other_option=True))
   else:require(option['name']=='DefaultOption'and set(fields)=={'ID','NoOtherOption'}and default is None,'Unique choice default required');default=ref
  require(default is not None and len({x['value']for x in options})==len(options),'Unique choice values/default required');return dict(options=options,default=default)
 def validate_not(self,n,cfg):
  require(set(cfg)=={'ChoiceMapping'},'Not requires original ChoiceMapping');d=self.derived.get('Not');require(d is not None and d.findtext('DerivedGistMapping/BaseGist')=='BooleanChoice','Original Not derived definition required');mapping=d.find('DerivedGistMapping');items=mapping.findall('InputMappings/Input');require([(i.findtext('Role'),i.findtext('MappedRole'))for i in items if i.find('Role')is not None]==[('Value','Choice')],'Not role mapping differs');constants=[i.find('Constant/Value')for i in items if i.find('Constant/Value')is not None];require([(x.get('baseType'),x.text)for x in constants]==[('xsd:boolean','true'),('xsd:boolean','false')],'Not derived constants differ')
  require([x.get('id')for x in constants]==['trueID','falseID'],'Not derived identity mapping differs');source=children(cfg['ChoiceMapping']);require(len(source)==2,'Not choice count differs');expected=[('Option',{'Value':'true','ID':n['node_id']+'/DerivedGistConstantValue1','NoOtherOption':False}),('DefaultOption',{'ID':n['node_id']+'/DerivedGistConstantValue0','NoOtherOption':False})]
  for el,(name,fields)in zip(source,expected):require(el['name']==name and{k:scalar(v)for k,v in named(children(el)).items()}==fields,'Not node-specific constant binding differs')
  dc=mapping.find('ConfigurationMappings/Configuration');require(dc is not None and dc.findtext('MappedName')=='ChoiceMapping','Not derived mapped name differs');constant=dc.find('Constant');require(constant is not None and[(x.tag,[(y.tag,y.text)for y in x])for x in constant]==[('Option',[('Value','true'),('ID','ID_FOR_CONSTANT_INPUT(falseID)'),('NoOtherOption','false')]),('DefaultOption',[('ID','ID_FOR_CONSTANT_INPUT(trueID)'),('NoOtherOption','false')])],'Not derived choice mapping differs')
 def multicopy_ids(self,cfg,inputs):
  require(set(cfg)=={'MultiCopyIDs'},'Exact MultiCopyIDs required');entries=[]
  for entry in children(cfg['MultiCopyIDs']):
   parts={k:scalar(v)for k,v in named(children(entry)).items()};require(entry['name']=='Entry'and set(parts)=={'MultiCopyID','Value'},'Exact MC key/value entry required');ref=self.ref(parts['Value']);require(ref in inputs.get('Value',()),'MC mapped value is not input');key=parts['MultiCopyID'];require(type(key)is str and key and'\0'not in key,'Finite MC literal key required');entries.append(dict(key=key,reference=ref))
  require(len(entries)==len({e['key']for e in entries})==len({e['reference']for e in entries})==len(inputs.get('Value',())),'Unique complete MC input mapping required');return entries
 def configuration(self,n,c,inputs,mode):
  gist=c['gist']['name'];cfg=named(c['gist'].get('configuration_values',[]))
  if gist=='MFJMFSQualifier':
   d=self.derived.get(gist);require(d is not None and d.findtext('DerivedGistMapping/BaseGist')=='AllConditionsTrue'and[(x.findtext('Role'),x.findtext('MappedRole'))for x in d.findall('DerivedGistMapping/InputMappings/Input')]==[('ConsideredMarried','Condition'),('WantToFileJoint','Condition')],'MFJMFS source role mapping differs')
  if gist=='Not':self.validate_not(n,cfg);return 'source_boolean_not'if mode=='product'else{'source_boolean_not':True}
  if gist in('SimpleStringCaseSelector','StringCaseSelector','SimpleBooleanCaseSelector','SimpleNumericCaseSelector'):
   return dict(selector=self.selector(cfg,inputs,value_type=None if mode in('EE','tail')else'boolean'if gist=='SimpleBooleanCaseSelector'else'string'))
  if gist in('BooleanChoice','StringChoice'):return dict(choice=self.choice(cfg))
  if gist=='BooleanChoiceBasedOnCondition':
   choice=self.choice(cfg);require(choice==dict(options=[dict(value=k,reference=inputs[role][0],no_other_option=True)for k,role in(('true','ValueWhenTrue'),('false','ValueWhenFalse'))],default=inputs['ValueWhenBlank'][0]),'Derived Boolean choice roles/configuration differ');d=self.derived.get(gist);require(d is not None and d.findtext('DerivedGistMapping/BaseGist')=='BooleanChoice','Original Boolean choice derived definition required');return ['true','false','blank']
  if gist in('MultiCopyCreateFromBooleans','MultiCopyCreateFromNumerics'):return self.multicopy_ids(cfg,inputs)
  output={}
  allowed={'Accumulation':{'SkipToInputIfOnlyOneSet','Type'},'AllConditionsTrue':{'SkipToInputIfOnlyOneFalse'},'NumericCopyIfApplicable':{'SkipToIfCopied'},'BooleanCopyIfApplicable':{'SkipToIfCopied'},'MaximumTreatBlankAsZero':{'TreatBlankAsZero'}}.get(gist,set())
  for key,value in cfg.items():
   require(key in allowed,'Unimplemented gist configuration refused');v=scalar(value);require((key=='Type'and v=='generatedName')or v is True,'Unsupported configuration value');output[key]=v
  if gist=='MaximumTreatBlankAsZero':require(output=={'TreatBlankAsZero':True},'Maximum blank rule differs')
  return output
 def phase(self,plan):
  cuts={ref:(typ,kind)for ref,typ,kind in plan.cuts};seen=set();visiting=set()
  def walk(ref):
   require(type(ref)is int and ref in self.table.frames,'Original dependency reference absent');require(ref not in visiting,'Cyclic finite source dependency refused')
   if ref in seen:return
   require(len(seen)<2048,'Finite source cone budget exceeded');visiting.add(ref);n=self.node(ref);typ=n.get('type',0)
   if ref not in cuts and typ==0:
    c=n.get('calculated_node');require(type(c)is dict,'Calculated source body required')
    for item in c.get('inputs',[]):
     for dep in item.get('node_references',[]):walk(dep)
   visiting.remove(ref);seen.add(ref)
  for r in plan.roots:walk(r)
  order=sorted(seen)
  if plan.mode in('collection','scalar_collection'):order=[r for r,_,_ in plan.cuts]+sorted(seen-set(cuts))
  rows=[]
  for ref in order:
   n=self.node(ref);typ=n.get('type',0);row=dict(reference=ref)
   if ref in cuts:
    tag,kind=cuts[ref];row['type']=tag
    if kind is not None:row['supply_kind'if tag=='supplied'else'value_type']=kind
   elif typ in(2,5):require('calculated_node'not in n,'Input cannot carry a calculation');row['type']='input'
   elif typ==1:
    require('calculated_node'not in n,'Constant cannot carry a calculation');row=self.constant(n,plan.mode)
    require(not n.get('post_processing')or(n['post_processing']=={'rounder':{'type':5}}and row['value']=='0'),'Unsupported constant postprocessing')
   else:
    require(typ==0,'Unsupported finite graph node type');c=n['calculated_node'];require(set(c)<={'flags','gist','inputs','assign_statement','iterator','blank_condition'},'Unimplemented calculated-node features refused');flags=c.get('flags',{});require(set(flags)<={'can_auto_iterate','can_optimize','explanation_only','has_manual_iteration'}and all(type(x)is bool for x in flags.values()),'Unimplemented calculated-node flags refused');g=c.get('gist',{});require(set(g)<={'name','configuration_values'}and g.get('name')in SUPPORTED_GISTS,'Unsupported original gist refused');gist=g['name'];items=c.get('inputs',[]);inputs={}
    for item in items:
     require(set(item)=={'role','node_references'}and item['role']not in inputs and item['node_references'],'Exact unique nonempty input roles required');require(0<len(item['node_references'])<=128,'Finite input cardinality exceeded');inputs[item['role']]=list(item['node_references'])
    require(frozenset(inputs)in ROLE_SIGNATURES[gist],'Unimplemented gist input signature refused')
    iterator=c.get('iterator',{});require(set(iterator)<={'iterated_inputs'},'Unimplemented iterator semantics refused');iteration=list(iterator.get('iterated_inputs',()));require(len(iteration)==len(set(iteration))and set(iteration)<={x for xs in inputs.values()for x in xs},'Iterator is not a unique input subset')
    assignment=self.assignment(c,inputs);precision=self.precision(n);blank=None
    if'blank_condition'in c:
     b=c['blank_condition'];require(set(b)<={'type','condition_reference','output_blank_values'}and b.get('type')in(2,3)and type(b.get('condition_reference'))is int,'Unimplemented blank condition refused');require(inputs.get('BlankIfFalseNotBlank'if b['type']==2 else'BlankIfFalseOrBlank')==[b['condition_reference']],'Blank condition is not the actual bound input');blank=dict(type=b['type'],reference=b['condition_reference'],output_blank_values=b.get('output_blank_values',False))
    config=self.configuration(n,c,inputs,plan.mode);row.update(type='calculated',gist=gist,inputs=inputs)
    mode=plan.mode
    if mode in('normal','bank'):
     row.update(iterated_inputs=iteration,configuration=config,assignment=assignment if mode=='normal'else assignment['kind'],round_precision=precision,blank_condition=blank)
    elif mode=='prefix':
     require(not config and precision is None and blank is None and assignment['kind']in('none','user_entered'),'Prefix protocol exceeds finite implementation');row.update(iterated_inputs=iteration,assignment=assignment['kind'])
    elif mode=='EE':
     require(not iteration and assignment['kind']=='none'and blank is None,'EE finite normal-return protocol differs');row.update(configuration=config,round_precision=precision)
    elif mode=='product':
     require(assignment['kind']=='none'and blank is None and precision is None,'Product finite protocol differs');row.update(iterated_inputs=iteration,configuration=config or None)
    elif mode in('flat','presence'):
     require(not iteration and precision is None and blank is None and assignment['kind']in('none','user_entered'),'Flat finite protocol differs');require(not config or(mode=='presence'and gist=='MultiCopyCreateFromBooleans'),'Unimplemented flat configuration');row.update(assignment=assignment['kind'])
     if mode=='presence':row['configuration']=config or None
    elif mode in('scalar_collection','collection'):
     require(not iteration and assignment['kind']=='none'and blank is None and precision is None,'Collection finite protocol differs')
     if mode=='scalar_collection':require(not config or gist in('MultiCopyCreateFromBooleans','MultiCopyCreateFromNumerics'),'Unimplemented scalar collection configuration');row['configuration']=config or None
     else:require(not config,'Unimplemented collection configuration')
    elif mode=='tail':
     require(not iteration and precision is None and blank is None and assignment['kind']in('none','user_entered'),'Tail finite protocol differs');selector=None
     if gist=='SimpleNumericCaseSelector':
      s=config['selector'];require(len(s['cases'])==1 and len(s['cases'][0]['predicates'])==1 and s['cases'][0]['predicates'][0][0]=='True','Only single-True tail selector supported');selector=dict(condition=s['cases'][0]['predicates'][0][1],when_true=s['cases'][0]['result'],default=s['default'])
     else:require(not config or gist in('Not','MaximumTreatBlankAsZero'),'Unimplemented tail configuration')
     a='none'if assignment['kind']=='none'else'uniform_absent_user_entered'if ref==14726 else'scalar_user_entered';row.update(assignment=a,selector=selector)
    else:raise ValueError('Unimplemented finite phase mode')
   rows.append(row)
  model=dict(roots=list(plan.roots),nodes=rows);sources=[]
  for ref in sorted(seen):
   n=self.node(ref);f=self.table.frames[ref];entry=dict(reference=ref,node_id=f.node_id,node_type=f.node_type,frame_start=f.start,frame_end=f.end,frame_sha256=f.sha256,cut=ref in cuts,source_post_processing=n.get('post_processing'),mapping_entries=self.mapping.get(f.node_id,[]))
   if n.get('type',0)in(2,5)and f.node_id.startswith('/Return/'):
    elements=self.schema.findall(f.node_id[len('/Return/'):]);require(len(elements)<=1,'Ambiguous original schema input element');entry['schema_element_found']=bool(elements);entry['schema_attributes']=dict(elements[0].attrib)if elements else None;entry['input_post_processing']=n.get('post_processing')
   sources.append(entry)
  return dict(model=model,sha256=hashlib.sha256(canonical(model)).hexdigest()),dict(path=list(plan.path),mode=plan.mode,roots=list(plan.roots),cuts=[dict(reference=r,type=t,value_type=k)for r,t,k in plan.cuts],sources=sources)


def _compile_current_interest_programs_uncached(carrier,*,authority):
 """Return programs + provenance; authority must be authenticated by the host.

 A hash supplied by an untrusted request is not a trusted original-resource
 identity. The caller controls this immutable authority outside that request.
 """
 require(type(authority)is dict and set(authority)=={'carrier_sha256','payload_sha256'},'Externally authenticated complete resource identities required');payloads=authority['payload_sha256'];require(type(payloads)is dict and set(payloads)=={5014,5015,5017,5021,5036},'Exact original numeric resource identities required')
 table=read_node_table(carrier,approved_carrier_sha256=authority['carrier_sha256'],approved_payload_sha256=payloads[5036]);definitions={}
 for kind in(5014,5015,5017,5021):definitions[kind]=read_xml_resource(carrier,approved_carrier_sha256=authority['carrier_sha256'],approved_payload_sha256=payloads[kind],resource_type=kind,resource_id=1)
 require(len(definitions[5014])==len(definitions[5015])==len(definitions[5017])==1,'One complete schema/constants/mapping definition required');derived={}
 for d in definitions[5021]:
  root=d.parse();name=root.findtext('Name');require(root.tag=='Gist'and type(name)is str and name not in derived,'Unique derived Gist definition required');derived[name]=root
 require(len(derived)==93,'Reviewed derived-definition catalog version required');directory=read_xprf_directory(carrier,expected_sha256=authority['carrier_sha256']);compiler=Compiler(table,definitions[5015][0].parse(),definitions[5014][0].parse(),derived,definitions[5017][0].parse());programs={};phases=[]
 for phase in PHASES:
  compiled,report=compiler.phase(phase);target=programs
  for key in phase.path[:-1]:target=target.setdefault(key,{})
  target[phase.path[-1]]=compiled;phases.append(report)
 return dict(programs=programs,provenance=dict(carrier_sha256=table.carrier_sha256,resource_directory_complete=True,graph_resource=dict(resource_type=5036,resource_id=1,offset=table.resource_offset,bytes=table.resource_size,payload_sha256=table.payload_sha256,total_nodes=len(table.frames)),XML_resources=[dict(resource_type=k,resource_id=1,offset=directory[k,1][0],bytes=directory[k,1][1],payload_sha256=payloads[k],definitions=[dict(index=d.index,source_start=d.source_start,source_end=d.source_end,source_sha256=d.source_sha256,decoded_sha256=d.decoded_sha256,decoded_bytes=len(d.decoded))for d in ds])for k,ds in definitions.items()],phases=phases,active_unique_references=len(compiler.cache)),external_normalized_programs_accepted=False,vendor_programs_or_tables_bundled=False,original_native_runtime=0,native_dependency_schedule_executed=False,normal_return_finite_branch_only=True,original_input_and_constant_postprocessing_executed=False,native_current_inventory_verified=False,comparison_only=True,writeback_allowed=False)


# One owned resource-program cache. This never stores current document/FV data.
# A complete file digest and host-authority digest are checked on every call;
# only a previous successful complete decode can populate this single entry.
_RESOURCE_PROGRAM_CACHE=None

def compile_current_interest_programs(carrier,*,authority):
 global _RESOURCE_PROGRAM_CACHE
 require(type(carrier)is bytes and type(authority)is dict and set(authority)=={'carrier_sha256','payload_sha256'},'Exact caller bytes and external authority required')
 require(hashlib.sha256(carrier).hexdigest()==authority['carrier_sha256'],'Caller resource identity changed before compile/cache lookup')
 key=(authority['carrier_sha256'],hashlib.sha256(canonical(authority)).hexdigest())
 if _RESOURCE_PROGRAM_CACHE is not None and _RESOURCE_PROGRAM_CACHE[0]==key:
  return copy.deepcopy(_RESOURCE_PROGRAM_CACHE[1])
 output=_compile_current_interest_programs_uncached(carrier,authority=authority)
 _RESOURCE_PROGRAM_CACHE=(key,copy.deepcopy(output))
 return output
