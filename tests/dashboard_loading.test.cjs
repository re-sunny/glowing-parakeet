// 실제 초기화 함수를 실행해 날짜 목록 중복 요청과 수동 갱신 우회를 검사한다.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '..', 'dashboard.html'), 'utf8');
const source = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
const elements = new Map();
const requests = [];
const storage = new Map();
let fetchOverride;
let renderCount = 0;
const context = vm.createContext({
    console,
    Date,
    URLSearchParams,
    localStorage: {getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value)},
    window: {addEventListener() {}},
    document: {getElementById(id) {
        if (!elements.has(id)) elements.set(id, {style: {}, value: '', checked: false, setAttribute(key, value) { this[key] = value; }});
        return elements.get(id);
    }, querySelectorAll() { return []; }},
    alert(message) { throw new Error(message); },
    async fetch(url) {
        requests.push(url);
        if (fetchOverride) return fetchOverride(url);
        return {ok: true, json: async () => ({dates: ['2026-10-26', '2025-01-06'], date: '2026-10-26', disclosures: []})};
    },
});
vm.runInContext(source, context);
const linkedTitle = context.renderDisclosureTitle({source_url: 'https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno=20261028000801', title: '<공시> "안내"'});
assert.match(linkedTitle, /target="_blank" rel="noopener noreferrer"/);
assert.ok(linkedTitle.includes('&lt;공시&gt; &quot;안내&quot;'));
const encodedHref = linkedTitle.match(/href="([^"]+)"/)[1].replaceAll('&amp;', '&');
const parsedHref = new URL(encodedHref, 'https://example.invalid');
assert.equal(parsedHref.origin, 'https://kind.krx.co.kr');
assert.equal(parsedHref.searchParams.get('acptno'), '20261028000801');
assert.equal(context.renderDisclosureTitle({source_url: 'javascript:alert(1)', title: '잘못된 링크'}), '잘못된 링크');
assert.equal(context.renderDisclosureTitle({title: '기존 공시'}), '기존 공시');
// 표 렌더링은 네트워크 동작과 무관하므로 이 검사에서는 생략한다.
vm.runInContext('renderDashboard = () => {}; renderMonthSelector = () => {}; renderDaySelector = () => {};', context);
context.renderDashboard = () => { renderCount++; };
(async () => {
    await context.initializeWithLatest();
    assert.deepEqual(requests.splice(0), ['/api/bootstrap']);
    assert.equal(elements.get('disclosure-date').value, '2026-10-26');
    assert.equal(elements.get('loading').style.display, 'none');
    await context.initializeWithLatest(true);
    assert.deepEqual(requests.splice(0), ['/api/bootstrap?refresh=1']);

    // 저장된 화면은 네트워크 완료를 기다리지 않고 표시한다.
    let resolveFetch;
    fetchOverride = () => new Promise(resolve => { resolveFetch = resolve; });
    const before = renderCount;
    const pending = context.initializeWithLatest();
    assert.equal(renderCount, before + 1);
    assert.equal(elements.get('loading').style.display, 'none');
    assert.match(elements.get('data-load-status').textContent, /저장된/);
    resolveFetch({ok: true, json: async () => ({dates: ['2026-10-30'], date: '2026-10-30', disclosures: []})});
    await pending;
    assert.equal(elements.get('disclosure-date').value, '2026-10-30');

    // 재검증 실패 시 표시 중인 내용을 지우거나 최신이라고 표시하지 않는다.
    fetchOverride = async () => { throw new Error('offline'); };
    await context.initializeWithLatest();
    assert.equal(elements.get('loading').style.display, 'none');
    assert.match(elements.get('data-load-status').textContent, /최신 데이터 확인에 실패/);

    // 초기 응답 대기 중 날짜를 변경하면 늦은 초기 응답으로 선택을 덮어쓰지 않는다.
    fetchOverride = () => new Promise(resolve => { resolveFetch = resolve; });
    const late = context.initializeWithLatest();
    const resolveInitial = resolveFetch;
    await context.loadDisclosuresForDate('2026-10-26'); // 이미 조회한 날짜에는 추가 API 요청이 없다.
    const countBeforeLate = renderCount;
    resolveInitial({ok: true, json: async () => ({dates: ['2026-10-30'], date: '2026-10-30', disclosures: []})});
    await late;
    assert.equal(renderCount, countBeforeLate);

    requests.splice(0);
    fetchOverride = async url => ({ok: true,
        headers: {get: () => url.includes('refresh=1') ? 'MISS' : 'STALE'},
        json: async () => ({dates: ['2026-10-30'], date: '2026-10-30', disclosures: []})});
    await context.initializeWithLatest();
    assert.deepEqual(requests.splice(0), ['/api/bootstrap', '/api/bootstrap?refresh=1']);

    storage.set('nightdisclosure.bootstrap.v1', JSON.stringify({savedAt: Date.now() - 86400001, data: {dates: [], date: null, disclosures: []}}));
    assert.equal(context.readBootstrapCache(), null);
    storage.set('nightdisclosure.bootstrap.v1', '{broken');
    assert.equal(context.readBootstrapCache(), null);

    // 호버 선조회와 실제 클릭이 같은 요청을 공유하고 전체 화면을 막지 않는다.
    requests.splice(0);
    fetchOverride = () => new Promise(resolve => { resolveFetch = resolve; });
    context.prefetchDate('2026-09-30');
    const datePending = context.loadDisclosuresForDate('2026-09-30');
    assert.deepEqual(requests.splice(0), ['/api/disclosures?date=2026-09-30']);
    assert.equal(elements.get('loading').style.display, 'none');
    assert.equal(elements.get('dashboard-sections')['aria-busy'], 'true');
    resolveFetch({ok: true, json: async () => [{title: '9월 공시'}]});
    await datePending;
    assert.equal(elements.get('dashboard-sections')['aria-busy'], 'false');

    // 페이지를 다시 열어 메모리가 비어도 이전에 조회한 날짜는 저장소에서 복원한다.
    vm.runInContext('dateDataCache.clear(); dateCacheTimes.clear();', context);
    await context.loadDisclosuresForDate('2026-09-30');
    assert.deepEqual(requests.splice(0), []);
    assert.equal(context.readDateData('2026-09-30')[0].title, '9월 공시');
    assert.equal(context.dateCacheIsFresh('2020-01-01', Date.now() - 86400001), false);
    const today = new Date().toLocaleDateString('sv-SE');
    assert.equal(context.dateCacheIsFresh(today, Date.now() - 60001), false);

    // 빠르게 날짜를 바꿨을 때 늦게 끝난 요청은 현재 표를 덮어쓰지 않는다.
    const deferred = new Map();
    fetchOverride = url => new Promise(resolve => deferred.set(url, resolve));
    const firstDate = context.loadDisclosuresForDate('2026-08-31');
    const secondDate = context.loadDisclosuresForDate('2026-07-31');
    deferred.get('/api/disclosures?date=2026-07-31')({ok: true, json: async () => [{title: '7월 공시'}]});
    await secondDate;
    deferred.get('/api/disclosures?date=2026-08-31')({ok: true, json: async () => [{title: '8월 공시'}]});
    await firstDate;
    assert.equal(vm.runInContext('allDisclosuresData[0].title', context), '7월 공시');
    assert.equal(context.readDateData('2026-08-31')[0].title, '8월 공시');
    console.log('PASS: initial load, forced refresh, immediate cached render, failed revalidation, date-selection race, stale CDN refresh, expired/broken storage');
    console.log('PASS: shared prefetch, nonblocking date load, persistent date cache, cache expiry, rapid month changes');
})().catch(error => { console.error(error); process.exitCode = 1; });
