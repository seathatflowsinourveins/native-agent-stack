/* Local report presentation. Native bytes are verified and embedded by the collector. */
(() => {
  'use strict';
  const host = document.getElementById('current-native-results');
  if (!host) return;
  const data = JSON.parse(document.getElementById('data')?.textContent || document.getElementById('report-data').textContent);
  const evidence = data.additional_evidence?.returned_results;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const pre = value => '<pre>' + esc(typeof value === 'string' ? value : JSON.stringify(value, null, 2)) + '</pre>';
  if (!evidence) {
    const issues = data.issues || [];
    host.innerHTML = '<h2>Attached native runs and dashboard checks</h2>' +
      (issues.length ? '<p role="alert"><strong>Report collection reported errors. No verified selected run bundle is available.</strong></p>' + pre(issues) : '<p>No selected run bundle was configured or imported.</p>') +
      '<p>Counter refresh alone does not execute or qualify every native client or dashboard.</p>';
    return;
  }
  const bundle = evidence.result;
  const records = bundle.records || [];
  const runtimes = [...new Set(records.map(record => record.runtime))];
  const attachments = [];
  const download = (artifact, label) => {
    const index = attachments.push(artifact) - 1;
    return '<button type="button" data-native-download="' + index + '">' + esc(label) + '</button>';
  };
  const command = record => record.command?.argv || record.command || 'Invocation unavailable';
  const dashboardLink = record => {
    try {
      const url = new URL(record.url);
      return ['http:', 'https:'].includes(url.protocol) ? '<a href="' + esc(url.href) + '" target="_blank" rel="noopener noreferrer">Open view</a>' : '';
    } catch { return ''; }
  };
  host.innerHTML = '<h2>Attached native runs and dashboard checks</h2>' +
    '<p>' + esc(bundle.scope) + '</p><p class="small">Evidence bundle: ' + esc(bundle.captured_at) +
    '. Report capture: ' + esc(data.generated_at) + '. Each operation keeps its own execution time below.</p>' +
    '<p><button type="button" id="download-native-bundle">Download command/results JSON</button></p>' +
    '<p><label for="native-runtime-filter">Show results from </label><select id="native-runtime-filter"><option value="">All runtimes and dashboards</option>' +
    runtimes.map(runtime => '<option value="' + esc(runtime) + '">' + esc(runtime) + '</option>').join('') + '</select> · ' + records.length + ' recorded checks</p>' +
    '<p class="note">These are selected native operations executed for this check. Native client children, this Desktop connection, dashboard APIs and browser observations have separate scope. Usage is not savings; old snapshots and synthetic fixtures remain labeled.</p>' +
    '<div class="tablewrap"><table><thead><tr><th>Selected check</th><th>Observed status</th><th>Dashboard or report</th></tr></thead><tbody>' +
    records.map((record, index) => '<tr data-native-row-runtime="' + esc(record.runtime) + '"><td><button type="button" data-native-jump="' + index + '">' + esc(record.title || record.id) + '</button></td><td>' + esc(record.status) + '</td><td>' + dashboardLink(record) + '</td></tr>').join('') + '</tbody></table></div>' +
    records.map((record, index) => {
      const returned = (record.attachments || []).map(artifact => {
        const button = download(artifact, 'Download ' + artifact.label);
        return '<details class="native"><summary>' + esc(artifact.label) + ' · ' + esc(artifact.bytes) + ' bytes</summary>' +
          '<p>' + button + '</p><p class="small">SHA-256: <code>' + esc(artifact.sha256) + '</code></p>' +
          (typeof artifact.text === 'string' ? pre(artifact.text) : '<p>Binary attachment; download preserves the original bytes.</p>') + '</details>';
      }).join('');
      return '<article class="box native-run" id="native-result-' + index + '" data-runtime="' + esc(record.runtime) + '"><h3>' + esc(record.title || record.id) +
        '</h3><p><strong>' + esc(record.runtime) + ' · ' + esc(record.status) + '</strong> · ' + esc(record.kind) +
        '</p><p class="small">Started: ' + esc(record.started_at || 'unavailable') + ' · Completed: ' +
        esc(record.completed_at || 'unavailable') + '</p><h4>Upstream invocation</h4>' + pre(command(record)) +
        '<h4>Observed result</h4>' + pre(record.observation ?? 'No observation supplied') +
        '<p>' + esc(record.boundary) + '</p>' + returned +
        '<details><summary>Record provenance</summary>' + pre(Object.fromEntries(Object.entries(record).filter(([key]) => key !== 'attachments'))) + '</details></article>';
    }).join('');
  function save(bytes, name, type) {
    const url = URL.createObjectURL(new Blob([bytes], {type}));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = name.replace(/[^A-Za-z0-9._-]/g, '_');
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  host.addEventListener('click', event => {
    const jump = event.target.closest('[data-native-jump]');
    if (jump) {
      document.getElementById('native-result-' + jump.dataset.nativeJump)?.scrollIntoView({block: 'start'});
      return;
    }
    const button = event.target.closest('[data-native-download]');
    if (!button) return;
    const artifact = attachments[Number(button.dataset.nativeDownload)];
    const bytes = Uint8Array.from(atob(artifact.content_base64), ch => ch.charCodeAt(0));
    save(bytes, artifact.label, artifact.mime_type || 'application/octet-stream');
  });
  document.getElementById('download-native-bundle').onclick = () => save(JSON.stringify(evidence, null, 2), 'native-command-results.json', 'application/json');
  document.getElementById('native-runtime-filter').onchange = event => {
    for (const article of host.querySelectorAll('.native-run')) article.hidden = !!event.target.value && article.dataset.runtime !== event.target.value;
    for (const row of host.querySelectorAll('[data-native-row-runtime]')) row.hidden = !!event.target.value && row.dataset.nativeRowRuntime !== event.target.value;
  };
})();
