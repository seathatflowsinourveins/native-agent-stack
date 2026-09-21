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
  // Keep original record identities in downloads; normalize only the catalog join.
  const canonical = id => ({claude: 'claude-code', jcodemunch: 'jcodemunch-mcp',
    opentelemetry: 'opentelemetry-collector-contrib'}[id] || id);
  const components = data.stack?.components || [];
  const selectedIds = new Set(components.map(component => component.id));
  const recordComponents = record => (record.component_ids || []).map(canonical);
  const related = id => records.map((record, index) => ({record, index}))
    .filter(({record}) => recordComponents(record).includes(id));
  const covered = components.filter(component => related(component.id).length);
  const auxiliary = [...new Set(records.flatMap(recordComponents).filter(id => !selectedIds.has(id)))];
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
  const upstreamLink = component => {
    try {
      const url = new URL(component.repository);
      return url.protocol === 'https:' && !url.username && !url.password
        ? '<a href="' + esc(url.href) + '" target="_blank" rel="noopener noreferrer">Official source</a>' : '';
    } catch { return ''; }
  };
  const imagePreview = artifact => ['image/png', 'image/jpeg', 'image/webp'].includes(artifact.mime_type)
    ? '<img loading="lazy" style="max-width:100%;height:auto" alt="' + esc(artifact.label) +
      '" src="data:' + artifact.mime_type + ';base64,' + esc(artifact.content_base64) + '">' : '';
  host.innerHTML = '<h2>Attached native runs and dashboard checks</h2>' +
    '<p>' + esc(bundle.scope) + '</p><p class="small">Evidence bundle: ' + esc(bundle.captured_at) +
    '. Report capture: ' + esc(data.generated_at) + '. Each operation keeps its own execution time below.</p>' +
    '<p><button type="button" id="download-native-bundle">Download command/results JSON</button></p>' +
    '<p><strong>' + covered.length + ' / ' + components.length + ' selected components have attached observations.</strong> ' +
    'Coverage includes dated and current checks, failures and dashboard observations; it is not a pass count.</p>' +
    '<details id="native-component-coverage"><summary>Full selected stack: upstream commands and attached evidence</summary>' +
    '<div class="table-wrap"><table><thead><tr><th>Component / selected pin</th><th>Upstream commands</th><th>Attached observations</th></tr></thead><tbody>' +
    components.map(component => {
      const matches = related(component.id);
      return '<tr data-native-component-row="' + esc(component.id) + '"><td><strong>' + esc(component.id) + '</strong><br>' +
        esc(component.version) + '<br>' + upstreamLink(component) + '<p>' + esc(component.role) + '</p></td><td>' +
        pre(component.commands || []) + '</td><td>' + (matches.length
          ? matches.map(({record, index}) => '<button type="button" data-native-jump="' + index + '">' + esc(record.title || record.id) +
            '</button><p class="small">' + esc(record.completed_at || 'Execution date unavailable') + ' · ' + esc(record.status) + '</p>').join('')
          : '<strong>No attached run in this bundle.</strong><p>Catalog inclusion and historical recipe evidence do not establish current execution.</p>') + '</td></tr>';
    }).join('') + '</tbody></table></div></details>' +
    (auxiliary.length ? '<p class="small">Supporting identities outside the selected component count: ' + esc(auxiliary.join(', ')) + '.</p>' : '') +
    '<p><label for="native-component-filter">Component </label><select id="native-component-filter"><option value="">All selected components</option>' +
    components.map(component => '<option value="' + esc(component.id) + '">' + esc(component.id) + '</option>').join('') + '</select></p>' +
    '<p><label for="native-runtime-filter">Show results from </label><select id="native-runtime-filter"><option value="">All runtimes and dashboards</option>' +
    runtimes.map(runtime => '<option value="' + esc(runtime) + '">' + esc(runtime) + '</option>').join('') + '</select> · ' + records.length + ' recorded checks</p>' +
    '<p class="note">These are selected native operations executed for this check. Native client children, this Desktop connection, dashboard APIs and browser observations have separate scope. Usage is not savings; old snapshots and synthetic fixtures remain labeled.</p>' +
    '<div class="tablewrap"><table><thead><tr><th>Selected check</th><th>Observed status</th><th>Dashboard or report</th></tr></thead><tbody>' +
    records.map((record, index) => '<tr data-native-row-runtime="' + esc(record.runtime) + '" data-native-index="' + index + '"><td><button type="button" data-native-jump="' + index + '">' + esc(record.title || record.id) + '</button></td><td>' + esc(record.status) + '</td><td>' + dashboardLink(record) + '</td></tr>').join('') + '</tbody></table></div><p id="native-filter-empty" hidden>No attached observations match these filters.</p>' +
    records.map((record, index) => {
      const returned = (record.attachments || []).map(artifact => {
        const button = download(artifact, 'Download ' + artifact.label);
        return '<details class="native"><summary>' + esc(artifact.label) + ' · ' + esc(artifact.bytes) + ' bytes</summary>' +
          '<p>' + button + '</p><p class="small">SHA-256: <code>' + esc(artifact.sha256) + '</code></p>' +
          (imagePreview(artifact) || (typeof artifact.text === 'string' ? pre(artifact.text) : '<p>Binary attachment; download preserves the original bytes.</p>')) + '</details>';
      }).join('');
      return '<article class="box native-run" id="native-result-' + index + '" data-native-index="' + index + '" data-runtime="' + esc(record.runtime) + '"><h3>' + esc(record.title || record.id) +
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
      document.getElementById('native-runtime-filter').value = '';
      document.getElementById('native-component-filter').value = '';
      filter();
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
  function filter() {
    const runtime = document.getElementById('native-runtime-filter').value;
    const component = document.getElementById('native-component-filter').value;
    let visible = 0;
    for (const row of host.querySelectorAll('[data-native-index]')) {
      const record = records[Number(row.dataset.nativeIndex)];
      row.hidden = !!runtime && record.runtime !== runtime || !!component && !recordComponents(record).includes(component);
      if (!row.hidden) visible++;
    }
    document.getElementById('native-filter-empty').hidden = visible > 0;
  }
  document.getElementById('native-runtime-filter').onchange = filter;
  document.getElementById('native-component-filter').onchange = filter;
})();
