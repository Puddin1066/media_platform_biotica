// Save production settings and invalidate only their dependent Studio modules.
// This endpoint creates no Runway task and does not authorize publishing.
const API='https://api.github.com/repos/Puddin1066/media_platform_biotica';
async function github(path, options={}){
  const response=await fetch(API+path,{...options,headers:{Authorization:`Bearer ${process.env.GITHUB_TOKEN}`,Accept:'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'}});
  if(!response.ok)throw new Error(`GitHub ${response.status}: ${(await response.text()).slice(0,300)}`);
  return response.json();
}
export default async function handler(req,res){
  if(req.method!=='POST')return res.status(405).json({error:'Use POST'});
  if(!process.env.GITHUB_TOKEN)return res.status(503).json({error:'Studio GitHub token is missing'});
  const input=req.body||{},episode=String(input.episode||'');
  const numeric=(value,min,max)=>typeof value==='number'&&Number.isFinite(value)&&value>=min&&value<=max;
  if(!/^[a-z0-9][a-z0-9-]{2,120}$/.test(episode)||typeof input.prompt!=='string'||!input.prompt.trim()||input.prompt.length>1000||typeof input.r2_key!=='string'||!input.r2_key.trim()||input.r2_key.split('/').includes('..')||!numeric(input.plate_seconds,2,30)||!numeric(input.performance_max_seconds,3,30)||!Number.isInteger(input.expression_intensity)||!numeric(input.expression_intensity,1,5)||!Number.isInteger(input.max_overlay_images)||!numeric(input.max_overlay_images,1,120)){
    return res.status(400).json({error:'Enter a plate key, lab prompt, valid durations, expression intensity and image limit'});
  }
  try{
    const ref=await github('/git/ref/heads/main'),parent=await github('/git/commits/'+ref.object.sha);
    const root='studio/episodes/'+episode;
    const treeInfo=await github('/git/trees/'+parent.tree.sha+'?recursive=1');
    async function read(path){
      const entry=treeInfo.tree.find(item=>item.path===path);
      if(!entry)throw new Error('Episode settings not found');
      const blob=await github('/git/blobs/'+entry.sha);
      return JSON.parse(Buffer.from(blob.content,'base64').toString('utf8'));
    }
    const request=await read(root+'/request.json'),manifest=await read(root+'/episode_manifest.json');
    if(request.format?.id==='opportunity_brief')return res.status(400).json({error:'These controls are for Satoshi Reels'});
    request.host={...request.host,mode:'aleph_act_two',r2_key:input.r2_key.trim(),aleph:{prompt:input.prompt.trim(),seconds:input.plate_seconds},performance_max_seconds:input.performance_max_seconds,expression_intensity:input.expression_intensity};
    request.production={...request.production,max_overlay_images:input.max_overlay_images};
    for(const name of ['visual_plan','assets','host','assembly','publish']){
      const state=manifest.modules[name];
      if(state)state.status=state.version>0?'stale':'not_ready';
    }
    // The next manual module run uses the existing dependency checks and review gates.
    const tree=await github('/git/trees',{method:'POST',body:JSON.stringify({base_tree:parent.tree.sha,tree:[{path:root+'/request.json',mode:'100644',type:'blob',content:JSON.stringify(request,null,2)+'\n'},{path:root+'/episode_manifest.json',mode:'100644',type:'blob',content:JSON.stringify(manifest,null,2)+'\n'}]})});
    const commit=await github('/git/commits',{method:'POST',body:JSON.stringify({message:'studio: configure Aleph, Act Two and rich overlays',tree:tree.sha,parents:[ref.object.sha]})});
    await github('/git/refs/heads/main',{method:'PATCH',body:JSON.stringify({sha:commit.sha,force:false})});
    return res.status(200).json({saved:true,commit:commit.sha});
  }catch(error){return res.status(502).json({error:'Could not save host settings. The Studio GitHub token needs Contents write permission.',detail:error.message});}
}
