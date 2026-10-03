"""Build Studio's operation catalog from Runway's official OpenAPI document.

Run with --source for a reproducible offline refresh. The checked-in catalog
includes validation schemas, not credentials, so both Studio and the worker
can agree on exactly which operations and inputs are supported.
"""
import argparse
import hashlib
import json
from pathlib import Path

METHODS = {'get', 'post', 'patch', 'put', 'delete'}

def group(path):
    name = path.split('/')[2]
    if name in {'avatars','avatar_videos','avatar_conversations','avatar_usage','realtime_sessions','documents','voices'}:
        return 'Characters and voices'
    if name in {'workflows','workflow_invocations'}: return 'Published workflows'
    if name in {'routers','generate'}: return 'Model routing'
    if name == 'recipes': return 'Recipes'
    if name in {'organization','tasks','uploads'}: return 'Account and task tools'
    if name in {'text_to_speech','speech_to_speech','sound_effect','voice_dubbing','voice_isolation'}: return 'Audio'
    if name in {'image_upscale','video_upscale','video_to_hdr'}: return 'Enhancement'
    return 'Image and video'

def example(schema):
    """Seed required fields only; placeholders require an explicit user edit."""
    if 'const' in schema: return schema['const']
    if 'default' in schema: return schema['default']
    if 'enum' in schema: return schema['enum'][0]
    if 'oneOf' in schema or 'anyOf' in schema: return example((schema.get('oneOf') or schema['anyOf'])[0])
    kind = schema.get('type')
    if kind == 'object': return {k: example(schema.get('properties',{}).get(k,{})) for k in schema.get('required',[])}
    if kind == 'array': return [example(schema.get('items',{})) for _ in range(schema.get('minItems',0))]
    if kind in {'integer','number'}: return schema.get('minimum',1)
    if kind == 'boolean': return False
    return ''

def compact(value):
    # Retain validation keywords while omitting lengthy provider prose.
    if isinstance(value,dict): return {k:compact(v) for k,v in value.items() if k not in {'description','examples','$schema','deprecated'}}
    if isinstance(value,list): return [compact(v) for v in value]
    return value

def build(spec, source_sha):
    operations=[]
    for path, methods in spec['paths'].items():
        for method, item in methods.items():
            if method not in METHODS: continue
            schema=item.get('requestBody',{}).get('content',{}).get('application/json',{}).get('schema')
            parameters=[p for p in item.get('parameters',[]) if p.get('in') in {'path','query'}]
            task=method=='post' and path in {
                '/v1/avatar_videos','/v1/image_to_video','/v1/text_to_video','/v1/video_to_video',
                '/v1/text_to_image','/v1/image_upscale','/v1/video_upscale','/v1/video_to_hdr',
                '/v1/character_performance','/v1/sound_effect','/v1/speech_to_speech',
                '/v1/text_to_speech','/v1/voice_dubbing','/v1/voice_isolation',
                '/v1/generate/video','/v1/generate/image','/v1/generate/audio'}
            task=task or (method=='post' and path.startswith('/v1/recipes/'))
            workflow=method=='post' and path=='/v1/workflows/{id}'
            readonly=method=='get' or (method=='post' and path=='/v1/organization/usage')
            operations.append({'id':method+'_'+path.removeprefix('/v1/').replace('/','_').replace('{','').replace('}',''),
                'method':method.upper(),'path':path,'title':item.get('summary',path),
                'description':item.get('description','')[:400],'group':group(path),
                'parameters':compact(parameters),'body_schema':compact(schema),'body_template':example(schema) if schema else {},
                'task':task,'workflow':workflow,'paid':task or workflow or (method=='post' and path in {'/v1/realtime_sessions','/v1/voices/preview','/v1/voices'}),
                'mutation':not readonly,'docs':'https://docs.dev.runwayml.com/api/',
                'access_note':'Enterprise plan required' if '/organization/webapp/' in path else '',
                'verification':'Live output collected' if path=='/v1/avatar_videos' else
                    'Live task failed; diagnose before retry' if path=='/v1/character_performance' else 'Not individually live-tested'})
    return {'schema_version':1,'api_version':spec['info']['version'],
        'source_url':'https://github.com/runwayml/openapi/blob/main/openapi.json',
        'source_sha256':source_sha,'operations':operations}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True);parser.add_argument('--output',default='studio/runway_catalog.json')
    args=parser.parse_args();raw=Path(args.source).read_bytes()
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(build(json.loads(raw),hashlib.sha256(raw).hexdigest()),separators=(',',':'))+'\n')
    print(output)
