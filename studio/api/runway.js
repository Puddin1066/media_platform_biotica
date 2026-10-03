
async function queueByCommit(path,data){
  const url='https://api.github.com/repos/Puddin1066/media_platform_biotica/contents/'+path;
  const headers={Authorization:`Bearer ${process.env.GITHUB_TOKEN}`,Accept:'application/vnd.github+json','Content-Type':'application/json','User-Agent':'satoshi-studio'};
  const current=await fetch(url+'?ref=main',{headers});
  if(!current.ok)return current;
  const file=await current.json();
  return fetch(url,{method:'PUT',headers,body:JSON.stringify({branch:'main',sha:file.sha,message:'studio: queue Runway operation',content:Buffer.from(JSON.stringify(data,null,2)+'\n').toString('base64')})});
}
const catalog = require('../runway_catalog.json');
const operations=new Map(catalog.operations.map(op=>[op.id,op]));

// Reuse Studio's protected server-side GitHub dispatch channel. Runway secrets
// stay in Actions; the browser only sends a catalog operation and its inputs.
export default async function handler(req,res){
  if(req.method==='GET')return res.status(200).json({configured:Boolean(process.env.GITHUB_TOKEN),operation_count:operations.size});
  if(req.method!=='POST')return res.status(405).json({error:'Use GET or POST'});
  const request=req.body||{};
  if(request.operation==='qualify_aleph_act_two'){
    if(request.allow_media_spend!==true)return res.status(400).json({error:'Authorize the short qualification generation'});
    if(!process.env.GITHUB_TOKEN)return res.status(503).json({error:'Studio dispatch requires GITHUB_TOKEN'});
    const config=require('../runway_qualification_request.json');
    const response=await fetch('https://api.github.com/repos/Puddin1066/media_platform_biotica/actions/workflows/studio-runway-qualification.yml/dispatches',{
      method:'POST',headers:{Authorization:`Bearer ${process.env.GITHUB_TOKEN}`,Accept:'application/vnd.github+json','Content-Type':'application/json'},
      body:JSON.stringify({ref:'main',inputs:{request:JSON.stringify(config)}})});
    if(!response.ok){
      if(response.status!==403)return res.status(response.status).json({error:'Qualification dispatch failed'});
      const queued=await queueByCommit('studio/runway_qualification_request.json',{...config,dispatch_id:crypto.randomUUID()});
      if(!queued.ok)return res.status(queued.status).json({error:'Studio token needs Actions write or Contents write permission',detail:(await queued.text()).slice(0,1000)});
    }
    return res.status(202).json({status:'queued',url:'https://github.com/Puddin1066/media_platform_biotica/actions/workflows/studio-runway-qualification.yml'});
  }
  const op=operations.get(request.operation);
  if(!op||!/^[a-f0-9]{32}$/.test(request.request_id||''))return res.status(400).json({error:'Invalid operation or request ID'});
  if(op.mutation&&request.allow_mutation!==true)return res.status(400).json({error:'Authorize this provider operation'});
  if(op.paid&&(request.allow_media_spend!==true||!Number.isFinite(request.estimated_credits)||request.estimated_credits<=0))return res.status(400).json({error:'Enter a credit estimate and authorize generation'});
  const input=JSON.stringify(request);
  if(Buffer.byteLength(input)>48000)return res.status(400).json({error:'Request exceeds 48 KB; use media URLs rather than embedded files'});
  if(!process.env.GITHUB_TOKEN)return res.status(503).json({error:'Studio dispatch requires GITHUB_TOKEN'});
  const response=await fetch('https://api.github.com/repos/Puddin1066/media_platform_biotica/actions/workflows/studio-runway-tool.yml/dispatches',{
    method:'POST',headers:{Authorization:`Bearer ${process.env.GITHUB_TOKEN}`,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'},
    body:JSON.stringify({ref:'main',inputs:{request:input}})});
  if(!response.ok){
    if(response.status!==403)return res.status(response.status).json({error:'Runway tool dispatch failed',detail:(await response.text()).slice(0,1000)});
    const queued=await queueByCommit('studio/runway_tool_request.json',request);
    if(!queued.ok)return res.status(queued.status).json({error:'Studio token needs Actions write or Contents write permission',detail:(await queued.text()).slice(0,1000)});
  }
  return res.status(202).json({request_id:request.request_id,result_path:`studio/runway_jobs/${request.request_id}/result.json`});
}
