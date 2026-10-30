import assert from 'node:assert/strict';
import {createArchive, normalizeRow} from '../build_archive.mjs';

const row = {id: 1, disclosure_date: '2026-09-30', time: '20:15', company: 'N/A', code: '123.0',
    title: '상장폐지에 따른 매매거래정지', submitter: '코스닥시장본부', source_url: 'https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno=20260930000001',
    private_field: 'must not be published'};
assert.equal(normalizeRow(row).company, '코스닥시장본부');
assert.equal(normalizeRow(row).code, '000123');
assert.equal(normalizeRow(row).category, 'others');
assert(!('private_field' in normalizeRow(row)));
assert(!('id' in normalizeRow(row)));
assert.equal(normalizeRow({...row, title: '결과값이 없습니다.'}), null);
assert.equal(normalizeRow({...row, title: '공매도 과열종목 지정'}).category, 'short_selling');
const {manifest, days} = createArchive([row, {...row, id: 2}, {...row, id: 3, disclosure_date: '2026-10-30'}, {...row, id: 4, disclosure_date: '2026-10-31'}], '2026-10-30', 'revision');
assert.deepEqual(manifest.dates, ['2026-09-30']);
assert.equal(manifest.generatedAt, 'revision');
assert.equal(days['2026-09-30'].length, 2);
assert(!days['2026-10-30']);
console.log('PASS: archive normalization, placeholder exclusion, public-field allowlist, current/future exclusion');
