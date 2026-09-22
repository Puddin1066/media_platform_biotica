import React from 'react';
import {AbsoluteFill, Composition, Sequence, staticFile} from 'remotion';
import {Audio, Video} from '@remotion/media';
import type {Caption} from '@remotion/captions';
import rawEpisode from '../public/episode.json';

type Shot = {src: string; from: number; duration: number; credit: string;
  cue_id: string | null; claim_ids: string[]; playback_rate?: number};
type Episode = {plate: string; plate_start_frames: number; loop_plate: boolean;
  voice: string | null; shots: Shot[]; captions: Caption[]; duration_frames: number;
  fps: number; width: number; height: number; fixture?: boolean};
const episode = rawEpisode as Episode;

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
        <div style={{position: 'absolute', top: 210, right: 44, width: 560,
          padding: 8, background: '#f1e7d4', borderRadius: 12,
          boxShadow: '0 12px 28px #000a'}}>
          <Video src={staticFile(shot.src)} muted loop objectFit="contain"
            playbackRate={shot.playback_rate || 1}
            style={{width: 560, height: 315, background: '#101522'}} />
          <div style={{fontFamily: 'Arial, sans-serif', fontSize: 18,
            padding: '6px 10px', color: '#181c25', whiteSpace: 'nowrap',
            overflow: 'hidden', textOverflow: 'ellipsis'}}>{shot.credit}</div>
        </div>
      </Sequence>
    ))}
    {episode.captions.map((caption, index) => {
      const start = Math.round(caption.startMs * episode.fps / 1000);
      const end = Math.round(caption.endMs * episode.fps / 1000);
      return <Sequence key={index} from={start} durationInFrames={Math.max(1, end - start)}
        layout="none" name={`Caption ${index + 1}`}>
        <div style={{position: 'absolute', top: 1440, left: 90, width: 900,
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
