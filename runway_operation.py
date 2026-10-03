"""Execute one schema-validated Runway operation from the Studio catalog.

This is a reusable provider adapter, independent of episode orchestration.
Every mutation is durably reserved before submission. Ambiguous submissions
are never repeated automatically; existing task IDs can be polled instead.
Generated outputs are copied to R2 before their temporary provider URLs expire.
"""
import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
BASE='https://api.dev.runwayml.com'


def catalog():
    return json.loads((ROOT/'studio/runway_catalog.json').read_text())


def validate(request):
    """Use Runway's actual per-operation schema, including model variants."""
    from jsonschema import Draft202012Validator
    operations={op['id']:op for op in catalog()['operations']}
    if request.get('operation') not in operations: raise ValueError('Unknown Runway operation')
    op=operations[request['operation']]
    if not re.fullmatch(r'[a-f0-9]{32}',str(request.get('request_id',''))): raise ValueError('Invalid request ID')
    if op['mutation'] and request.get('allow_mutation') is not True: raise ValueError('Operation changes provider state; authorize this action')
    if op['paid'] and (request.get('allow_media_spend') is not True or not isinstance(request.get('estimated_credits'),(int,float)) or request['estimated_credits'] <= 0):
        raise ValueError('Generation requires spend authorization and a positive credit estimate')
    for location in ['path','query']:
        values=request.get('path_params' if location=='path' else 'query',{})
        if not isinstance(values,dict): raise ValueError('Parameters must be objects')
        definitions={p['name']:p for p in op['parameters'] if p['in']==location}
        if set(values)-set(definitions): raise ValueError('Unknown '+location+' parameter')
        for name,p in definitions.items():
            if p.get('required') and name not in values: raise ValueError('Missing '+location+' parameter: '+name)
            if name in values: Draft202012Validator(p['schema']).validate(values[name])
    body=request.get('body',{})
    if op['body_schema']:
        Draft202012Validator(op['body_schema']).validate(body)
    elif body: raise ValueError('This operation has no JSON body')
    return op


def api(method,path,body=None,query=None):
    """Fixed provider origin and headers; no arbitrary URL or credential inputs."""
    secret=os.environ.get('RUNWAYML_API_SECRET')
    if not secret: raise ValueError('RUNWAYML_API_SECRET is missing')
    url=BASE+path
    if query: url+='?'+urllib.parse.urlencode({k:str(v).lower() if isinstance(v,bool) else v for k,v in query.items()},doseq=True)
    req=urllib.request.Request(url,method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+secret,'X-Runway-Version':catalog()['api_version'],
                 'Content-Type':'application/json','User-Agent':'satoshi-studio/1'})
    with urllib.request.urlopen(req,timeout=120) as response:
        raw=response.read()
        return json.loads(raw) if raw else {}


def git_checkpoint():
    """The worker serializes Studio state writes; persist before paid requests."""
    import subprocess
    if os.environ.get('STUDIO_GIT_CHECKPOINT')!='true': return
    subprocess.run(['git','add','studio/runway_jobs'],cwd=ROOT,check=True)
    if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:
        subprocess.run(['git','commit','-m','studio: checkpoint Runway operation'],cwd=ROOT,check=True)
        # A rejected push blocks submission rather than risking an unrecorded bill.
        subprocess.run(['git','push','origin','HEAD:main'],cwd=ROOT,check=True)


def archive_outputs(response,job_id,work):
    """Task outputs are generated media; request/reference URLs are not copied."""
    import media_store
    urls=response.get('output',[])
    if isinstance(urls,dict): urls=[url for items in urls.values() if isinstance(items,list) for url in items]
    if not isinstance(urls,list): return []
    media=[]
    for i,url in enumerate(urls):
        if not isinstance(url,str) or urllib.parse.urlsplit(url).scheme!='https': continue
        suffix=Path(urllib.parse.urlsplit(url).path).suffix or '.bin'
        target=work/(str(i)+suffix)
        with urllib.request.urlopen(url,timeout=180) as source,target.open('wb') as dest:
            import shutil
            shutil.copyfileobj(source,dest)
        media.append(media_store.persist(target,'satoshi-studio/runway-tools/'+job_id+'/'+target.name))
    return media


