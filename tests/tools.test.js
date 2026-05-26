/**
 * Smoke tests for individual tools.
 * Run: node tests/tools.test.js
 */
require('dotenv').config();
const { webSearch, formatResults } = require('../tools/web_search');

async function testWebSearch() {
  console.log('Testing web_search...');
  const { results, error } = await webSearch('Moonshot AI 杨植麟 创始人', { maxResults: 3 });
  if (error) { console.error('FAIL web_search:', error); process.exit(1); }
  if (!results.length) { console.error('FAIL web_search: no results returned'); process.exit(1); }
  console.log(`PASS web_search — ${results.length} results`);
  console.log('  First result:', results[0].title);
}

async function testFormatResults() {
  console.log('Testing formatResults...');
  const mockResults = [
    { title: 'Test', url: 'https://example.com', content: 'Content here' },
  ];
  const formatted = formatResults(mockResults);
  if (!formatted.includes('Test')) { console.error('FAIL formatResults'); process.exit(1); }
  console.log('PASS formatResults');
}

(async () => {
  await testFormatResults();
  if (process.env.TAVILY_API_KEY) {
    await testWebSearch();
  } else {
    console.log('SKIP web_search (TAVILY_API_KEY not set)');
  }
  console.log('\nAll tool tests passed.');
})();
