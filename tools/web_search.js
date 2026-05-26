async function webSearch(query, { maxResults = 6, searchDepth = 'advanced' } = {}) {
  if (!process.env.TAVILY_API_KEY) {
    return { results: [], error: 'TAVILY_API_KEY not configured' };
  }
  try {
    const res = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: process.env.TAVILY_API_KEY,
        query,
        search_depth: searchDepth,
        max_results: maxResults,
        include_answer: false,
      }),
    });
    const data = await res.json();
    return { results: data.results || [], error: null };
  } catch (err) {
    return { results: [], error: err.message };
  }
}

function formatResults(results) {
  if (!results.length) return 'No results found.';
  return results
    .map(r => `**${r.title}**\nURL: ${r.url}\n${r.content}`)
    .join('\n\n---\n\n');
}

module.exports = { webSearch, formatResults };
