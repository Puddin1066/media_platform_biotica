import React, {useMemo} from 'react';
import {AbsoluteFill, Composition, Img, interpolate, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {Audio, Video} from '@remotion/media';
import type {Caption} from '@remotion/captions';
import rawEpisode from '../public/episode.json';
import rawCanonicalEpisode from '../public/canonical-episode.json';
import rawDirectEpisode from '../public/direct-episode.json';
import rawLibraryFirstPilot from '../public/library-first-pilot.json';
import {LibraryFirstPilot} from './libraryFirstPilot';
import rawLibraryFirstFruitNinja from '../public/library-first-fruit-ninja.json';
import {LibraryFirstFruitNinja} from './libraryFirstFruitNinja';

type Shot = {src: string; from: number; duration: number; credit: string;
  cue_id: string | null; claim_ids: string[]; playback_rate?: number;
  visual_type?: 'source' | 'illustration'};
type Episode = {plate: string; plate_start_frames: number; loop_plate: boolean;
  voice: string | null; shots: Shot[]; captions: Caption[]; duration_frames: number;
  fps: number; width: number; height: number; headline?: string; fixture?: boolean};
const episode = rawEpisode as Episode;
// The pinned captions package predates pageBreakAfter; keep this optional
// metadata local without upgrading unrelated Remotion dependencies.
type TimedCaption = Caption & {pageBreakAfter?: boolean};

type CanonicalBeat = {
  beat_id: string;
  role: string;
  text: string;
  citations: string[];
  still: string;
  motion: 'hold' | 'flip' | 'push' | 'crossfade' | 'slow_zoom' | 'pause';
  from: number;
  duration: number;
  visual_type?: string;
  screen_text?: string;
  source_label?: string;
  inset_video?: string;
  playback_rate?: number;
  publication?: {
    id: string;
    title: string;
    journal: string;
    year: number;
    doi?: string;
    source_url?: string;
    finding: string;
    authors: {name: string; role?: string; institution?: string}[];
    institutions: string[];
  };
  chart?: {source_url: string; units?: string; points: {label: string; value: number}[]};
};
type CanonicalHostSegment = {
  segment_id: string;
  role: string;
  src: string;
  from: number;
  duration: number;
  realism?: {
    scale_start?: number;
    scale_end?: number;
    x_start?: number;
    x_end?: number;
    y_start?: number;
    y_end?: number;
  };
};
type CanonicalEpisode = {
  title: string;
  format?: string;
  company?: string;
  host: string;
  host_segments?: CanonicalHostSegment[];
  voice?: string;
  loop_host?: boolean;
  cutaway_from_frame?: number | null;
  captions?: TimedCaption[];
  beats: CanonicalBeat[];
  duration_frames: number;
  fps: number;
  width: number;
  height: number;
};
const canonicalEpisode = rawCanonicalEpisode as CanonicalEpisode;
const directEpisode = rawDirectEpisode as unknown as CanonicalEpisode;
const libraryFirstPilot = rawLibraryFirstPilot as {duration_frames:number;fps:number;width:number;height:number};
const libraryFirstFruitNinja = rawLibraryFirstFruitNinja as {duration_frames:number;fps:number;width:number;height:number};

const SatoshiReel: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: '#111622'}}>
    {episode.plate && <Video src={staticFile(episode.plate)}
      trimBefore={episode.plate_start_frames} loop={episode.loop_plate}
      muted={Boolean(episode.voice)} objectFit="cover"
      style={{width: '100%', height: '100%'}} />}
    {episode.voice && <Audio src={staticFile(episode.voice)} volume={1} />}
    {episode.shots.map((shot) => (
      <Sequence key={shot.src} from={shot.from} durationInFrames={shot.duration}
        name={shot.cue_id || `Inset ${shot.from}`} layout="none">
        <div style={{position: 'absolute', top: 230, left: 46, width: 540,
          padding: 8, background: '#f1e7d4', borderRadius: 12,
          boxShadow: '0 12px 28px #000a'}}>
          <Video src={staticFile(shot.src)} muted loop objectFit="contain"
            playbackRate={shot.playback_rate || 1}
            style={{width: 540, height: 304, background: '#101522'}} />
          {shot.visual_type === 'illustration' &&
            <div style={{position: 'absolute', top: 17, left: 17, padding: '5px 8px',
              background: '#1b222be0', color: '#fff', font: 'bold 16px Arial'}}>
              ILLUSTRATION
            </div>}
          <div style={{fontFamily: 'Arial, sans-serif', fontSize: 18,
            padding: '6px 10px', color: '#181c25', whiteSpace: 'nowrap',
            overflow: 'hidden', textOverflow: 'ellipsis'}}>{shot.credit}</div>
        </div>
      </Sequence>
    ))}
    {episode.headline && <div style={{position: 'absolute', top: 1320, left: 64,
      width: 952, minHeight: 100, display: 'flex', alignItems: 'center',
      justifyContent: 'center', boxSizing: 'border-box', padding: '16px 24px',
      background: '#f6f2e9', borderBottom: '6px solid #ad3334',
      boxShadow: '0 10px 25px #0008', textAlign: 'center',
      color: '#1b222b', font: 'bold 43px Arial, sans-serif',
      lineHeight: 1.12, overflowWrap: 'anywhere'}}>{episode.headline}</div>}
    {episode.captions.map((caption, index) => {
      const start = Math.round(caption.startMs * episode.fps / 1000);
      const end = Math.round(caption.endMs * episode.fps / 1000);
      return <Sequence key={index} from={start} durationInFrames={Math.max(1, end - start)}
        layout="none" name={`Caption ${index + 1}`}>
        <div style={{position: 'absolute', top: 1510, left: 90, width: 900,
          textAlign: 'center', fontFamily: 'Arial, sans-serif', fontWeight: 800,
          color: '#ffffff', fontSize: 55, lineHeight: 1.14,
          textShadow: '0 3px 12px #000, 0 3px 4px #000'}}>{caption.text}</div>
      </Sequence>;
    })}
    {episode.fixture && <div style={{position: 'absolute', top: 120, left: 50,
      padding: 20, background: '#9b2226', color: '#fff', font: 'bold 46px Arial'}}>
      SYNTHETIC PIPELINE TEST
    </div>}
  </AbsoluteFill>
);

