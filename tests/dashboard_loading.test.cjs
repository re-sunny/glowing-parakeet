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
    window: {addEventListener() {}},
    document: {getElementById(id) {
        if (!elements.has(id)) elements.set(id, {style: {}, value: ''});
        return elements.get(id);
    }},
    alert(message) { throw new Error(message); },
    async fetch(url) {
        requests.push(url);
        return {ok: true, json: async () => url.startsWith('/api/dates') ? ['2026-10-26', '2025-01-06'] : []};
    },
});
vm.runInContext(source, context);
// 표 렌더링은 네트워크 동작과 무관하므로 이 검사에서는 생략한다.
vm.runInContext('renderDashboard = () => {}; renderMonthSelector = () => {}; renderDaySelector = () => {};', context);
(async () => {
    await context.initializeWithLatest();
    assert.deepEqual(requests.splice(0), ['/api/dates', '/api/disclosures?date=2026-10-26']);
    assert.equal(elements.get('disclosure-date').value, '2026-10-26');
    assert.equal(elements.get('loading').style.display, 'none');
    await context.initializeWithLatest(true);
    assert.deepEqual(requests, ['/api/dates?refresh=1', '/api/disclosures?date=2026-10-26&refresh=1']);
    console.log('Dashboard initial load and forced refresh passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
