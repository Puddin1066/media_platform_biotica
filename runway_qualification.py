"""Short, resumable Aleph -> Act Two qualification from Studio-owned media."""
import argparse, hashlib, json, subprocess, urllib.request, urllib.parse
from pathlib import Path
import media_store
from runway_operation import execute, api

def clip(source, target, seconds=4):
    subprocess.run(['ffmpeg','-y','-i',str(source),'-t',str(seconds),'-vf','fps=24','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(target)],check=True,capture_output=True)
    data=json.loads(subprocess.check_output(['ffprobe','-v','quiet','-show_streams','-show_format','-of','json',str(target)]))
    video=next(x for x in data['streams'] if x['codec_type']=='video')
    if not 3 <= float(data['format']['duration']) <= 4.1 or video['width']<256 or video['height']<256:
        raise ValueError('Invalid qualification clip')
    return media_store.persist(target,'satoshi-studio/qualification/'+hashlib.sha256(target.read_bytes()).hexdigest()+'/'+target.name)

def run(config):
    if config.get('allow_media_spend') is not True: raise ValueError('Explicit spend authorization required')
    work=Path('outputs/runway-qualification');work.mkdir(parents=True,exist_ok=True)
    inputs={}
    for name in ('character','driver'):
        source=work/(name+'-source.mp4')
        # Only the existing Studio public media origin is accepted.
        url=config[name+'_url']
        if not url.startswith(media_store.public_base_url()+'/'): raise ValueError('Use Studio media inputs')
        key=urllib.parse.unquote(url[len(media_store.public_base_url())+1:])
        media_store.fetch(key, source)
        inputs[name]=clip(source,work/(name+'.mp4'))
    token=config['revision']
    def request(kind,body,credits):
        identifier=hashlib.sha256((token+kind+json.dumps(body,sort_keys=True)).encode()).hexdigest()[:32]
        return execute({'request_id':identifier,'operation':kind,'body':body,'allow_mutation':True,'allow_media_spend':True,'estimated_credits':credits})
    results={}
    errors={}
    # Independent qualification: a failed Aleph request must not hide Act Two results.
    try:
        results['aleph']=request('post_video_to_video',{'model':'aleph2','videoUri':inputs['character']['url'],'promptText':config['aleph_prompt'],'outputFormat':'mp4','targetAspectRatio':'9:16'},112)
    except Exception as error: errors['aleph']=str(error)
    character=inputs['character']['url']
    if results.get('aleph',{}).get('media'): character=results['aleph']['media'][0]['url']
    try:
        results['act_two']=request('post_character_performance',{'model':'act_two','character':{'type':'video','uri':character},'reference':{'type':'video','uri':inputs['driver']['url']},'ratio':'720:1280','expressionIntensity':3},20)
    except Exception as error: errors['act_two']=str(error)
    report={'inputs':inputs,'results':results,'errors':errors,'visual_review':'required'}
    (work/'report.json').write_text(json.dumps(report,indent=2))
    if errors: raise RuntimeError(json.dumps(errors))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True)
    run(json.loads(Path(parser.parse_args().config).read_text()))
