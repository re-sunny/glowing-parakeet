// 실제 초기화 함수를 실행해 날짜 목록 중복 요청과 수동 갱신 우회를 검사한다.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '..', 'dashboard.html'), 'utf8');
const source = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
const elements = new Map();
const requests = [];
const context = vm.createContext({
    console,
    Date,
    URLSearchParams,
    window: {addEventListener() {}},
    document: {getElementById(id) {
        if (!elements.has(id)) elements.set(id, {style: {}, value: ''});
        return elements.get(id);
    }},
    alert(message) { throw new Error(message); },
    async fetch(url) {
        requests.push(url);
        return {ok: true, json: async () => ({dates: ['2026-10-26', '2025-01-06'], date: '2026-10-26', disclosures: []})};
    },
});
vm.runInContext(source, context);
const linkedTitle = context.renderDisclosureTitle({disclosure_date: '2025-01-06', time: '20:00', company: '회사 & 이름', code: '005930', title: '<공시> "안내"', submitter: '시장본부'});
assert.match(linkedTitle, /target="_blank" rel="noopener noreferrer"/);
assert.ok(linkedTitle.includes('&lt;공시&gt; &quot;안내&quot;'));
const encodedHref = linkedTitle.match(/href="([^"]+)"/)[1].replaceAll('&amp;', '&');
const parsedHref = new URL(encodedHref, 'https://example.invalid');
assert.equal(parsedHref.pathname, '/api/disclosure-link');
assert.equal(parsedHref.searchParams.get('company'), '회사 & 이름');
assert.equal(parsedHref.searchParams.get('date'), '2025-01-06');
assert.equal(context.renderDisclosureTitle({title: '기존 공시'}), '기존 공시');
// 표 렌더링은 네트워크 동작과 무관하므로 이 검사에서는 생략한다.
vm.runInContext('renderDashboard = () => {}; renderMonthSelector = () => {}; renderDaySelector = () => {};', context);
(async () => {
    await context.initializeWithLatest();
    assert.deepEqual(requests.splice(0), ['/api/bootstrap']);
    assert.equal(elements.get('disclosure-date').value, '2026-10-26');
    assert.equal(elements.get('loading').style.display, 'none');
    await context.initializeWithLatest(true);
    assert.deepEqual(requests, ['/api/bootstrap?refresh=1']);
    console.log('Dashboard initial load and forced refresh passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
