/* KIND 공개 서비스: 종목 이력, 관심 종목, 전체 검색과 조건 공유. */
(() => {
    'use strict';
    const el = id => document.getElementById(id);
    const text = (id, value) => { if (el(id)) el(id).textContent = value; };
    const WATCH_KEY = 'nightdisclosure.watchlist.v1';
    const validCode = code => /^\d{6}$/.test(code || '') && !['999980', '999990'].includes(code);
    const validDate = value => {
        try { return /^\d{4}-\d{2}-\d{2}$/.test(value) && new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) === value; }
        catch (_) { return false; }
    };
    const labels = {caution: '투자주의·환기', overheating: '단기과열', warning_risk_trading: '경고·위험·매매거래', short_selling: '공매도', others: '기타'};
    let watches = [];
    try {
        const saved = JSON.parse(localStorage.getItem(WATCH_KEY));
        if (Array.isArray(saved)) watches = saved.filter(item => item && validCode(item.code) && typeof item.name === 'string').slice(0, 100);
    } catch (_) { /* 저장소가 없어도 조회할 수 있다. */ }
    let searchSerial = 0, historySerial = 0, statusSerial = 0, searchPage = 1, searchResult = null;
    let historyCode = '', historyName = '', historyPage = 1;
    let sharedCodes = null, restoring = false, restored = false;
    let searchTimer;

    async function getJSON(url) {
        const response = await fetch(url);
        if (!response.ok) throw new Error('요청을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.');
        const data = await response.json();
        if (!data || !Array.isArray(data.items) || !Number.isInteger(data.total)) throw new Error('공시 응답을 확인할 수 없습니다.');
        return data;
    }
    function watchCodes() { return sharedCodes || watches.map(item => item.code); }
    function isWatched(code) { return watches.some(item => item.code === code); }
    function persistWatches() {
        try { localStorage.setItem(WATCH_KEY, JSON.stringify(watches)); return true; }
        catch (_) { text('service-feedback', '브라우저 저장이 차단되어 이번 방문에서만 유지합니다.'); return false; }
    }
    function toggleWatch(code, name) {
        if (!validCode(code)) return;
        if (isWatched(code)) watches = watches.filter(item => item.code !== code);
        else {
            if (watches.length >= 100) { text('service-feedback', '관심 종목은 최대 100개까지 저장할 수 있습니다.'); return; }
            watches.push({code, name: String(name || code).slice(0, 80)});
        }
        const saved = persistWatches();
        if (saved) text('service-feedback', isWatched(code) ? '관심 종목에 저장했습니다.' : '관심 종목을 해제했습니다.');
        updateHistoryWatch();
        renderWatchlist();
        window.onSearchInput();
    }
    function companyCell(item) {
        if (!validCode(item.code) || ['유가증권시장본부', '코스닥시장본부'].includes(item.company)) {
            const market = ['999980', '999990'].includes(item.code) || ['유가증권시장본부', '코스닥시장본부'].includes(item.company);
            return `<span class="company-name">${escapeHtml(item.company)}</span><small class="service-note"> · ${market ? '시장 자료' : '종목코드 확인 불가'}</small>`;
        }
        return `<button class="service-star" data-watch-code="${item.code}" data-name="${escapeHtml(item.company)}" aria-label="${escapeHtml(item.company)} 관심 종목 ${isWatched(item.code) ? '해제' : '저장'}" aria-pressed="${isWatched(item.code)}">${isWatched(item.code) ? '★' : '☆'}</button><button class="history-link" data-history-code="${item.code}" data-name="${escapeHtml(item.company)}" title="공시 목록의 종목코드 기준 이력 보기">${escapeHtml(item.company)}</button>`;
    }
    function renderWatchlist() {
        el('watchlist-items').innerHTML = watches.length
            ? watches.map(item => `<span><button class="service-btn" data-history-code="${item.code}" data-name="${escapeHtml(item.name)}">${escapeHtml(item.name)} (${item.code})</button><button class="service-star" data-watch-code="${item.code}" data-name="${escapeHtml(item.name)}" aria-label="${escapeHtml(item.name)} 관심 종목 해제">×</button></span>`).join('')
            : '<p class="service-note">저장한 관심 종목이 없습니다. 공시 목록의 ☆를 눌러 추가하세요.</p>';
    }
    function pager(id, data, action) {
        const target = el(id);
        target.replaceChildren();
        target.hidden = false;
        const pages = Math.max(1, Math.ceil(data.total / data.page_size));
        const previous = document.createElement('button');
        previous.className = 'service-btn'; previous.textContent = '← 이전'; previous.disabled = data.page <= 1;
        previous.onclick = () => action(data.page - 1);
        const label = document.createElement('span'); label.className = 'service-note';
        const first = data.total ? (data.page - 1) * data.page_size + 1 : 0;
        label.textContent = `전체 ${data.total.toLocaleString()}건 · ${first}–${Math.min(data.page * data.page_size, data.total)}건 · ${data.page}/${pages}페이지`;
        const next = document.createElement('button');
        next.className = 'service-btn'; next.textContent = '다음 →'; next.disabled = !data.has_more;
        next.onclick = () => action(data.page + 1);
        target.append(previous, label, next);
    }
    function scope() {
        text('counts-scope', searchResult
            ? `검색 조건 전체 ${searchResult.total.toLocaleString()}건 · 표/복사는 이 페이지 ${filteredDisclosuresData.length}건 기준`
            : '현재 표시 자료 기준 · 문서 건수');
        if (searchResult) {
            el('stats-area').innerHTML = Object.keys(labels).map(key => `<span class="stat-badge">${labels[key]}: ${Number(searchResult.category_counts?.[key] || 0).toLocaleString()}건</span>`).join('');
        }
    }
    const originalRender = window.renderDashboard;
    window.renderDashboard = (...args) => { originalRender(...args); scope(); };

    function dailyFilter() {
        searchResult = null;
        el('explore-pagination').hidden = true;
        const q = el('filter-search').value.trim().toLowerCase();
        const excluded = el('exclude-checkbox').checked;
        const selected = el('watch-only').checked ? new Set(watchCodes()) : null;
        filteredDisclosuresData = allDisclosuresData.filter(item => {
            if (selected && !selected.has(item.code)) return false;
            const matches = [item.company, item.code, item.title, item.submitter].some(value => String(value ?? '').toLowerCase().includes(q));
            return !q || (excluded ? !matches : matches);
        });
        el('date-navigation-panel').style.opacity = '1';
        el('date-navigation-panel').style.pointerEvents = 'auto';
        setDateLoading(false);
        window.renderDashboard();
    }
    async function runSearch(page = 1) {
        const serial = ++searchSerial;
        searchPage = page;
        const params = new URLSearchParams({q: el('filter-search').value.trim(), exclude: String(el('exclude-checkbox').checked), page: String(page), size: '50'});
        if (currentActiveTab !== 'all') params.set('category', currentActiveTab);
        if (el('watch-only').checked) params.set('codes', watchCodes().join(','));
        setDateLoading(true);
        text('data-load-status', '전체 기간에서 공시를 검색하고 있습니다.');
        el('date-navigation-panel').style.opacity = '0.45';
        el('date-navigation-panel').style.pointerEvents = 'none';
        try {
            const data = await getJSON('/api/explore?' + params);
            if (serial !== searchSerial || !el('ignore-date-checkbox').checked) return;
            searchResult = data;
            filteredDisclosuresData = data.items;
            window.renderDashboard(true);
            pager('explore-pagination', data, runSearch);
            text('data-load-status', `전체 기간 검색 · 전체 ${data.total.toLocaleString()}건 · ${data.scope}`);
        } catch (error) {
            if (serial !== searchSerial) return;
            searchResult = null; filteredDisclosuresData = [];
            window.renderDashboard(true);
            el('explore-pagination').hidden = true;
            text('data-load-status', error.message);
        } finally {
            if (serial === searchSerial) setDateLoading(false);
        }
    }
    window.onSearchInput = () => {
        if (restoring) return;
        clearTimeout(searchTimer);
        ++searchSerial;
        if (!el('ignore-date-checkbox').checked) { dailyFilter(); return; }
        searchTimer = setTimeout(() => runSearch(1), 250);
    };
    const originalSwitch = window.switchTab;
    window.switchTab = (event, name) => {
        originalSwitch(event, name);
        if (el('ignore-date-checkbox').checked) {
            clearTimeout(searchTimer); runSearch(1);
        }
    };

    function updateHistoryWatch() {
        text('history-watch', isWatched(historyCode) ? '★ 관심 종목 해제' : '☆ 관심 종목 저장');
    }
    async function openHistory(code, name = '', condition = null) {
        if (!validCode(code)) return;
        el('watchlist-dialog').close();
        historyCode = code; historyName = name || code;
        text('history-title', historyName + ' 공시 이력');
        text('history-subtitle', `종목코드 ${code} · 20:00 이후 수집 공시`);
        el('history-from').value = condition?.from || databaseDates.at(-1) || '2025-01-01';
        el('history-to').value = condition?.to || databaseDates[0] || new Date().toLocaleDateString('sv-SE');
        el('history-category').value = condition?.topic || '';
        updateHistoryWatch();
        if (!el('history-dialog').open) el('history-dialog').showModal();
        await loadHistory(condition?.page || 1);
    }
    async function loadHistory(page = 1) {
        const serial = ++historySerial;
        historyPage = page;
        const from = el('history-from').value, to = el('history-to').value;
        if (!validDate(from) || !validDate(to) || from > to) {
            text('history-status', '시작일과 종료일을 확인해 주세요.');
            el('history-events').replaceChildren(); el('history-pagination').replaceChildren();
            return;
        }
        const params = new URLSearchParams({code: historyCode, start: from, end: to, page: String(page), size: '30'});
        if (el('history-category').value) params.set('category', el('history-category').value);
        text('history-status', '종목 공시 이력을 불러오고 있습니다.');
        el('history-events').replaceChildren(); el('history-pagination').replaceChildren();
        try {
            const data = await getJSON('/api/explore?' + params);
            if (serial !== historySerial || !el('history-dialog').open) return;
            if (historyName === historyCode && data.items[0]) {
                historyName = data.items[0].company;
                text('history-title', historyName + ' 공시 이력');
            }
            text('history-status', `선택 기간 전체 ${data.total.toLocaleString()}건 · 관련 공시 문서 수이며 지정 횟수가 아닙니다.`);
            el('history-events').innerHTML = data.items.length ? data.items.map(item => `<article class="history-event"><time datetime="${escapeHtml(item.disclosure_date)}T${escapeHtml(item.time)}:00+09:00">${escapeHtml(item.disclosure_date)} ${escapeHtml(item.time)}</time><p>${renderDisclosureTitle(item)}</p><p class="service-note">${escapeHtml(item.company)} · ${escapeHtml(labels[item.category] || '기타')} · ${escapeHtml(item.submitter)}</p></article>`).join('') : '<p class="service-note">이 기간과 유형에 해당하는 수집 공시가 없습니다.</p>';
            pager('history-pagination', data, loadHistory);
        } catch (error) { if (serial === historySerial) text('history-status', error.message); }
    }
    function closeHistory() { ++historySerial; el('history-dialog').close(); }

    async function copyLink(hash) {
        const url = new URL(window.location.href);
        url.search = ''; url.hash = hash;
        try {
            await navigator.clipboard.writeText(url.href);
            text('service-feedback', '조건 링크를 복사했습니다.');
            if (el('history-dialog').open) text('history-status', '이력 조건 링크를 복사했습니다.');
        } catch (_) {
            window.prompt('아래 조건 링크를 복사하세요.', url.href);
        }
        return url.href;
    }
    function conditionParams() {
        const params = new URLSearchParams();
        const date = el('disclosure-date').value;
        if (validDate(date)) params.set('date', date);
        if (currentActiveTab !== 'all') params.set('tab', currentActiveTab);
        const q = el('filter-search').value.trim().slice(0, 120);
        if (q) params.set('q', q);
        if (el('ignore-date-checkbox').checked) { params.set('all', '1'); params.set('page', String(searchPage)); }
        if (el('exclude-checkbox').checked) params.set('exclude', '1');
        if (el('watch-only').checked) params.set('codes', watchCodes().join(','));
        return params;
    }
    async function restoreHash() {
        const params = new URLSearchParams(window.location.hash.slice(1));
        if (!params.size) return;
        if (validCode(params.get('code'))) {
            await openHistory(params.get('code'), '', {
                from: validDate(params.get('from')) ? params.get('from') : undefined,
                to: validDate(params.get('to')) ? params.get('to') : undefined,
                topic: labels[params.get('topic')] ? params.get('topic') : '',
                page: Math.min(100000, Math.max(1, Number(params.get('page')) || 1))
            });
            return;
        }
        restoring = true;
        try {
            el('filter-search').value = (params.get('q') || '').slice(0, 120);
            el('ignore-date-checkbox').checked = params.get('all') === '1';
            el('exclude-checkbox').checked = params.get('exclude') === '1';
            sharedCodes = params.has('codes') ? params.get('codes').split(',').filter(validCode).slice(0, 100) : null;
            el('watch-only').checked = sharedCodes !== null;
            currentActiveTab = labels[params.get('tab')] ? params.get('tab') : 'all';
            document.querySelectorAll('.tab-btn').forEach(button => {
                button.classList.toggle('active', (button.getAttribute('onclick') || '').includes(`'${currentActiveTab}'`));
            });
            const date = params.get('date');
            if (validDate(date)) {
                el('disclosure-date').value = date;
                activeDate = date; activeMonth = date.slice(0, 7);
                await loadDisclosuresForDate(date);
                renderMonthSelector(); renderDaySelector();
            }
        } finally { restoring = false; }
        if (el('ignore-date-checkbox').checked) await runSearch(Math.min(100000, Math.max(1, Number(params.get('page')) || 1)));
        else dailyFilter();
        if (sharedCodes !== null) text('service-feedback', '공유 링크의 종목 필터를 적용했습니다. 내 관심 종목은 바뀌지 않습니다.');
    }
    function resetFilters() {
        clearTimeout(searchTimer); ++searchSerial;
        el('filter-search').value = '';
        el('ignore-date-checkbox').checked = false;
        el('exclude-checkbox').checked = false;
        el('watch-only').checked = false;
        sharedCodes = null;
        currentActiveTab = 'all';
        document.querySelectorAll('.tab-btn').forEach(button => {
            button.classList.toggle('active', (button.getAttribute('onclick') || '').includes("'all'"));
        });
        window.history.replaceState(null, '', window.location.pathname + window.location.search);
        dailyFilter(); text('service-feedback', '검색 조건을 초기화했습니다.');
    }

    const originalMonths = window.renderMonthSelector;
    window.renderMonthSelector = () => {
        originalMonths();
        el('month-select').innerHTML = getUniqueMonths(databaseDates).map(month => `<option value="${month}"${month === activeMonth ? ' selected' : ''}>${month.replace('-', '년 ')}월</option>`).join('');
    };
    function selectMonth(month) {
        const date = databaseDates.find(value => value.startsWith(month));
        if (!date) return;
        activeMonth = month; activeDate = date; el('disclosure-date').value = date;
        loadDisclosuresForDate(date); renderMonthSelector(); renderDaySelector();
    }
    async function refreshCollectionStatus() {
        const serial = ++statusSerial;
        try {
            const date = el('disclosure-date').value;
            const response = await fetch('/api/collection-status' + (validDate(date) ? '?day=' + date : ''));
            if (!response.ok) throw new Error('status');
            const data = await response.json(), run = data.run;
            if (serial !== statusSerial) return;
            if (!run) { text('collection-status', `${date || '선택일'} · 수집 실행 기록 확인 불가. 표시된 공시의 존재만으로 수집 완료를 판단하지 않습니다.`); return; }
            const when = value => new Intl.DateTimeFormat('ko-KR', {timeZone: 'Asia/Seoul', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false}).format(new Date(value));
            const state = run.state === 'succeeded' ? `저장 확인 · 해당 날짜 DB ${run.stored_count ?? '확인 불가'}건 · ${when(run.completed_at)}`
                : run.state === 'failed' ? `수집 실패 · ${when(run.completed_at)}`
                : Date.now() - new Date(run.started_at).getTime() > 30 * 60000 ? '완료 기록이 지연되고 있습니다. 확인이 필요합니다.' : '수집 실행 중';
            text('collection-status', `${run.target_date} · ${state}`);
        } catch (_) { if (serial === statusSerial) text('collection-status', '수집 실행 기록을 확인할 수 없습니다. 공시 조회는 계속 사용할 수 있습니다.'); }
    }
    const nativeInitialize = window.initializeWithLatest;
    window.initializeWithLatest = async (...args) => {
        await nativeInitialize(...args);
        refreshCollectionStatus();
        if (!restored) { restored = true; await restoreHash(); }
    };
    const nativeLoadDate = window.loadDisclosuresForDate;
    window.loadDisclosuresForDate = async (...args) => { await nativeLoadDate(...args); refreshCollectionStatus(); };
    const nativeTheme = window.toggleTheme;
    window.toggleTheme = () => {
        nativeTheme();
        try { localStorage.setItem('nightdisclosure.theme', document.body.classList.contains('light-mode') ? 'light' : 'dark'); } catch (_) {}
    };
    try { if (localStorage.getItem('nightdisclosure.theme') === 'light' && !document.body.classList.contains('light-mode')) nativeTheme(); } catch (_) {}

    document.addEventListener('click', event => {
        const watch = event.target.closest('[data-watch-code]');
        const history = event.target.closest('[data-history-code]');
        if (watch) toggleWatch(watch.dataset.watchCode, watch.dataset.name);
        else if (history) openHistory(history.dataset.historyCode, history.dataset.name);
    });
    window.addEventListener('hashchange', restoreHash);
    el('history-dialog').addEventListener('close', () => { ++historySerial; });
    window.NightService = {
        companyCell, openHistory, loadHistory, closeHistory, validCode, validDate,
        selectMonth, refreshCollectionStatus, resetFilters,
        openWatchlist: () => { renderWatchlist(); el('watchlist-dialog').showModal(); },
        clearWatchlist: () => { watches = []; persistWatches(); renderWatchlist(); updateHistoryWatch(); window.onSearchInput(); },
        toggleHistoryWatch: () => toggleWatch(historyCode, historyName),
        copyConditions: () => copyLink(conditionParams().toString()),
        copyHistoryLink: () => copyLink(new URLSearchParams({code: historyCode, from: el('history-from').value,
            to: el('history-to').value, topic: el('history-category').value, page: String(historyPage)}).toString())
    };
})();
