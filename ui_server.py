"""Local operator UI for step-wise Inquiry Studio pipeline execution.

Stdlib only. Serves the static UI and a small JSON API that drives pipeline.py.
Does not expose secrets. Live provider calls remain gated by environment flags.
"""
import argparse
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pipeline
import runway

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'ui' / 'static'
DEFAULT_OUTPUT = 'outputs/pipeline'


def _json_response(handler, code, payload):
    body = json.dumps(payload).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler):
    length = int(handler.headers.get('Content-Length') or 0)
    if length <= 0:
        return {}
    if length > 1_000_000:
        raise ValueError('Request too large')
    raw = handler.rfile.read(length)
    return json.loads(raw.decode('utf-8'))


class Handler(BaseHTTPRequestHandler):
    server_version = 'InquiryStudioUI/0.1'

    def log_message(self, fmt, *args):
        # Keep operator console readable.
        sys_stderr = __import__('sys').stderr
        sys_stderr.write('%s - %s\n' % (self.address_string(), fmt % args))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == '/api/bootstrap':
            return _json_response(self, 200, pipeline.bootstrap())
        if path == '/api/runs':
            return _json_response(self, 200, {'runs': pipeline.list_runs(DEFAULT_OUTPUT)})
        if path.startswith('/api/runs/'):
            run_id = path.split('/')[-1]
            try:
                return _json_response(self, 200, pipeline.load_run(DEFAULT_OUTPUT, run_id))
            except FileNotFoundError:
                return _json_response(self, 404, {'error': 'Unknown run'})
        if path == '/api/capabilities':
            return _json_response(self, 200, {'media': runway.capabilities(),
                                             'formats': pipeline.WRITING_FORMATS,
                                             'stages': pipeline.STAGES})
        return self._static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            data = _read_json(self)
        except ValueError as exc:
            return _json_response(self, 400, {'error': str(exc)})
        try:
            if path == '/api/runs':
                run = pipeline.start(
                    data.get('case_path', pipeline.DEFAULT_CASE),
                    data.get('hypothesis_ids'),
                    data.get('formats'),
                    data.get('media_targets'),
                    DEFAULT_OUTPUT,
                    data.get('plan_path', pipeline.DEFAULT_PLAN),
                )
                return _json_response(self, 201, run)
            if path.startswith('/api/runs/') and path.endswith('/advance'):
                run_id = path.split('/')[-2]
                run = pipeline.load_run(DEFAULT_OUTPUT, run_id)
                live = bool(data.get('live'))
                run = pipeline.advance(
                    run, root=DEFAULT_OUTPUT, live=live,
                    budget=float(data.get('budget_usd') or 0),
                    max_usd_per_search=float(data.get('max_usd_per_search') or 0),
                    max_usd_per_run=float(data.get('max_usd_per_run') or 0),
                    max_usd_per_job=float(data.get('max_usd_per_job') or 0),
                )
                return _json_response(self, 200, run)
            if path.startswith('/api/runs/') and path.endswith('/skip'):
                run_id = path.split('/')[-2]
                run = pipeline.load_run(DEFAULT_OUTPUT, run_id)
                run = pipeline.skip_stage(run, data.get('stage'), DEFAULT_OUTPUT,
                                          data.get('reason', 'Operator skipped'))
                return _json_response(self, 200, run)
            if path.startswith('/api/runs/') and '/stage/' in path:
                # /api/runs/{id}/stage/{name}
                parts = path.strip('/').split('/')
                run_id, stage = parts[2], parts[4]
                run = pipeline.load_run(DEFAULT_OUTPUT, run_id)
                live = bool(data.get('live'))
                budget = float(data.get('budget_usd') or 0)
                if stage == 'research':
                    run = pipeline.run_research(
                        run, DEFAULT_OUTPUT, live, budget,
                        float(data.get('max_usd_per_search') or 0),
                        int(data.get('max_tool_calls') or 4))
                elif stage == 'writing':
                    run = pipeline.run_writing(
                        run, DEFAULT_OUTPUT, live, budget,
                        float(data.get('max_usd_per_run') or 0),
                        int(data.get('max_tool_calls') or 6))
                elif stage == 'media':
                    run = pipeline.run_media(
                        run, DEFAULT_OUTPUT, live, budget,
                        float(data.get('max_usd_per_job') or 0))
                elif stage == 'review':
                    run = pipeline.advance(run, root=DEFAULT_OUTPUT)
                else:
                    return _json_response(self, 400, {'error': 'Unknown stage'})
                return _json_response(self, 200, run)
        except (ValueError, FileNotFoundError, OSError, RuntimeError, KeyError, TypeError) as exc:
            return _json_response(self, 400, {'error': str(exc), 'publishable': False})
        return _json_response(self, 404, {'error': 'Not found'})

    def _static(self, path):
        if path in ('', '/'):
            path = '/index.html'
        # Prevent path traversal.
        rel = path.lstrip('/')
        target = (STATIC / rel).resolve()
        if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
            self.send_error(404)
            return
        content = target.read_bytes()
        types = {
            '.html': 'text/html; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.svg': 'image/svg+xml',
            '.json': 'application/json',
        }
        ctype = types.get(target.suffix, 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not (STATIC / 'index.html').exists():
        parser.exit(1, 'Missing ui/static/index.html\n')
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({
        'status': 'ready',
        'url': f'http://{args.host}:{args.port}/',
        'pipeline': 'theme → research → writing → media → review',
        'publishable': False,
    }))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')


if __name__ == '__main__':
    main()
