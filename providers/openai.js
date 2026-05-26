const OpenAI = require('openai');
const { webSearch, formatResults } = require('../tools/web_search');
const { readFile } = require('../tools/read_file');
const { browseUrl } = require('../tools/browse_url');

let _client = null;
function getClient() {
  if (!_client) {
    _client = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
      baseURL: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
    });
  }
  return _client;
}

const RESEARCH_TOOLS = [
  {
    type: 'function',
    function: {
      name: 'web_search',
      description: 'Search the web for information about founders, companies, products, and funding rounds.',
      parameters: {
        type: 'object',
        properties: { query: { type: 'string' } },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'read_file',
      description: 'Read a local file provided by the user (.md, .txt, .pdf, .json, .csv).',
      parameters: {
        type: 'object',
        properties: { path: { type: 'string' } },
        required: ['path'],
      },
    },
  },
];

const SYNTHESIS_TOOLS = [
  {
    type: 'function',
    function: {
      name: 'browse_url',
      description: 'Fetch the full content of a specific URL. Use this when a search result references an important article but only shows a snippet — especially for paywalled sources the user has access to. Only call this for URLs already found in the research results.',
      parameters: {
        type: 'object',
        properties: { url: { type: 'string', description: 'Full URL to fetch' } },
        required: ['url'],
      },
    },
  },
];

async function callTool(name, args, send) {
  send({ type: 'tool_start', name, input: args });

  let content;
  if (name === 'web_search') {
    const { results, error } = await webSearch(args.query);
    content = error ? `Search error: ${error}` : formatResults(results);
  } else if (name === 'read_file') {
    const { content: text, error, pages } = await readFile(args.path);
    if (error) content = `File read error: ${error}`;
    else content = pages ? `[PDF, ${pages} pages]\n\n${text}` : text;
  } else if (name === 'browse_url') {
    const { content: text, error } = await browseUrl(args.url);
    content = error ? `Browse error: ${error}` : text;
  } else {
    content = `Unknown tool: ${name}`;
  }

  send({ type: 'tool_done', name });
  return content;
}

async function reactLoop(systemPrompt, userPrompt, send, maxIterations = 18, tools = RESEARCH_TOOLS) {
  const messages = [
    { role: 'system', content: systemPrompt },
    { role: 'user', content: userPrompt },
  ];
  let iterations = 0;

  while (iterations < maxIterations) {
    iterations++;

    const response = await getClient().chat.completions.create({
      model: process.env.MODEL || 'gpt-4o',
      max_tokens: 8192,
      tools,
      messages,
    });

    const choice = response.choices[0];

    if (choice.finish_reason === 'stop' || !choice.message.tool_calls?.length) {
      return choice.message.content || '';
    }

    messages.push(choice.message);

    for (const toolCall of choice.message.tool_calls) {
      const args = JSON.parse(toolCall.function.arguments);
      const content = await callTool(toolCall.function.name, args, send);
      messages.push({ role: 'tool', tool_call_id: toolCall.id, content });
    }
  }

  throw new Error('Max iterations reached');
}

async function complete(systemPrompt, userPrompt) {
  const response = await getClient().chat.completions.create({
    model: process.env.MODEL || 'gpt-4o',
    max_tokens: 8192,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
  });
  return response.choices[0].message.content || '';
}

module.exports = { reactLoop, complete, SYNTHESIS_TOOLS };