def execute(request,call=api,checkpoint=git_checkpoint,pause=time.sleep,archive=archive_outputs,
            job_root=None,work_root=None):
    op=validate(request)
    # Episode workers can keep journals inside their existing artifact/library
    # tree without changing a global path or the standalone tool worker.
    job=Path(job_root or ROOT/'studio/runway_jobs')/request['request_id']
    job.mkdir(parents=True,exist_ok=True)
    state_path=job/'result.json'
    def save(state):
        state_path.write_text(json.dumps(state,indent=2)+'\n');checkpoint()
    # The full input is preserved once so an ID cannot be reused with a new prompt.
    input_path=job/'request.json'
    if input_path.exists() and json.loads(input_path.read_text())!=request:
        raise ValueError('Request ID already belongs to different inputs')
    input_path.write_text(json.dumps(request,indent=2)+'\n')
    state=json.loads(state_path.read_text()) if state_path.exists() else None
    if state and state['state']=='completed': return state
    if state and state['state'] in {'reserved_unknown','failed','rejected'}:
        raise ValueError('Saved operation is '+state['state']+'; inspect it before an explicit new request')
    if not state:
        if op['paid']:
            account=call('GET','/v1/organization')
            balance=account.get('creditBalance')
            if not isinstance(balance,(int,float)): raise ValueError('Provider did not return a numeric credit balance')
            if balance<request['estimated_credits']: raise ValueError('Insufficient API credits for the entered estimate')
        state={'state':'reserved_unknown','operation':op['id'],'media':[],
               'estimated_credits':request.get('estimated_credits'),
               'credit_estimate_note':'Preflight estimate, not a provider-enforced spending cap'}
        save(state)
        path=op['path']
        for name,value in request.get('path_params',{}).items(): path=path.replace('{'+name+'}',urllib.parse.quote(str(value),safe=''))
        try:
            response=call(op['method'],path,request.get('body') if op['body_schema'] else None,request.get('query'))
        except urllib.error.HTTPError as error:
            state.update(state='rejected',http_status=error.code,provider_error=error.read().decode(errors='replace')[:4000]);save(state);raise
        # Connection loss leaves the reservation intact: the provider may have billed.
        if op['path']=='/v1/uploads':
            # Temporary upload form signatures are usable credentials. Keep the
            # raw response only in the private Actions artifact, never public git.
            private=Path(work_root or ROOT/'outputs/runway-tools')/request['request_id'];private.mkdir(parents=True,exist_ok=True)
            (private/'upload-session.json').write_text(json.dumps(response))
            response={**response,'uploadUrl':'[private Actions artifact]','fields':{'redacted':'private Actions artifact'}}
        state['response']=response
        state['state']='submitted' if (op['task'] or op['workflow']) and response.get('id') else 'completed'
        if op['path']=='/v1/voices/preview' and response.get('url'):
            state['state']='generated';state['provider_detail']={'output':[response['url']]}
        save(state)
    if state['state']=='submitted':
        identifier=state['response']['id']
        poll_path='/v1/workflow_invocations/' if op['workflow'] else '/v1/tasks/'
        deadline=time.monotonic()+1800
        while True:
            response=call('GET',poll_path+urllib.parse.quote(identifier,safe=''))
            status=str(response.get('status','')).upper()
            state['provider_detail']=response
            if status in {'FAILED','CANCELED','CANCELLED'}:
                state['state']='failed';save(state)
                raise RuntimeError('Runway generation failed; provider details saved in result.json')
            if status in {'SUCCEEDED','COMPLETED'}:
                state['state']='generated';save(state);break
            if time.monotonic()>=deadline:
                save(state);raise TimeoutError('Generation is still submitted; resume this same request ID')
            pause(10)
    if state['state']=='generated':
        work=Path(work_root or ROOT/'outputs/runway-tools')/request['request_id'];work.mkdir(parents=True,exist_ok=True)
        state['media']=archive(state['provider_detail'],request['request_id'],work)
        state['state']='completed';save(state)
    return state

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--request',required=True)
    args=parser.parse_args()
    request=json.loads(Path(args.request).read_text())
    try:
        result=execute(request);print(json.dumps({'state':result['state'],'media':result['media']}))
    except Exception as error:
        # Validation and balance failures also need a visible Studio result.
        identifier=str(request.get('request_id',''))
        if re.fullmatch(r'[a-f0-9]{32}',identifier):
            job=ROOT/'studio/runway_jobs'/identifier;job.mkdir(parents=True,exist_ok=True)
            result_path=job/'result.json'
            if not result_path.exists():
                (job/'request.json').write_text(json.dumps(request,indent=2)+'\n')
                result_path.write_text(json.dumps({'state':'rejected','error':str(error),'media':[]},indent=2)+'\n')
        git_checkpoint();raise
