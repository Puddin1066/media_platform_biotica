import React from 'react';
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

type CanonicalBeat = {
  beat_id: string;
  role: string;
  text: string;
  citations: string[];
  still: string;
  motion: 'hold' | 'flip' | 'push' | 'crossfade' | 'slow_zoom' | 'pause';
  from: number;
  duration: number;
};
type CanonicalEpisode = {
  title: string;
  host: string;
  voice?: string;
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

const EvidenceOverlay: React.FC<{beat: CanonicalBeat}> = ({beat}) => {
  const frame = useCurrentFrame();
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
  return <div style={{position: 'absolute', top: 165, right: 42, width: 575,
    transform: `translateX(${translateX}px) scale(${zoom})`, opacity,
    transformOrigin: 'center center', padding: 9, background: '#f4ead7',
    borderRadius: 16, boxShadow: '0 14px 36px #000b'}}>
    <div style={{position: 'relative', width: 575, height: 355, overflow: 'hidden',
      borderRadius: 10, background: '#111722'}}>
      <Img src={staticFile(beat.still)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      <div style={{position: 'absolute', top: 12, left: 12, padding: '6px 9px',
        background: '#151b24e8', color: '#fff', font: '700 15px Arial, sans-serif',
        letterSpacing: 0.5}}>AI ILLUSTRATION</div>
    </div>
    <div style={{padding: '8px 11px 2px', color: '#202630',
      font: '700 17px Arial, sans-serif', textTransform: 'uppercase'}}>
      {beat.role.replaceAll('_', ' ')}
    </div>
    <div style={{padding: '0 11px 7px', color: '#4a5360',
      font: '600 14px Arial, sans-serif', whiteSpace: 'nowrap', overflow: 'hidden',
      textOverflow: 'ellipsis'}}>
      {source ? `SOURCE: ${source}` : 'EDITORIAL / RHETORICAL BEAT'}
    </div>
  </div>;
};

const CanonicalSatoshiEpisode: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: '#111622'}}>
    <Video src={staticFile(canonicalEpisode.host)} muted={Boolean(canonicalEpisode.voice)} objectFit="cover"
      style={{width: '100%', height: '100%'}} />
    {canonicalEpisode.voice && <Audio src={staticFile(canonicalEpisode.voice)} volume={1} />}
    {canonicalEpisode.beats.map((beat) => (
      <Sequence key={beat.beat_id} from={beat.from} durationInFrames={beat.duration}
        layout="none" name={`${beat.beat_id} ${beat.role}`}>
        <EvidenceOverlay beat={beat} />
        <div style={{position: 'absolute', left: 64, bottom: 115, width: 952,
          textAlign: 'center', color: '#fff', font: '800 51px Arial, sans-serif',
          lineHeight: 1.12, textShadow: '0 4px 14px #000, 0 2px 5px #000',
          padding: '12px 18px', boxSizing: 'border-box'}}>{beat.text}</div>
      </Sequence>
    ))}
    <div style={{position: 'absolute', top: 42, left: 42, padding: '8px 12px',
      background: '#111722d9', color: '#fff', font: '700 18px Arial, sans-serif',
      letterSpacing: 0.8}}>BIOTICA MEDIA · SATOSHI</div>
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
