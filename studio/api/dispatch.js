const OWNER = 'Puddin1066';
const REPO = 'media_platform_biotica';
const WORKFLOW = 'satoshi-studio-module.yml';
const ALLOWED = new Set(['source','research','story','script','prosody','voice','audio_review','alignment','visual_plan','assets','host','assembly','publish']);

export default async function handler(req, res) {
  if (req.method === 'GET') {
    return res.status(200).json({
      ok: true,
      configured: Boolean(process.env.GITHUB_TOKEN),
      workflow: WORKFLOW,
      auth: 'vercel-protected-control-surface',
    });
  }
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'GET, POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return res.status(503).json({ error: 'Studio dispatch is not configured on the server. Missing GITHUB_TOKEN.' });
  }

  const episode = String(req.body?.episode || '').trim();
  const module = String(req.body?.module || '').trim();
  const allowMediaSpend = req.body?.allow_media_spend === true;
  if (!episode || !/^[a-z0-9][a-z0-9-]{2,120}$/.test(episode)) {
    return res.status(400).json({ error: 'Invalid episode id.' });
  }
  if (!ALLOWED.has(module)) {
    return res.status(400).json({ error: 'Invalid module.' });
  }
  if (['assets', 'host'].includes(module) && !allowMediaSpend) {
    return res.status(400).json({ error: 'This media module requires explicit spend authorization.' });
  }

  const response = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
      'User-Agent': 'satoshi-studio',
    },
    body: JSON.stringify({ ref: 'main', inputs: { episode, module, allow_media_spend: String(allowMediaSpend) } }),
  });

  if (!response.ok) {
    const detail = await response.text();
    return res.status(response.status).json({ error: 'GitHub workflow dispatch failed.', detail: detail.slice(0, 1000) });
  }
  return res.status(202).json({ ok: true, episode, module, workflow: WORKFLOW });
}
