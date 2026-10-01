// Create one complete Studio workspace atomically in GitHub. No provider runs
// here: the new episode starts at Source and the operator controls every stage.
const OWNER = 'Puddin1066';
const REPO = 'media_platform_biotica';
const API = `https://api.github.com/repos/${OWNER}/${REPO}`;
const MODULES = ['source','research','story','script','prosody','voice','audio_review',
  'alignment','visual_plan','assets','host','assembly','publish'];

function clean(value, max) {
  return String(value || '').trim().slice(0, max);
}

async function github(path, token, options = {}) {
  const response = await fetch(API + path, {
    ...options,
    headers: {Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json',
      'User-Agent': 'satoshi-studio', ...options.headers},
  });
  if (!response.ok) throw new Error(`GitHub ${response.status}: ${(await response.text()).slice(0, 300)}`);
  return response.json();
}

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({error: 'Method not allowed'});
  const token = process.env.GITHUB_TOKEN;
  if (!token) return res.status(503).json({error: 'Studio creation is not configured.'});
  const company = clean(req.body?.company, 160).replace(/\s+/g, ' ');
  const role = clean(req.body?.role, 160).replace(/\s+/g, ' ');
  const question = clean(req.body?.decision_question, 500).replace(/\s+/g, ' ');
  const topic = clean(req.body?.topic, 1600);
  const jobUrl = clean(req.body?.job_url, 600);
  if (!company || !role || !question || !topic) {
    return res.status(400).json({error: 'Company, role, decision question and topic are required.'});
  }
  if (jobUrl) {
    try {if (new URL(jobUrl).protocol !== 'https:') throw new Error();}
    catch {return res.status(400).json({error: 'Job URL must be HTTPS.'});}
  }
  const slug = company.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '').slice(0, 45) || 'company';
  const episode = `opportunity-${slug}-${Date.now().toString(36)}`;
  const root = `studio/episodes/${episode}`;
  const request = {schema_version: 1, format: {id: 'opportunity_brief'},
    trigger_phrase: 'Create an Opportunity Brief',
    conversation_digest: {summary: topic, source_messages: [{id: 'u1', speaker: 'user', text: topic}]},
    opportunity: {company, role, decision_question: question, job_url: jobUrl, candidate: 'Jay'},
    production: {target_seconds: 75, sound_design: false, publish_instagram: false},
    host: {mode: 'brief_canvas'}};
  const manifest = {schema_version: 1, episode_id: episode,
    title: `${company} · Opportunity Brief`, status: 'in_progress',
    request_path: `${root}/request.json`,
    modules: Object.fromEntries(MODULES.map((id, index) => [id,
      {status: index === 0 ? 'ready' : 'not_ready', version: 0}])),
    publish: {manual_approval_required: true, allowed: false}};
  try {
    const branch = await github('/git/ref/heads/main', token);
    const sha = branch.object.sha;
    const parent = await github(`/git/commits/${sha}`, token);
    const tree = await github('/git/trees', token, {method: 'POST', body: JSON.stringify({
      base_tree: parent.tree.sha,
      tree: [{path: `${root}/request.json`, mode: '100644', type: 'blob',
        content: JSON.stringify(request, null, 2) + '\n'},
        {path: `${root}/episode_manifest.json`, mode: '100644', type: 'blob',
          content: JSON.stringify(manifest, null, 2) + '\n'}],
    })});
    const commit = await github('/git/commits', token, {method: 'POST', body: JSON.stringify({
      message: `studio: create opportunity brief for ${company}`, tree: tree.sha, parents: [sha],
    })});
    await github('/git/refs/heads/main', token, {method: 'PATCH',
      body: JSON.stringify({sha: commit.sha, force: false})});
    return res.status(201).json({ok: true, episode, commit: commit.sha});
  } catch (error) {
    return res.status(502).json({error: 'Could not create episode; refresh and retry.', detail: error.message});
  }
}
