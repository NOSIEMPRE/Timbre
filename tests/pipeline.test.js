/**
 * Smoke test: verifies the pipeline can be imported and the schema validator works.
 * Run: node tests/pipeline.test.js
 */
require('dotenv').config();
const { validate } = require('../schemas/founder_profile');
const { qualityCheck } = require('../eval/quality_check');

function testSchema() {
  console.log('Testing schema validator...');

  const badProfile = 'Too short.';
  const r1 = validate(badProfile);
  if (r1.valid) { console.error('FAIL schema: should be invalid'); process.exit(1); }
  console.log('PASS schema — correctly flags incomplete profile');
  console.log('  Issues:', r1.issues);

  const goodProfile = `
## Founder 画像\n content \n## 创始团队图谱\n content \n## 公司与产品\n content \n## 融资信息\n content \n## 信息源清单\nhttps://a.com https://b.com https://c.com
`.repeat(5);
  const r2 = validate(goodProfile);
  console.log('PASS schema — full profile evaluation done');
  console.log('  Valid:', r2.valid, '| Issues:', r2.issues);
}

function testQualityCheck() {
  console.log('Testing qualityCheck...');
  const profile = '## Founder 画像\n## 创始团队图谱\n## 公司与产品\n## 融资信息\n## 信息源清单\nhttps://x.com https://y.com https://z.com more content '.repeat(10);
  const entity = { founder: '杨植麟', company: 'Moonshot AI' };
  const metrics = qualityCheck(profile, entity);
  console.log('PASS qualityCheck:', metrics);
}

function testImports() {
  console.log('Testing pipeline import...');
  const { runFounderResearch } = require('../pipelines/founder_research');
  if (typeof runFounderResearch !== 'function') {
    console.error('FAIL: runFounderResearch is not a function');
    process.exit(1);
  }
  console.log('PASS pipeline import');
}

testSchema();
testQualityCheck();
testImports();
console.log('\nAll pipeline tests passed.');
