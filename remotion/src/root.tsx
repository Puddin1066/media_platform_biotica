import React from 'react';
import {AbsoluteFill, Composition, Sequence, staticFile} from 'remotion';
import {Audio, Video} from '@remotion/media';
import rawEpisode from '../public/episode.json';

type Shot = {src: string; from: number; duration: number; credit: string;
  cue_id: string | null; claim_ids: string[]};
type Episode = {plate: string; plate_start_frames: number; loop_plate: boolean;
  voice: string | null; shots: Shot[]; duration_frames: number;
  fps: number; width: number; height: number};
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
          <Video src={staticFile(shot.src)} muted objectFit="contain"
            style={{width: 560, height: 315, background: '#101522'}} />
          <div style={{fontFamily: 'Arial, sans-serif', fontSize: 18,
            padding: '6px 10px', color: '#181c25', whiteSpace: 'nowrap',
            overflow: 'hidden', textOverflow: 'ellipsis'}}>{shot.credit}</div>
        </div>
      </Sequence>
    ))}
  </AbsoluteFill>
);

export const Root: React.FC = () => (
  <Composition id="SatoshiReel" component={SatoshiReel}
    durationInFrames={episode.duration_frames} fps={episode.fps}
    width={episode.width} height={episode.height} />
);
