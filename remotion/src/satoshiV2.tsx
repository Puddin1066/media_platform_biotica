import React from 'react';
import {AbsoluteFill, Img, Sequence, staticFile} from 'remotion';
import {Audio, Video} from '@remotion/media';
import raw from '../public/satoshi-v2/render.json';

type Publication={title:string;journal?:string;year?:number;finding?:string;doi?:string};
type Visual={type?:string;screen_text?:string;publication?:Publication};
type Beat={id:string;text:string;kind:string;from:number;duration:number;host_src?:string;host_duration?:number;visual:Visual};
type Manifest={title:string;voice:string;scene:string;beats:Beat[];duration_frames:number;fps:number;width:number;height:number};
const m=raw as Manifest;

const PublicationCard:React.FC<{p:Publication}>=({p})=><AbsoluteFill style={{background:'#0d1117',alignItems:'center',justifyContent:'center'}}>
  <div style={{width:880,padding:56,boxSizing:'border-box',background:'#f4ead7',borderRadius:28,color:'#14191f'}}>
    <div style={{font:'800 26px Arial',color:'#7a2f30',marginBottom:18}}>{p.journal||'PRIMARY EVIDENCE'} {p.year?('· '+p.year):''}</div>
    <div style={{font:'800 50px Arial',lineHeight:1.06}}>{p.title}</div>
    {p.finding&&<div style={{marginTop:34,borderLeft:'8px solid #7a2f30',padding:'18px 22px',font:'800 30px Arial',lineHeight:1.15}}>{p.finding}</div>}
    {p.doi&&<div style={{marginTop:28,font:'600 18px Arial',color:'#606872'}}>DOI {p.doi}</div>}
  </div>
</AbsoluteFill>;

const BeatVisual:React.FC<{beat:Beat}>=({beat})=>{
  if(beat.kind==='host'&&beat.host_src) return <Sequence from={0} durationInFrames={beat.host_duration||beat.duration} layout="none"><Video src={staticFile(beat.host_src)} muted style={{width:'100%',height:'100%',objectFit:'cover'}}/></Sequence>;
  if(beat.visual?.type==='publication'&&beat.visual.publication) return <PublicationCard p={beat.visual.publication}/>;
  return <AbsoluteFill style={{background:'#111622',alignItems:'center',justifyContent:'center',padding:90,boxSizing:'border-box'}}>
    <div style={{font:'800 66px Arial',lineHeight:1.08,color:'#ffe19b',textAlign:'center',whiteSpace:'pre-line'}}>{beat.visual?.screen_text||beat.text}</div>
  </AbsoluteFill>;
};

export const SatoshiV2:React.FC=()=>(
  <AbsoluteFill style={{background:'#111622'}}>
    <Img src={staticFile(m.scene)} style={{position:'absolute',width:'100%',height:'100%',objectFit:'cover',opacity:.22}}/>
    <Audio src={staticFile(m.voice)} />
    {m.beats.map(b=><Sequence key={b.id} from={b.from} durationInFrames={b.duration} layout="none">
      <BeatVisual beat={b}/>
      <div style={{position:'absolute',left:70,right:70,bottom:140,padding:'16px 20px',borderRadius:14,
        background:'#0b0f16c9',color:'#fff',font:'800 50px Arial',lineHeight:1.12,textAlign:'center',
        textShadow:'0 3px 8px #000'}}>{b.text}</div>
    </Sequence>)}
  </AbsoluteFill>
);
