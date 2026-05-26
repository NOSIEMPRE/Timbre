const Anthropic = require('@anthropic-ai/sdk');
const { webSearch, formatResults } = require('../tools/web_search');
const { readFile } = require('../tools/read_file');
const { browseUrl } = require('../tools/browse_url');

let _client = null;
function getClient() {
  if (!_client) _client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  return _client;
}

// Full tool set for entity resolution (web_search + read_file)
const RESEARCH_TOOLS = [
  {
    name: 'web_search',
    description: 'Search the web for information about founders, companies, products, and funding rounds.',
    input_schema: {
      type: 'object',
      properties: { query: { type: 'string' } },
      required: ['query'],
    },
  },
  {
    name: 'read_file',
    description: 'Read a local file provided by the user (.md, .txt, .pdf, .json, .csv).',
    input_schema: {
      type: 'object',
      properties: { path: { type: 'string' } },
      required: ['path'],
    },
  },
];

// Synthesis tool set: browse_url only (no new searches, but can fetch full articles)
const SYNTHESIS_TOOLS = [
  {
    name: 'browse_url',
    description: 'Fetch the full content of a specific URL. Use this when a search result references an important article but only shows a snippet — especially for paywalled sources the user has access to (TechCrunch, The Information, 晚点 LatePost, 36Kr, etc.). Only call this for URLs already found in the research results.',
    input_schema: {
      type: 'object',
      properties: { url: { type: 'string', description: 'Full URL to fetch' } },
      required: ['url'],
    },
  },
];

async function callTool(name, input, send) {
  send({ type: 'tool_start', name, input });

  let content;
  if (name === 'web_search') {
    const { results, error } = await webSearch(input.query);
    content = error ? `Search error: ${error}` : formatResults(results);
  } else if (name === 'read_file') {
    const { content: text, error, pages } = await readFile(input.path);
    if (error) content = `File read error: ${error}`;
    else content = pages ? `[PDF, ${pages} pages]\n\n${text}` : text;
  } else if (name === 'browse_url') {
    const { content: text, error } = await browseUrl(input.url);
    content = error ? `Browse error: ${error}` : text;
  } else {
    content = `Unknown tool: ${name}`;
  }

  send({ type: 'tool_done', name });
  return content;
}

async function reactLoop(systemPrompt, userPrompt, send, maxIterations = 18, tools = RESEARCH_TOOLS) {
  const messages = [{ role: 'user', content: userPrompt }];
  let iterations = 0;

  while (iterations < maxIterations) {
    iterations++;

    const response = await getClient().messages.create({
      model: process.env.MODEL || 'claude-sonnet-4-6',
      max_tokens: 8192,
      system: systemPrompt,
      tools,
      messages,
    });

    if (response.stop_reason === 'end_turn') {
      return response.content.filter(b => b.type === 'text').map(b => b.text).join('');
    }

    messages.push({ role: 'assistant', content: response.content });
    const toolResults = [];

    for (const block of response.content) {
      if (block.type !== 'tool_use') continue;
      const content = await callTool(block.name, block.input, send);
      toolResults.push({ type: 'tool_result', tool_use_id: block.id, content });
    }

    messages.push({ role: 'user', content: toolResults });
  }

  throw new Error('Max iterations reached');
}

// Single-shot call with no tools
async function complete(systemPrompt, userPrompt) {
  const response = await getClient().messages.create({
    model: process.env.MODEL || 'claude-sonnet-4-6',
    max_tokens: 8192,
    system: systemPrompt,
    messages: [{ role: 'user', content: userPrompt }],
  });
  return response.content.filter(b => b.type === 'text').map(b => b.text).join('');
}

module.exports = { reactLoop, complete, SYNTHESIS_TOOLS };
