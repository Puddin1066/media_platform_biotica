"""Build a validated Runway workflow request from meaningful Studio input names."""
import json
from pathlib import Path
from runway_operation import validate
def build_request(values,request_id,estimated_credits,allow_media_spend=False):
    binding=json.loads((Path(__file__).parent/'studio/runway_workflow_bindings.json').read_text())
    unknown=set(values)-set(binding['inputs'])
    if unknown: raise ValueError('Unknown workflow controls: '+', '.join(sorted(unknown)))
    if not str(values.get('abstract_text','')).strip(): raise ValueError('An abstract is required')
    # Clear inherited citations explicitly rather than reusing a previous topic's citation.
    values={'citation_details':'',**values}
    outputs={}
    for name,value in values.items():
        item=binding['inputs'][name]
        if not isinstance(value,str): raise ValueError('Workflow inputs must be strings')
        payload={'type':item['type'],'uri':value} if item['type']=='video' else {'type':'primitive','value':value}
        if item['type']=='video' and ('_jwt=' in value or 'X-Amz-Signature=' in value):
            raise ValueError('Use durable Studio media rather than expiring signed URLs')
        outputs[item['node_id']]={item['output']:payload}
    request={'request_id':request_id,'operation':'post_workflows_id','path_params':{'id':binding['workflow_id']},'body':{'nodeOutputs':outputs},'allow_mutation':True,'allow_media_spend':allow_media_spend,'estimated_credits':estimated_credits}
    validate(request)
    return request
