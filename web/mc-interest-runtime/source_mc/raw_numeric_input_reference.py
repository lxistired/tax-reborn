"""Pure raw-node/schema policy; no private request driver."""

REFS={'L1':9400,'L3':9401,'EXINT':9441}


FRAMES={9400:'1aff0857a9fe3351d964ccf7e7b20cec9c882e3db021a6a5bf70075685e0f9bb',9401:'3479de34659ea537d125854c78f9aabd242e84e83d64d0ec4903067b1fcb30e0',9441:'1281a7aa8cbe6540f1a384e58253043b4e861d15e5761335e490768ac09cc500'}


CARRIER='5e8db09dc9c4126c0cd85fe11ee7b02965a3b9e88db1075ba32efc4269e0bc2f'


NODE_PAYLOAD='517b84458389f7f259f708e525070a47c85f6fd11b4aa06a3a1ac02de3b73a92'


SCHEMA_PAYLOAD='f027a36fba39d21e1ea9ca60e740c1b144e7e10440491500130bc7492da0ebdd'


SCHEMA_XML='712c753298e1f232949368e9d73ec6e999d3b5f15bbda70d69b9461442efb0d3'


def ordinary_type(node_id,base_type,previous=5):
 if not isinstance(node_id,str) or not node_id.isascii() or not node_id.startswith('/Return/'):
  raise ValueError('Exact ordinary ASCII Return path required')
 # Three original length-aware substring classifiers.  This finite profile
 # accepts no metadata/covered-field alternative type branches.
 raw=node_id.encode('ascii')
 if any(token in raw for token in (b'[@covered]',b'/TKEMetaData/',b'FieldAttributes')):
  raise ValueError('Metadata or covered-field input type is outside this profile')
 if base_type!='xsd:integer':raise ValueError('Exact reviewed integer schema base type required')
 if type(previous)is not int or previous not in range(6):raise ValueError('Explicit finite stored type required')
 if previous==5:return 2
 if previous!=2:raise ValueError('Source MismatchTypeException: existing type differs from schema')
 return previous


def derive_policy(table,schema,field,expected_node_id):
 if field not in REFS:raise ValueError('One exact three-field raw input policy required')
 ref=REFS[field];frame=table.frames.get(ref)
 if frame is None or frame.sha256!=FRAMES[ref]:raise ValueError('Original raw input node frame changed')
 n=table.decode(ref)
 if n!={'type':5,'node_id':expected_node_id,'node_reference':ref}:raise ValueError('Exact raw type5 input without PostProcessing required')
 if schema.tag!='Return'or not expected_node_id.startswith('/Return/'):raise ValueError('Original ElementTypes Return schema required')
 elements=schema.findall(expected_node_id[len('/Return/'):])
 if len(elements)!=1:raise ValueError('One actual original schema input declaration required')
 attrs=elements[0].attrib
 if attrs.get('baseType')!='xsd:integer'or attrs.get('type')!='USAmountType'or attrs.get('structure')!='field':
  raise ValueError('Exact reviewed xsd:integer ordinary amount declaration required')
 cursor=schema;path='/Return';ancestors=[]
 for name in expected_node_id.split('/')[2:]:
  children=cursor.findall(name)
  if len(children)!=1:raise ValueError('Unique exact original schema ancestry required')
  cursor=children[0];path+='/'+name
  if cursor.get('multiCopy')=='true':ancestors.append(path)
 if ancestors!=['/Return/ReturnData/PP1099Int']:raise ValueError('Exact nonempty MC input ancestry required; no invented row domain')
 return dict(reference=ref,node_id=expected_node_id,source_frame_sha256=frame.sha256,
  raw_node=dict(n),raw_post_processing_message_present=False,
  normal_fresh_node_post_pointer_NULL=True,postprocessing_class='NoPostProcessing',
  inner_postprocessing_class='NoPostProcessing',numeric_precision=2,
  constructor_InputNode_value_type=5,constructor_value_type_means_unresolved=True,
  schema_declaration=dict(attrs),source_model_ValueTypes=ordinary_type(expected_node_id,attrs['baseType']),
  value_type_assignment_rule='unknown5 adopts schema type; pretyped different type throws MismatchTypeException; missing info leaves unresolved',
  source_multicopy_ancestors=ancestors,MC_ancestor_UUIDs_or_inventory_recovered=False,
  normal_final_input_postprocess='NoPostProcessing preserves shared Value object',
  schema_integer_does_not_truncate_input_cents=True,
  precision_selection='fresh Node.post NULL -> NoPost MC inner byte8=1 -> xor1=0 Factory slot20 -> NoOp precision2',
  MC_CompleteSetup_rule='only checks nonempty ancestors; no claim it calls scalar InputNode.CompleteSetup',
  native_InputNode_setup_executed=False,native_ElementTypes_registry_active=False)

