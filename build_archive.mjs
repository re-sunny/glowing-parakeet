// Publish only the same public KIND fields that the dashboard already displays.
// The build uses a publishable/anon key, never the collector's service-role key.
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';

export function normalizeRow(row) {
    const clean = (value, fallback = '-') => {
        const text = String(value ?? '').trim();
        return ['', 'nan', 'none', 'null', 'n/a', 'na', '<na>', '-'].includes(text.toLowerCase()) ? fallback : text;
    };
    const noResults = new Set(['결과값이없습니다', '조회결과가없습니다', '검색결과가없습니다', '조회된데이터가없습니다', '검색된데이터가없습니다', '조회된결과값이없습니다']);
    const compact = value => clean(value).replace(/[\s.!。！]+/g, '');
    if (noResults.has(compact(row.title)) || noResults.has(compact(row.time))) return null;
    const title = clean(row.title);
    const kind = title.replace(/\s+/g, '');
    let category = 'others';
    if (!kind.includes('상장폐지')) {
        if (['거래정지', '정지해제', '매매정지', '투자경고', '투자위험', '투자주의경고', '매매거래'].some(word => kind.includes(word))) category = 'warning_risk_trading';
        else if (kind.includes('단기과열')) category = 'overheating';
        else if (['투자주의', '환기종목'].some(word => kind.includes(word))) category = 'caution';
        else if (kind.includes('공매도')) category = 'short_selling';
    }
    let company = clean(row.company);
    const submitter = clean(row.submitter);
    const market = submitter.replace(/\s+/g, '');
    if (['-', '시장 전체', '회사명 미제공'].includes(company) && ['유가증권시장본부', '코스닥시장본부'].includes(market)) company = market;
    if (company === '-') company = '회사명 미제공';
    let code = clean(row.code).replace(/^(\d+)\.0+$/, '$1');
    if (/^\d+$/.test(code)) code = code.padStart(6, '0');
    return {disclosure_date: row.disclosure_date, time: clean(row.time), company, code, title, submitter, category, source_url: row.source_url ?? null};
}

export function createArchive(rows, today, generatedAt = new Date().toISOString()) {
    const days = {};
    for (const row of [...rows].sort((a, b) => String(b.time ?? '').localeCompare(String(a.time ?? '')) || Number(b.id) - Number(a.id))) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(row.disclosure_date) || row.disclosure_date >= today) continue;
        const normalized = normalizeRow(row);
        if (normalized) (days[row.disclosure_date] ??= []).push(normalized);
    }
    return {manifest: {version: 1, generatedAt, dates: Object.keys(days).sort().reverse()}, days};
}

async function fetchRows(today) {
    const base = process.env.SUPABASE_URL || 'https://uyqmlrivrrjjzcuxbttj.supabase.co';
    const key = process.env.SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_ANON_KEY || 'sb_publishable_KkQB5rDmsV7R5ZkPsMt3pw_bgr29KcM';
    const url = new URL('/rest/v1/disclosures', base);
    url.searchParams.set('select', 'id,disclosure_date,time,company,code,title,submitter,source_url');
    url.searchParams.set('disclosure_date', `lt.${today}`);
    url.searchParams.set('order', 'id.asc');
    const rows = [];
    let expected = null;
    for (let offset = 0; expected === null || offset < expected; offset += 1000) {
        const response = await fetch(url, {headers: {apikey: key, Authorization: `Bearer ${key}`, Range: `${offset}-${offset + 999}`, Prefer: 'count=exact'}, signal: AbortSignal.timeout(30000)});
        if (!response.ok) throw new Error(`Archive public query failed: HTTP ${response.status}`);
        const count = Number(response.headers.get('content-range')?.split('/')[1]);
        if (!Number.isSafeInteger(count) || count < 0) throw new Error('Archive count is unavailable');
        if (expected === null) expected = count;
        if (count !== expected) throw new Error('Archive changed during export; retry build');
        const page = await response.json();
        if (!Array.isArray(page) || (page.length === 0 && rows.length < expected)) throw new Error('Incomplete archive page');
        rows.push(...page);
    }
    if (rows.length !== expected || new Set(rows.map(row => row.id)).size !== rows.length) throw new Error('Archive count or receipt key mismatch');
    return rows;
}

async function build() {
    const today = new Intl.DateTimeFormat('sv-SE', {timeZone: 'Asia/Seoul'}).format(new Date());
    const rows = await fetchRows(today);
    const {manifest, days} = createArchive(rows, today);
    await mkdir('public/archive/dates', {recursive: true});
    await Promise.all(Object.entries(days).map(([date, disclosures]) => writeFile(`public/archive/dates/${date}.json`, JSON.stringify({version: 1, date, generatedAt: manifest.generatedAt, disclosures}))));
    await writeFile('public/archive/manifest.json', JSON.stringify(manifest));
    const html = await readFile('dashboard.html', 'utf8');
    const marker = '/*__ARCHIVE_MANIFEST__*/ null';
    if (!html.includes(marker)) throw new Error('Archive manifest marker missing');
    await writeFile('public/dashboard.html', html.replace(marker, JSON.stringify(manifest)));
    await writeFile('public/service.js', await readFile('service.js', 'utf8'));
    console.log(`Published ${manifest.dates.length} archived dates, ${Object.values(days).reduce((sum, day) => sum + day.length, 0)} public disclosures; today remains live.`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    build().catch(error => { console.error(error.message); process.exitCode = 1; });
}
