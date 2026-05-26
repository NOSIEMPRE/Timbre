require('dotenv').config();
const express = require('express');
const Anthropic = require('@anthropic-ai/sdk');
const path = require('path');
const { runFounderResearch } = require('./pipelines/founder_research');

const app = express();
const PORT = process.env.PORT || 3000;
const MODEL = process.env.MODEL || 'claude-sonnet-4-6';
const MAX_ITERATIONS = 10;

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ── Tool definitions (for legacy /api/agent) ──
const TOOLS = [
  {
    name: 'web_search',
    description: 'Search the web for current information: company news, funding rounds, product launches, financial data, market analysis, etc.',
    input_schema: {
      type: 'object',
      properties: { query: { type: 'string', description: 'Specific search query' } },
      required: ['query'],
    },
  },
];

// Per-mode system prompts
const SYSTEM_PROMPTS = {
  default: '你是一位专业研究助手，拥有 web_search 工具。在撰写任何分析报告前，主动搜索 2–4 次，获取最新的具体信息（融资数据、新闻、产品更新、财务指标等）。基于搜索结果综合撰写，引用具体数字，不确定时标注。',
};

async function executeLegacyTool(name, input) {
  if (name !== 'web_search') return 'Unknown tool.';
  if (!process.env.TAVILY_API_KEY) return 'Web search unavailable (TAVILY_API_KEY not configured).';
  try {
    const res = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: process.env.TAVILY_API_KEY,
        query: input.query,
        search_depth: 'basic',
        max_results: 5,
        include_answer: false,
      }),
    });
    const data = await res.json();
    if (!data.results?.length) return 'No results found.';
    return data.results.map(r => `**${r.title}**\nURL: ${r.url}\n${r.content}`).join('\n\n---\n\n');
  } catch (err) {
    return `Search error: ${err.message}`;
  }
}

// ── Health ──
app.get('/api/health', (req, res) => {
  res.json({ ok: true, model: MODEL, search: !!process.env.TAVILY_API_KEY });
});

// ── Legacy single-turn ──
app.post('/api/chat', async (req, res) => {
  const { prompt, model, maxTokens } = req.body;
  if (!prompt) return res.status(400).json({ error: 'prompt is required' });
  if (!process.env.ANTHROPIC_API_KEY) return res.status(500).json({ error: 'ANTHROPIC_API_KEY not set' });
  try {
    const message = await anthropic.messages.create({
      model: model || MODEL,
      max_tokens: maxTokens || 4096,
      messages: [{ role: 'user', content: prompt }],
    });
    const text = message.content.filter(b => b.type === 'text').map(b => b.text).join('');
    res.json({ content: text, usage: message.usage });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Legacy ReAct agent (SSE) ──
app.post('/api/agent', async (req, res) => {
  const { prompt, model, maxTokens } = req.body;
  if (!prompt) return res.status(400).json({ error: 'prompt is required' });
  if (!process.env.ANTHROPIC_API_KEY) return res.status(500).json({ error: 'ANTHROPIC_API_KEY not set' });

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  const send = (data) => res.write(`data: ${JSON.stringify(data)}\n\n`);

  const messages = [{ role: 'user', content: prompt }];
  let iterations = 0;
  try {
    while (iterations < MAX_ITERATIONS) {
      iterations++;
      const response = await anthropic.messages.create({
        model: model || MODEL,
        max_tokens: maxTokens || 4096,
        system: SYSTEM_PROMPTS.default,
        tools: TOOLS,
        messages,
      });
      if (response.stop_reason === 'end_turn' || response.stop_reason !== 'tool_use') {
        const text = response.content.filter(b => b.type === 'text').map(b => b.text).join('');
        send({ type: 'done', content: text });
        break;
      }
      messages.push({ role: 'assistant', content: response.content });
      const toolResults = [];
      for (const block of response.content) {
        if (block.type !== 'tool_use') continue;
        send({ type: 'tool_start', name: block.name, input: block.input });
        const result = await executeLegacyTool(block.name, block.input);
        send({ type: 'tool_done', name: block.name });
        toolResults.push({ type: 'tool_result', tool_use_id: block.id, content: result });
      }
      messages.push({ role: 'user', content: toolResults });
    }
    if (iterations >= MAX_ITERATIONS) send({ type: 'error', message: '已达最大搜索轮次' });
  } catch (err) {
    send({ type: 'error', message: err.message || 'Agent 执行失败' });
  } finally {
    res.write('data: [DONE]\n\n');
    res.end();
  }
});

// ── Founder Research Pipeline (SSE) ──
app.post('/api/founder', async (req, res) => {
  const { input } = req.body;
  if (!input) return res.status(400).json({ error: 'input is required' });
  if (!process.env.ANTHROPIC_API_KEY) return res.status(500).json({ error: 'ANTHROPIC_API_KEY not set' });

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  const send = (data) => res.write(`data: ${JSON.stringify(data)}\n\n`);

  try {
    const profile = await runFounderResearch(input, send);
    send({ type: 'done', content: profile });
  } catch (err) {
    console.error('[FOUNDER ERROR]', err.message);
    send({ type: 'error', message: err.message || '调研失败' });
  } finally {
    res.write('data: [DONE]\n\n');
    res.end();
  }
});

app.get('*', (req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));

app.listen(PORT, () => {
  console.log(`\n  Research Agent running at http://localhost:${PORT}`);
  console.log(`  Model  : ${MODEL}`);
  console.log(`  API key: ${process.env.ANTHROPIC_API_KEY ? '✓ set' : '✗ missing'}`);
  console.log(`  Search : ${process.env.TAVILY_API_KEY ? '✓ enabled (Tavily)' : '✗ disabled'}\n`);
});
