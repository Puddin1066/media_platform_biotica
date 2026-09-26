import React from 'react';
import {AbsoluteFill, Composition, Easing, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Audio, Video} from '@remotion/media';
import type {Caption} from '@remotion/captions';
import rawEpisode from '../public/episode.json';

type Shot = {src: string; from: number; duration: number; credit: string;
  cue_id: string | null; claim_ids: string[]; playback_rate?: number;
  visual_type?: 'source' | 'illustration'};
type BrandIdentity = {brand: string; host: string; tagline: string;
  variant: 'dossier' | 'terminal' | 'receipt'; case_id: string; episode_label: string;
  start_frame: number; duration_frames: number; bug_start_frame: number; bug_text: string};
type Episode = {plate: string; plate_start_frames: number; loop_plate: boolean;
  voice: string | null; shots: Shot[]; captions: Caption[]; duration_frames: number;
  fps: number; width: number; height: number; headline?: string; fixture?: boolean;
  script_sha256?: string; brand_identity?: BrandIdentity};
const episode = rawEpisode as Episode;

const BrandIdentityLayer: React.FC = () => {
  const frame = useCurrentFrame();
  const brand = episode.brand_identity;
  if (!brand) return null;
  const start = brand.start_frame;
  const end = start + brand.duration_frames;
  const active = frame >= start && frame < end;
  const reveal = interpolate(frame, [start, start + 7], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const exit = interpolate(frame, [end - 7, end], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.7, 0, 0.84, 0),
  });
  const opacity = active ? Math.min(reveal, exit) : 0;
  const translateX = interpolate(frame, [start, start + 8], [-44, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const caseLine = `CASE ${brand.case_id} // ${brand.episode_label}`;

  return <>
    {active && brand.variant === 'dossier' && <div style={{position: 'absolute', top: 86, left: 54,
      width: 720, opacity, translate: `${translateX}px 0`, rotate: '-1.5deg',
      background: '#efe6d3', color: '#17191e', border: '2px solid #17191e',
      boxShadow: '12px 14px 0 #17191ecc', padding: '22px 28px 18px',
      fontFamily: 'Arial, sans-serif'}}>
      <div style={{fontSize: 20, letterSpacing: 4, fontWeight: 800}}>{brand.brand} // FIELD DOSSIER</div>
      <div style={{fontSize: 54, fontWeight: 950, marginTop: 8}}>{brand.host}</div>
      <div style={{fontSize: 19, marginTop: 8, fontWeight: 850, letterSpacing: 1.2}}>{caseLine}</div>
      <div style={{display: 'flex', alignItems: 'center', gap: 16, marginTop: 12}}>
        <div style={{border: '4px solid #a12c2d', color: '#a12c2d', padding: '6px 10px',
          fontSize: 23, fontWeight: 900, rotate: '-3deg'}}>RECEIPTS REQUIRED</div>
        <div style={{fontSize: 18, fontWeight: 800}}>MEN'S HEALTH INTELLIGENCE</div>
      </div>
    </div>}

    {active && brand.variant === 'terminal' && <div style={{position: 'absolute', top: 82, left: 54,
      width: 720, opacity, translate: `${translateX}px 0`, background: '#09110fef',
      border: '2px solid #72f3b1', boxShadow: '0 0 30px #19d77a66', padding: '22px 28px',
      color: '#bfffdc', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace'}}>
      <div style={{fontSize: 20, letterSpacing: 3}}>&gt; BIOTICA_MEDIA / ANALYSIS_CHANNEL</div>
      <div style={{fontSize: 52, lineHeight: 1.05, fontWeight: 900, marginTop: 10,
        color: '#ffffff'}}>{brand.host}</div>
      <div style={{marginTop: 10, fontSize: 18, letterSpacing: 1.6}}>{caseLine}</div>
      <div style={{marginTop: 8, fontSize: 20, letterSpacing: 2}}>{brand.tagline}</div>
      <div style={{height: 5, marginTop: 14, background: '#72f3b1',
        width: `${interpolate(frame, [start, end - 8], [12, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}%`}} />
    </div>}

    {active && brand.variant === 'receipt' && <div style={{position: 'absolute', top: 70, left: 70,
      width: 650, opacity, translate: `${translateX}px 0`, background: '#faf7ef', color: '#101318',
      padding: '18px 24px 22px', borderTop: '8px solid #101318', borderBottom: '8px solid #101318',
      boxShadow: '0 16px 34px #0009', fontFamily: 'Arial, sans-serif'}}>
      <div style={{fontSize: 19, fontWeight: 900, letterSpacing: 5}}>{brand.brand}</div>
      <div style={{fontSize: 50, fontWeight: 950, marginTop: 6}}>{brand.host}</div>
      <div style={{fontSize: 18, marginTop: 7, fontWeight: 850}}>{caseLine}</div>
      <div style={{fontSize: 21, marginTop: 7, fontWeight: 800}}>{brand.tagline}</div>
      <div style={{display: 'flex', gap: 5, marginTop: 13, height: 26}}>
        {[8,3,10,5,4,12,3,8,5,11,4,7,3,13,5,8,4,10].map((w, i) =>
          <div key={i} style={{width: w, background: '#101318'}} />)}
      </div>
    </div>}

    {frame >= brand.bug_start_frame && <div style={{position: 'absolute', top: 54, right: 46,
      padding: '8px 11px', background: '#10151ca8', borderLeft: '4px solid #b73535',
      color: '#fff', fontFamily: 'Arial, sans-serif', fontSize: 15,
      fontWeight: 900, letterSpacing: 1.6, boxShadow: '0 4px 13px #0004'}}>
      {brand.bug_text}
    </div>}
  </>;
};

const SatoshiReel: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: '#111622'}}>
    {episode.plate && <Video src={staticFile(episode.plate)}
      trimBefore={episode.plate_start_frames} loop={episode.loop_plate}
      muted={Boolean(episode.voice)} objectFit="cover"
      style={{width: '100%', height: '100%'}} />}
    {episode.voice && <Audio src={staticFile(episode.voice)} />}
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
    <BrandIdentityLayer />
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

export const Root: React.FC = () => (
  <Composition id="SatoshiReel" component={SatoshiReel}
    durationInFrames={episode.duration_frames} fps={episode.fps}
    width={episode.width} height={episode.height} />
);
