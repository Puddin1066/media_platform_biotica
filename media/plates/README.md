# Host plates (private)

Put your on-camera plate here. Default expected file:

`media/plates/ride.mp4`

That should be your Peloton ride recording (you on the bike). The pipeline’s
`host_ride_plate` Runway job uses it as `promptVideo` for video-to-video.

## Do not commit likeness media

`*.mp4` / `*.mov` / `*.webm` under this folder are gitignored. Keep plates on
your machine or private storage.

## Configuration

| Variable | Purpose |
| --- | --- |
| `HOST_PLATE_PATH` | Override local path (default `media/plates/ride.mp4`) |
| `RUNWAY_HOST_PLATE_URI` | HTTPS or Runway URI for live API calls (preferred for large files) |

Live Runway rejects `file://` paths. Small local files can be embedded as data
URIs; larger rides should be uploaded and referenced with `RUNWAY_HOST_PLATE_URI`.