const citationDomain = (citation?: string) => {
  if (!citation) return null;
  try {
    return new URL(citation).hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
};


const PublicationEvidence: React.FC<{beat: CanonicalBeat}> = ({beat}) => {
  const pub = beat.publication;
  if (!pub) return null;
  const authors = pub.authors.slice(0, 3);
  const institutions = pub.institutions.slice(0, 5);
  return <AbsoluteFill style={{backgroundColor:'#0d1117', alignItems:'center', justifyContent:'center'}}>
    <div style={{position:'relative', width:900, minHeight:1320, boxSizing:'border-box',
      background:'#f7f3e8', borderRadius:30, padding:'54px 56px 44px',
      boxShadow:'0 28px 80px #000b', color:'#14191f'}}>
      <div style={{font:'800 26px Arial', letterSpacing:2.1, textTransform:'uppercase',
        color:'#7a2f30', marginBottom:18}}>{pub.journal} · {pub.year}</div>

      <div style={{font:'800 48px Arial', lineHeight:1.06, marginBottom:24}}>
        {pub.title}
      </div>

      <div style={{height:2, background:'#c9bda7', margin:'10px 0 28px'}} />

      <div style={{font:'800 22px Arial', letterSpacing:1.5, color:'#5d6670',
        textTransform:'uppercase', marginBottom:14}}>People behind the evidence</div>

      <div style={{display:'flex', gap:14, flexWrap:'wrap', marginBottom:28}}>
        {authors.map((a) => <div key={a.name} style={{flex:'1 1 235px', minWidth:220,
          border:'2px solid #d7cab2', borderRadius:18, padding:'16px 18px', background:'#fffdf8'}}>
          <div style={{font:'800 28px Arial', lineHeight:1.04}}>{a.name}</div>
          {a.role && <div style={{font:'700 17px Arial', color:'#7a2f30', marginTop:6,
            textTransform:'uppercase'}}>{a.role}</div>}
          {a.institution && <div style={{font:'600 19px Arial', color:'#4c5660',
            marginTop:8, lineHeight:1.16}}>{a.institution}</div>}
        </div>)}
      </div>

      <div style={{font:'800 22px Arial', letterSpacing:1.5, color:'#5d6670',
        textTransform:'uppercase', marginBottom:13}}>Institution network</div>
      <div style={{display:'flex', gap:10, flexWrap:'wrap', marginBottom:30}}>
        {institutions.map((name) => <div key={name} style={{
          padding:'10px 14px', borderRadius:999, background:'#18222d', color:'#f7f3e8',
          font:'700 18px Arial'}}>{name}</div>)}
      </div>

      <div style={{borderLeft:'8px solid #7a2f30', padding:'16px 20px',
        background:'#eee5d4', borderRadius:12, marginTop:4}}>
        <div style={{font:'800 20px Arial', color:'#7a2f30', textTransform:'uppercase',
          letterSpacing:1.2, marginBottom:8}}>What this paper found</div>
        <div style={{font:'800 30px Arial', lineHeight:1.15}}>{pub.finding}</div>
      </div>

      <div style={{position:'absolute', left:56, right:56, bottom:28,
        display:'flex', justifyContent:'space-between', alignItems:'flex-end', gap:20}}>
        <div style={{font:'700 18px Arial', color:'#5b646e'}}>
          {pub.authors[0]?.name}{pub.authors.length > 1 ? ' et al.' : ''} · {pub.journal} · {pub.year}
        </div>
        {pub.doi && <div style={{font:'600 16px Arial', color:'#7b838b'}}>DOI {pub.doi}</div>}
      </div>
    </div>
  </AbsoluteFill>;
};

const EvidenceOverlay: React.FC<{beat: CanonicalBeat; brief?: boolean; cutawayFrom?: number | null}> = ({beat, brief = false, cutawayFrom}) => {

  if (!brief && (beat.still || beat.visual_type === 'typography')) {
    return <AbsoluteFill style={{backgroundColor:'#0d1117', alignItems:'center', justifyContent:'center'}}>
      {beat.still ? <div style={{width:900, height:1180, borderRadius:28, overflow:'hidden',
        background:'#161d27', boxShadow:'0 28px 80px #000b', position:'relative'}}>
        <Img src={staticFile(beat.still)} style={{width:'100%',height:'100%',objectFit:'cover'}} />
        <div style={{position:'absolute',inset:0,background:'linear-gradient(180deg,transparent 55%,#0d1117ee 100%)'}} />
        {beat.source_label && <div style={{position:'absolute',left:34,right:34,bottom:118,
          color:'#d4dbe2',font:'700 20px Arial',letterSpacing:.4}}>{beat.source_label}</div>}
        {beat.screen_text && <div style={{position:'absolute',left:34,right:34,bottom:34,
          color:'#fff',font:'800 42px Arial',lineHeight:1.08}}>{beat.screen_text}</div>}
      </div> :
      <div style={{width:880,minHeight:540,borderRadius:28,padding:'74px 68px',
        boxSizing:'border-box',background:'#f4ead7',boxShadow:'0 28px 80px #000b',
        display:'flex',flexDirection:'column',justifyContent:'center',textAlign:'left'}}>
        <div style={{color:'#7a2f30',font:'800 22px Arial',letterSpacing:1.8,
          textTransform:'uppercase',marginBottom:22}}>{beat.source_label || 'SATOSHI / FIELD NOTE'}</div>
        <div style={{color:'#14191f',font:'800 62px Arial',lineHeight:1.06}}>{beat.screen_text}</div>
      </div>}
    </AbsoluteFill>;
  }

  const frame = useCurrentFrame();
  const cutaway = cutawayFrom != null && frame + beat.from >= cutawayFrom;
  if (beat.visual_type === 'host') return null;
  if (beat.visual_type === 'publication') return <PublicationEvidence beat={beat} />;
  const enter = interpolate(frame, [0, Math.min(8, beat.duration - 1)], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const zoom = beat.motion === 'slow_zoom'
    ? interpolate(frame, [0, Math.max(1, beat.duration - 1)], [1, 1.08], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    }) : 1;
  const translateX = beat.motion === 'push' ? (1 - enter) * 90 : 0;
  const opacity = beat.motion === 'crossfade' ? enter : 1;
  const source = citationDomain(beat.citations[0]);
  return <div style={{position: 'absolute', top: brief ? 215 : cutaway ? 220 : 760, right: brief ? 75 : cutaway ? 100 : 42, width: brief ? 575 : cutaway ? 860 : 460,
    transform: `translateX(${translateX}px) scale(${zoom})`, opacity,
    transformOrigin: 'center center', padding: 9, background: '#f4ead7',
    borderRadius: 16, boxShadow: '0 14px 36px #000b'}}>
    <div style={{position: 'relative', width: brief ? 575 : cutaway ? 860 : 460, height: brief ? 355 : cutaway ? 860 : 460, overflow: 'hidden',
      borderRadius: 10, background: '#111722'}}>
      {beat.inset_video ? <Video src={staticFile(beat.inset_video)} muted loop
        playbackRate={beat.playback_rate || 1} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        : beat.still ? <Img src={staticFile(beat.still)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        : beat.chart ? <div style={{padding: '45px 24px 15px', color: '#fff', font: '20px Arial'}}>
          {beat.chart.points.slice(0, 5).map((point) => <div key={point.label} style={{marginBottom: 16}}>
            <div>{point.label}: {point.value} {beat.chart?.units}</div>
            <div style={{height: 14, marginTop: 4, background: '#ffe19b', width:
              `${100 * point.value / Math.max(1, ...beat.chart!.points.map(p => p.value))}%`}} />
          </div>)}
        </div> : <div style={{padding: '68px 30px', color: '#ffe19b', font: `800 ${cutaway ? 72 : 40}px Arial`, lineHeight: 1.15}}>
          {beat.screen_text}
        </div>}
      <div style={{position: 'absolute', top: 12, left: 12, padding: '6px 9px',
        background: '#151b24e8', color: '#fff', font: `700 ${cutaway ? 24 : 15}px Arial, sans-serif`,
        letterSpacing: 0.5}}>{beat.visual_type === 'source' ? 'SOURCE FOOTAGE'
          : beat.visual_type === 'chart' ? 'DATA' : beat.visual_type === 'typography' ? 'COMMENTARY' : 'AI ILLUSTRATION'}</div>
    </div>
    <div style={{padding: '8px 11px 2px', color: '#202630',
      font: `700 ${cutaway ? 28 : 17}px Arial, sans-serif`, textTransform: 'uppercase'}}>
      {beat.visual_type === 'source' ? 'EVIDENCE' : beat.visual_type === 'chart' ? 'RESEARCH' : beat.source_label ? 'SCIENCE / CONTEXT' : 'SATOSHI / FIELD NOTES'}
    </div>
    <div style={{padding: '0 11px 7px', color: '#4a5360',
      font: `600 ${cutaway ? 26 : 14}px Arial, sans-serif`, whiteSpace: 'nowrap', overflow: 'hidden',
      textOverflow: 'ellipsis'}}>
      {beat.source_label || (source ? `SOURCE: ${source}` : 'EDITORIAL / RHETORICAL BEAT')}
    </div>
    {beat.screen_text && beat.visual_type !== 'typography' && <div style={{padding: '12px 14px',
      borderTop: '2px solid #ad3334', color: '#161d27', font: `800 ${cutaway ? 48 : 28}px Arial`, lineHeight: 1.15}}>
      {beat.screen_text}
    </div>}
  </div>;
};

// Each short page holds at most five measured words. Frame-based highlighting
// follows the locked voice master, including pauses; no CSS animation timers.
const MeasuredCaptions: React.FC<{captions: TimedCaption[]; fps: number; brief?: boolean}> = ({captions, fps, brief = false}) => {
  const frame = useCurrentFrame();
  const milliseconds = frame * 1000 / fps;
  const pages = useMemo(() => {
  const grouped: TimedCaption[][] = [];
  let page: TimedCaption[] = [];
  for (const word of captions) {
    page.push(word);
    if (word.pageBreakAfter || page.length === 5) {grouped.push(page); page = [];}
  }
  if (page.length) grouped.push(page);
  return grouped;
  }, [captions]);
  const active = pages.find(words => milliseconds >= words[0].startMs && milliseconds < words[words.length - 1].endMs);
  if (!active) return null;
  return <div style={{position: 'absolute', left: brief ? 85 : 80, bottom: brief ? 245 : 300,
    width: brief ? 1080 : 880, textAlign: brief ? 'left' : 'center',
    color: '#fff', font: '800 58px Arial', lineHeight: 1.15, textShadow: '0 3px 8px #000',
    background: '#111622b8', borderRadius: 16, padding: '14px 20px', boxSizing: 'border-box'}}>
    {active.map((word, index) => <span key={index} style={{color:
      milliseconds >= word.startMs && milliseconds < word.endMs ? '#ffe19b' : '#fff'}}>{word.text}</span>)}
  </div>;
};


const RealisticHostSegment: React.FC<{segment: CanonicalHostSegment}> = ({segment}) => {
  const frame = useCurrentFrame();
  const last = Math.max(1, segment.duration - 1);
  const realism = segment.realism || {};
  const scale = interpolate(frame, [0, last],
    [realism.scale_start ?? 1.0, realism.scale_end ?? 1.018],
    {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  const x = interpolate(frame, [0, last],
    [realism.x_start ?? 0, realism.x_end ?? 8],
    {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  const y = interpolate(frame, [0, last],
    [realism.y_start ?? 0, realism.y_end ?? -4],
    {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  return <Video src={staticFile(segment.src)} muted
    style={{position:'absolute', inset:0, width:'100%', height:'100%',
      objectFit:'cover', transform:`translate(${x}px,${y}px) scale(${scale})`,
      transformOrigin:'center center'}} />;
};

const CanonicalSatoshiEpisode: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: '#111622'}}>
    {canonicalEpisode.host && <Sequence from={0} durationInFrames={canonicalEpisode.cutaway_from_frame ?? canonicalEpisode.duration_frames} layout="none">
      <Video src={staticFile(canonicalEpisode.host)} loop={Boolean(canonicalEpisode.loop_host)} muted={Boolean(canonicalEpisode.voice)} objectFit="cover"
        style={{width: '100%', height: '100%'}} />
    </Sequence>}
    {canonicalEpisode.voice && <Audio src={staticFile(canonicalEpisode.voice)} volume={1} />}
    {canonicalEpisode.format === 'opportunity_brief' && <div style={{
      position: 'absolute', top: 74, left: 88, width: 1650,
      color: '#fff', font: '700 30px Arial', letterSpacing: 1,
    }}>OPPORTUNITY BRIEF <span style={{color: '#ffe19b'}}>· {canonicalEpisode.company}</span>
      <div style={{font: '800 54px Arial', marginTop: 20, maxWidth: 1600}}>{canonicalEpisode.title}</div>
    </div>}
    {canonicalEpisode.beats.map((beat) => (
      <Sequence key={beat.beat_id} from={beat.from} durationInFrames={beat.duration}
        layout="none" name={`${beat.beat_id} ${beat.role}`}>
        <EvidenceOverlay beat={beat} brief={canonicalEpisode.format === 'opportunity_brief'} cutawayFrom={canonicalEpisode.cutaway_from_frame} />
        {!canonicalEpisode.captions?.length && <div style={{position: 'absolute', left: 64, bottom: 115, width: 952,
          textAlign: 'center', color: '#fff', font: '800 51px Arial, sans-serif',
          lineHeight: 1.12, textShadow: '0 4px 14px #000, 0 2px 5px #000',
          padding: '12px 18px', boxSizing: 'border-box'}}>{beat.text}</div>}
      </Sequence>
    ))}
    {canonicalEpisode.host_segments?.map((segment) => (
      <Sequence key={segment.segment_id} from={segment.from} durationInFrames={segment.duration}
        layout="none" name={`${segment.segment_id} ${segment.role}`}>
        <RealisticHostSegment segment={segment} />
        <div style={{position:'absolute', top:48, left:48, padding:'8px 12px',
          borderRadius:8, background:'#111622cc', color:'#fff',
          font:'700 20px Arial', letterSpacing:0.7}}>SATOSHI</div>
      </Sequence>
    ))}
    {canonicalEpisode.captions?.length ? <MeasuredCaptions captions={canonicalEpisode.captions} fps={canonicalEpisode.fps}
      brief={canonicalEpisode.format === 'opportunity_brief'} /> : null}
  </AbsoluteFill>
);


const DirectTetrisEpisode: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: '#111622'}}>
    {directEpisode.host && <Video src={staticFile(directEpisode.host)}
      muted={Boolean(directEpisode.voice)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />}
    {directEpisode.voice && <Audio src={staticFile(directEpisode.voice)} volume={1} />}
    {directEpisode.beats.map((beat) => {
      const source = citationDomain(beat.citations?.[0]);
      const isHost = beat.visual_type === 'host';
      return <Sequence key={beat.beat_id} from={beat.from} durationInFrames={beat.duration}
        layout="none" name={`${beat.beat_id} ${beat.role}`}>
        {!isHost && <div style={{position: 'absolute', inset: 0}}>
          {beat.inset_video ? <Video src={staticFile(beat.inset_video)} muted loop
            playbackRate={beat.playback_rate || 1}
            style={{width: '100%', height: '100%', objectFit: 'cover'}} />
            : beat.still ? <Img src={staticFile(beat.still)}
              style={{width: '100%', height: '100%', objectFit: 'cover'}} />
            : <div style={{position: 'absolute', inset: 0, display: 'flex',
              alignItems: 'center', justifyContent: 'center', padding: '110px',
              textAlign: 'center', color: '#ffe19b', font: '800 70px Arial',
              lineHeight: 1.08, background: '#111622'}}>
                <div>{beat.screen_text}
                  <div style={{marginTop: 40, color: '#fff', font: '700 28px Arial', lineHeight: 1.3}}>
                    {beat.source_label || (source ? `SOURCE: ${source}` : '')}
                  </div>
                  {source && <div style={{marginTop: 12, color: '#9fb3c8', font: '600 22px Arial'}}>
                    {source}
                  </div>}
                </div>
              </div>}
        </div>}
        <div style={{position: 'absolute', top: 48, left: 48, padding: '8px 12px',
          borderRadius: 8, background: '#111622dd', color: '#fff',
          font: '700 20px Arial', letterSpacing: 0.7}}>
          {isHost ? 'SATOSHI' : beat.visual_type === 'typography' ? 'RESEARCH / SOURCE RECEIPT' : 'AI ILLUSTRATION'}
        </div>
        {!isHost && beat.visual_type !== 'typography' && <div style={{position: 'absolute',
          left: 52, right: 52, bottom: 185, padding: '18px 22px',
          borderRadius: 14, background: '#111622cc', color: '#fff',
          font: '800 46px Arial', lineHeight: 1.1, textAlign: 'center',
          textShadow: '0 3px 8px #000'}}>{beat.screen_text}</div>}
      </Sequence>;
    })}
    {directEpisode.captions?.length ? <MeasuredCaptions captions={directEpisode.captions}
      fps={directEpisode.fps} /> : null}
  </AbsoluteFill>
);

export const Root: React.FC = () => (
  <>
    <Composition id="SatoshiReel" component={SatoshiReel}
      durationInFrames={episode.duration_frames} fps={episode.fps}
      width={episode.width} height={episode.height} />
    <Composition id="CanonicalSatoshiEpisode" component={CanonicalSatoshiEpisode}
      durationInFrames={canonicalEpisode.duration_frames} fps={canonicalEpisode.fps}
      width={canonicalEpisode.width} height={canonicalEpisode.height} />
    <Composition id="DirectTetrisEpisode" component={DirectTetrisEpisode}
      durationInFrames={directEpisode.duration_frames} fps={directEpisode.fps}
      width={directEpisode.width} height={directEpisode.height} />
    <Composition id="LibraryFirstPilot" component={LibraryFirstPilot}
      durationInFrames={libraryFirstPilot.duration_frames} fps={libraryFirstPilot.fps}
      width={libraryFirstPilot.width} height={libraryFirstPilot.height} />
    <Composition id="LibraryFirstFruitNinja" component={LibraryFirstFruitNinja}
      durationInFrames={libraryFirstFruitNinja.duration_frames} fps={libraryFirstFruitNinja.fps}
      width={libraryFirstFruitNinja.width} height={libraryFirstFruitNinja.height} />
  </>
);
