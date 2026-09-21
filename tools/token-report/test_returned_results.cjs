const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/returned_results.js', 'utf8');

function render() {
  const data = {generated_at:'2026-09-21', stack:{components:[
    {id:'claude-code', version:'1', commands:['claude -p'], repository:'https://github.com/anthropics/claude-code'},
    {id:'qmd', version:'1', commands:['qmd search'], repository:'https://github.com/tobi/qmd'}]},
    additional_evidence:{returned_results:{result:{scope:'Actual and retained checks', captured_at:'2026-09-21', records:[
      {id:'native-claude', component_ids:['claude'], runtime:'Native Claude', status:'failed',
        observation:'<script>bad()</script>', attachments:[{label:'safe.png',bytes:8,sha256:'abc',mime_type:'image/png',content_base64:'iVBORw0KGgo='}]},
      {id:'support', component_ids:['support-only'], runtime:'Dashboard', status:'observed', attachments:[
        {label:'unsafe.svg',mime_type:'image/svg+xml',content_base64:'PHN2Zz4='}]}]}}}};
  const elements = new Map();
  const rows = [0,1].flatMap(i => [0,1].map(() => ({dataset:{nativeIndex:String(i)},hidden:false})));
  const host = {innerHTML:'', handlers:{}, addEventListener(type, fn){this.handlers[type]=fn;}, querySelectorAll(){return rows;}};
  elements.set('current-native-results',host);
  elements.set('data',{textContent:JSON.stringify(data)});
  const document = {getElementById(id){
    if (!elements.has(id)) elements.set(id,{value:'', hidden:true, scrollIntoView(){this.scrolled=true;}});
    return elements.get(id);
  }};
  vm.runInNewContext(source,{document,URL,Blob,Uint8Array,atob,setTimeout});
  return {host,rows,document};
}

test('coverage joins aliases, retains failures, and exposes uncovered selected components', () => {
  const {host}=render();
  assert.match(host.innerHTML,/1 \/ 2 selected components have attached observations/);
  assert.match(host.innerHTML,/data-native-component-row="claude-code"/);
  assert.match(host.innerHTML,/No attached run in this bundle/);
  assert.match(host.innerHTML,/failed/);
  assert.match(host.innerHTML,/Supporting identities outside.*support-only/);
  assert.match(host.innerHTML,/claude -p/);
});

test('raster bytes render inline while source text and active image formats stay inert', () => {
  const {host}=render();
  assert.match(host.innerHTML,/<img[^>]+src="data:image\/png;base64,iVBORw0KGgo="/);
  assert.doesNotMatch(host.innerHTML,/src="data:image\/svg/);
  assert.match(host.innerHTML,/&lt;script&gt;bad\(\)&lt;\/script&gt;/);
  assert.doesNotMatch(host.innerHTML,/<script>bad/);
});

test('combined filters and evidence jumps never leave the target hidden', () => {
  const {host,rows,document}=render();
  const component=document.getElementById('native-component-filter');
  const runtime=document.getElementById('native-runtime-filter');
  component.value='claude-code'; component.onchange();
  assert.deepEqual(rows.map(r=>r.hidden),[false,false,true,true]);
  runtime.value='Dashboard'; runtime.onchange();
  assert.ok(rows.every(r=>r.hidden));
  assert.equal(document.getElementById('native-filter-empty').hidden,false);
  host.handlers.click({target:{closest:selector=>selector==='[data-native-jump]'?{dataset:{nativeJump:'1'}}:null}});
  assert.ok(rows.every(r=>!r.hidden));
  assert.equal(document.getElementById('native-result-1').scrolled,true);
  assert.equal(component.value,''); assert.equal(runtime.value,'');
});
