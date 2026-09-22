const state = {
  bootstrap: null,
  run: null,
};

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function checkedValues(selector) {
  return [...document.querySelectorAll(selector + ':checked')].map((el) => el.value);
}

function renderStages(run) {
  const nav = document.getElementById('stage-nav');
  const stages = (state.bootstrap && state.bootstrap.stages) || [];
  nav.innerHTML = stages.map((name) => {
    const info = (run && run.stages && run.stages[name]) || { status: 'blocked' };
    const current = run && run.stage === name ? 'current' : '';
    return `<div class="stage-pill ${info.status} ${current}" title="${info.status}">${name}<br><small>${info.status}</small></div>`;
  }).join('');
}

function renderBootstrap(data) {
  document.getElementById('theme-text').textContent = data.theme;
  document.getElementById('hypotheses').innerHTML = data.hypotheses.map((h) => `
    <label><input type="checkbox" name="hypothesis" value="${h.id}" checked />
      <span><strong>${h.id}</strong> — ${h.statement}</span></label>`).join('');
  document.getElementById('formats').innerHTML = data.writing_formats.map((f, i) => `
    <label><input type="checkbox" name="format" value="${f}" ${i === 0 ? 'checked' : ''} />
      <span>${f}</span></label>`).join('');
  document.getElementById('media-targets').innerHTML = data.media_capabilities.map((m, i) => `
    <label><input type="checkbox" name="media" value="${m.id}" ${i < 3 ? 'checked' : ''} />
      <span>${m.label}</span></label>`).join('');
  renderStages(null);
}

function renderRun(run) {
  state.run = run;
  const meta = document.getElementById('run-meta');
  const json = document.getElementById('run-json');
  const actions = document.getElementById('run-actions');
  meta.textContent = `Run ${run.run_id} · stage ${run.stage} · formats ${run.formats.join(', ')}`;
  json.hidden = false;
  json.textContent = JSON.stringify(run, null, 2);
  actions.hidden = false;
  renderStages(run);
  renderDetail(run);
}

function renderDetail(run) {
  const el = document.getElementById('stage-detail');
  const cards = Object.entries(run.stages).map(([name, info]) => `
    <article class="card">
      <h3>${name} · ${info.status}</h3>
      <p>${info.summary || info.reason || '—'}</p>
    </article>`).join('');
  el.innerHTML = cards;
}

function showError(err) {
  const box = document.getElementById('error');
  box.hidden = !err;
  box.textContent = err || '';
}

async function startRun() {
  showError('');
  try {
    const run = await api('/api/runs', {
      method: 'POST',
      body: JSON.stringify({
        hypothesis_ids: checkedValues('input[name="hypothesis"]'),
        formats: checkedValues('input[name="format"]'),
        media_targets: checkedValues('input[name="media"]'),
      }),
    });
    renderRun(run);
  } catch (err) {
    showError(err.message);
  }
}

async function advance() {
  if (!state.run) return;
  showError('');
  try {
    const run = await api(`/api/runs/${state.run.run_id}/advance`, {
      method: 'POST',
      body: JSON.stringify({ live: false }),
    });
    renderRun(run);
  } catch (err) {
    showError(err.message);
  }
}

async function skip(stage) {
  if (!state.run) return;
  showError('');
  try {
    const run = await api(`/api/runs/${state.run.run_id}/skip`, {
      method: 'POST',
      body: JSON.stringify({ stage, reason: 'Skipped from UI' }),
    });
    renderRun(run);
  } catch (err) {
    showError(err.message);
  }
}

async function runStage(stage) {
  if (!state.run) return;
  showError('');
  try {
    const run = await api(`/api/runs/${state.run.run_id}/stage/${stage}`, {
      method: 'POST',
      body: JSON.stringify({ live: false }),
    });
    renderRun(run);
  } catch (err) {
    showError(err.message);
  }
}

async function init() {
  showError('');
  state.bootstrap = await api('/api/bootstrap');
  renderBootstrap(state.bootstrap);
  document.getElementById('btn-start').addEventListener('click', startRun);
  document.getElementById('btn-advance').addEventListener('click', advance);
  document.getElementById('btn-skip-research').addEventListener('click', () => skip('research'));
  document.getElementById('btn-skip-writing').addEventListener('click', () => skip('writing'));
  document.getElementById('btn-research').addEventListener('click', () => runStage('research'));
  document.getElementById('btn-writing').addEventListener('click', () => runStage('writing'));
  document.getElementById('btn-media').addEventListener('click', () => runStage('media'));
  document.getElementById('btn-review').addEventListener('click', () => runStage('review'));
}

init().catch((err) => showError(err.message));
