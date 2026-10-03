import React, {useMemo} from 'react';
import {AbsoluteFill, Composition, Img, interpolate, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {Audio, Video} from '@remotion/media';
import type {Caption} from '@remotion/captions';
import rawEpisode from '../public/episode.json';
import rawCanonicalEpisode from '../public/canonical-episode.json';

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
  chart?: {source_url: string; units?: string; points: {label: string; value: number}[]};
};
type CanonicalEpisode = {
  title: string;
  format?: string;
  company?: string;
  host: string;
  voice?: string;
  loop_host?: boolean;
  captions?: TimedCaption[];
  beats: CanonicalBeat[];
  duration_frames: number;
  fps: number;
  width: number;
  height: number;
};
const canonicalEpisode = rawCanonicalEpisode as CanonicalEpisode;

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

const EvidenceOverlay: React.FC<{beat: CanonicalBeat; brief?: boolean}> = ({beat, brief = false}) => {
  const frame = useCurrentFrame();
  if (beat.visual_type === 'host') return null;
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
  return <div style={{position: 'absolute', top: brief ? 215 : 900, right: brief ? 75 : 42, width: brief ? 575 : 460,
    transform: `translateX(${translateX}px) scale(${zoom})`, opacity,
    transformOrigin: 'center center', padding: 9, background: '#f4ead7',
    borderRadius: 16, boxShadow: '0 14px 36px #000b'}}>
    <div style={{position: 'relative', width: brief ? 575 : 460, height: brief ? 355 : 460, overflow: 'hidden',
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
        </div> : <div style={{padding: '68px 30px', color: '#ffe19b', font: '800 40px Arial', lineHeight: 1.15}}>
          {beat.screen_text}
        </div>}
      <div style={{position: 'absolute', top: 12, left: 12, padding: '6px 9px',
        background: '#151b24e8', color: '#fff', font: '700 15px Arial, sans-serif',
        letterSpacing: 0.5}}>{beat.visual_type === 'source' ? 'SOURCE FOOTAGE'
          : beat.visual_type === 'chart' ? 'DATA' : beat.visual_type === 'typography' ? 'COMMENTARY' : 'AI ILLUSTRATION'}</div>
    </div>
    <div style={{padding: '8px 11px 2px', color: '#202630',
      font: '700 17px Arial, sans-serif', textTransform: 'uppercase'}}>
      {beat.role.replaceAll('_', ' ')}
    </div>
    <div style={{padding: '0 11px 7px', color: '#4a5360',
      font: '600 14px Arial, sans-serif', whiteSpace: 'nowrap', overflow: 'hidden',
      textOverflow: 'ellipsis'}}>
      {beat.source_label || (source ? `SOURCE: ${source}` : 'EDITORIAL / RHETORICAL BEAT')}
    </div>
    {beat.screen_text && beat.visual_type !== 'typography' && <div style={{padding: '12px 14px',
      borderTop: '2px solid #ad3334', color: '#161d27', font: '800 28px Arial', lineHeight: 1.15}}>
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

const CanonicalSatoshiEpisode: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: '#111622'}}>
    <Video src={staticFile(canonicalEpisode.host)} loop={Boolean(canonicalEpisode.loop_host)} muted={Boolean(canonicalEpisode.voice)} objectFit="cover"
      style={{width: '100%', height: '100%'}} />
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
        <EvidenceOverlay beat={beat} brief={canonicalEpisode.format === 'opportunity_brief'} />
        {!canonicalEpisode.captions?.length && <div style={{position: 'absolute', left: 64, bottom: 115, width: 952,
          textAlign: 'center', color: '#fff', font: '800 51px Arial, sans-serif',
          lineHeight: 1.12, textShadow: '0 4px 14px #000, 0 2px 5px #000',
          padding: '12px 18px', boxSizing: 'border-box'}}>{beat.text}</div>}
      </Sequence>
    ))}
    {canonicalEpisode.captions?.length ? <MeasuredCaptions captions={canonicalEpisode.captions} fps={canonicalEpisode.fps}
      brief={canonicalEpisode.format === 'opportunity_brief'} /> : null}
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
  </>
);
