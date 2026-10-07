import React from 'react';
import {AbsoluteFill, Audio, Img, Sequence, staticFile} from 'remotion';
import {Video} from '@remotion/media';
import raw from '../public/library-first-fruit-ninja.json';
import {EvidenceCitationCard, ContradictionCard, ThesisCard} from './satoshiEditorialGraphics';

type Beat={id:string;from:number;duration:number;kind:'image'|'video'|'evidence'|'correction'|'thesis';asset?:string;sfx?:string;title?:string;text:string;citation?:string;data?:Record<string,string|number>};
type Pilot={fps:number;width:number;height:number;duration_frames:number;narration:string;background_bed?:string;beats:Beat[]};
const episode=raw as Pilot;
const FullAsset:React.FC<{beat:Beat}>=({beat})=>beat.asset?(beat.kind==='video'?<Video src={staticFile(beat.asset)} muted loop style={{width:'100%',height:'100%',objectFit:'cover'}}/>:<Img src={staticFile(beat.asset)} style={{width:'100%',height:'100%',objectFit:'cover'}}/>):null;

export const LibraryFirstFruitNinja:React.FC=()=>(
<AbsoluteFill style={{background:'#111622',fontFamily:'Arial, sans-serif'}}>
  {episode.background_bed&&<Audio src={staticFile(episode.background_bed)} volume={0.11} loop/>}
  <Audio src={staticFile(episode.narration)} volume={1}/>
  {episode.beats.map((beat)=>(
    <Sequence key={beat.id} from={beat.from} durationInFrames={beat.duration} layout="none" name={beat.id}>
      {(beat.kind==='image'||beat.kind==='video')&&<AbsoluteFill><FullAsset beat={beat}/></AbsoluteFill>}
      {beat.kind==='evidence'&&<AbsoluteFill style={{padding:70,justifyContent:'center'}}><EvidenceCitationCard study={String(beat.data?.study||'Peters et al.')} journal={String(beat.data?.journal||'Scientific Reports')} year={String(beat.data?.year||'2021')} n={String(beat.data?.n||'64')} finding={beat.text} citation={beat.citation}/></AbsoluteFill>}
      {beat.kind==='correction'&&<AbsoluteFill style={{padding:70,justifyContent:'center'}}><ContradictionCard heard={String(beat.data?.heard||'A video game treats dyslexia')} data={beat.text}/></AbsoluteFill>}
      {beat.kind==='thesis'&&<AbsoluteFill style={{padding:70,justifyContent:'center'}}><ThesisCard idea={beat.text} caveat="Interesting signal. Not a licensed treatment claim."/></AbsoluteFill>}
      {beat.sfx&&<Audio src={staticFile(beat.sfx)} volume={0.72}/>}
      {(beat.kind==='image'||beat.kind==='video')&&<>
        <div style={{position:'absolute',top:54,left:54,right:54,color:'#fff',fontSize:22,fontWeight:800,letterSpacing:1.2,textTransform:'uppercase',textShadow:'0 2px 8px #000'}}>{beat.title||'SATOSHI'}</div>
        <div style={{position:'absolute',left:54,right:54,bottom:120,padding:'18px 22px',borderRadius:14,background:'#111622d9',color:'#fff',fontSize:48,fontWeight:800,lineHeight:1.08,textAlign:'center',textShadow:'0 3px 8px #000'}}>{beat.text}</div>
      </>}
    </Sequence>
  ))}
</AbsoluteFill>
);