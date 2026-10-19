// Execute the actual route handler in memory, without building .next or a server.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const os = require('node:os');
const ts = require('typescript');
const Module = require('node:module');
const file = path.resolve('app/api/county/[geoid]/route.ts');
const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
}).outputText;
const mod = new Module(file, module);
mod.filename = file;
mod.paths = Module._nodeModulePaths(path.dirname(file));
mod._compile(compiled, file);
(async () => {
  const cases = [
    ['24027', 'hazard=wildfire&year=current', 200],
    ['24027', 'hazard=flood&year=current', 200],
    ['24027', 'hazard=wildfire&year=2021', 404],
    ['10005', 'hazard=wildfire&year=current', 404],
    ['24027', 'hazard=flood&year=../2021', 400],
    ['24027', 'hazard=wildfire&year=current&download=1', 200],
  ];
  for (const [geoid, query, expected] of cases) {
    const url = `http://localhost/api/county/${geoid}?${query}`;
    const response = await mod.exports.GET(new Request(url), { params: Promise.resolve({ geoid }) });
    assert.equal(response.status, expected, url);
    const body = await response.json();
    if (expected === 200) {
      const hazard = new URL(url).searchParams.get('hazard');
      const original = JSON.parse(fs.readFileSync(`data/processed/${hazard === 'wildfire' ? 'wildfire/' : ''}counties/${geoid}.json`));
      assert.deepEqual(body, original, 'Maryland response must retain its original format and values');
      assert.equal(response.headers.get('X-Assessment-Period'), 'current');
    }
    if (query.includes('download=1')) assert.match(response.headers.get('Content-Disposition'), /current\.json/);
    console.log(`${response.status} ${query} ${geoid}`);
  }
  // A generic validated flag must not bypass the user's scientific/source gate.
  // Temporary metadata only; no synthetic county measurements are written.
  const originalCwd = process.cwd();
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'climate-publication-gate-'));
  try {
    process.chdir(temporary);
    fs.mkdirSync('data/processed', { recursive: true });
    for (const extra of [
      {},
      { methodology_status: 'approved', source_validation_status: 'pending', observation_year: 2021 },
      { methodology_status: 'approved', source_validation_status: 'validated', observation_year: 2022 },
    ]) {
      fs.writeFileSync('data/processed/assessment-publications.json', JSON.stringify({
        '2021:wildfire:10005': { validation_status: 'validated', sha256: '0'.repeat(64), ...extra },
      }));
      const response = await mod.exports.GET(new Request('http://localhost/api/county/10005?hazard=wildfire&year=2021'),
        { params: Promise.resolve({ geoid: '10005' }) });
      assert.equal(response.status, 404, 'Annual data requires approved methodology, validated sources and matching year');
    }
    console.log('Annual methodology/source/year publication gates passed');
  } finally {
    process.chdir(originalCwd);
    fs.rmSync(temporary, { recursive: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
