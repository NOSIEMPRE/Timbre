require('dotenv').config();
const yaml = require('js-yaml');
const fs = require('fs');
const path = require('path');
const { getProvider } = require('../providers');
const { qualityCheck } = require('../eval/quality_check');
const { recall, remember } = require('../memory/store');
const { webSearch, formatResults } = require('../tools/web_search');

function loadPrompt(name) {
  const p = path.join(__dirname, '../prompts', `${name}.yaml`);
  return yaml.load(fs.readFileSync(p, 'utf8'));
}

// Stage 1: resolve arbitrary input → confirmed entity (ReAct, max 4 iterations)
async function resolveEntity(input, send) {
  send({ type: 'stage', name: 'entity_resolution', status: 'start', label: '实体识别中' });

  const prompt = loadPrompt('entity_resolution');
  const userPrompt = prompt.task.replace(/\{input\}/g, input);
  const systemPrompt = '你是一级市场研究员。通过搜索确认用户输入对应的华人创始人和公司，然后以纯 JSON 格式输出，不要有任何其他文字。';

  const { reactLoop } = getProvider();
  const raw = await reactLoop(systemPrompt, userPrompt, send, 4);

  const match = raw.match(/\{[\s\S]*?\}/);
  if (!match) throw new Error('实体识别失败：无法解析 JSON 输出');

  const entity = JSON.parse(match[0]);
  send({ type: 'stage', name: 'entity_resolution', status: 'done', result: entity });
  return entity;
}

// Stage 2a: generate a structured search plan (single LLM call, no tools)
async function planResearch(entity, send) {
  send({ type: 'stage', name: 'planning', status: 'start', label: '制定研究计划' });

  const prompt = loadPrompt('research_plan');
  const userPrompt = prompt.task
    .replace(/\{founder\}/g, entity.founder)
    .replace(/\{founder_en\}/g, entity.founder_en || entity.founder)
    .replace(/\{company\}/g, entity.company)
    .replace(/\{valuation\}/g, entity.valuation || '未知');

  const { complete } = getProvider();
  const raw = await complete(prompt.system, userPrompt);

  let plan;
  try {
    const match = raw.match(/\{[\s\S]*\}/);
    plan = JSON.parse(match ? match[0] : raw);
  } catch {
    throw new Error('研究计划生成失败：无法解析 JSON');
  }

  send({ type: 'stage', name: 'planning', status: 'done' });
  send({ type: 'plan_ready', plan });
  return plan;
}

// Stage 2b: execute all searches in parallel (no LLM, direct Tavily calls)
async function executeSearches(plan, send) {
  send({ type: 'stage', name: 'search', status: 'start', label: '并行搜索中' });

  const allQueries = plan.dimensions.flatMap(dim =>
    dim.queries.map(q => ({ query: q, dimension: dim.name, label: dim.label }))
  );

  const CONCURRENCY = 5;
  const resultsByDimension = {};
  for (const dim of plan.dimensions) resultsByDimension[dim.name] = { label: dim.label, items: [] };

  for (let i = 0; i < allQueries.length; i += CONCURRENCY) {
    const batch = allQueries.slice(i, i + CONCURRENCY);
    await Promise.all(batch.map(async ({ query, dimension }) => {
      send({ type: 'tool_start', name: 'web_search', input: { query } });
      const { results, error } = await webSearch(query);
      send({ type: 'tool_done', name: 'web_search' });
      resultsByDimension[dimension].items.push({
        query,
        content: error ? `搜索失败: ${error}` : formatResults(results),
      });
    }));
  }

  send({ type: 'stage', name: 'search', status: 'done', total: allQueries.length });
  return resultsByDimension;
}

// Format all search results into a structured string for the synthesis prompt
function formatResearchResults(resultsByDimension) {
  return Object.values(resultsByDimension).map(dim => {
    const items = dim.items.map(item =>
      `### 搜索：${item.query}\n${item.content}`
    ).join('\n\n');
    return `## ${dim.label}\n\n${items}`;
  }).join('\n\n---\n\n');
}

// Stage 3: synthesize all results into a structured profile (single LLM call, no tools)
async function synthesize(entity, resultsByDimension, extraContext, send) {
  send({ type: 'stage', name: 'synthesis', status: 'start', label: '综合分析中' });

  const sys = loadPrompt('system');
  const prof = loadPrompt('founder_profile');

  const researchResults = formatResearchResults(resultsByDimension);

  // Inject cross-session memory if prior research exists
  const memories = recall(`${entity.founder} ${entity.company}`);
  let memoryNote = '';
  if (memories.length > 0) {
    const mem = memories[0];
    const hasProfile = mem.profilePath && fs.existsSync(mem.profilePath);
    memoryNote = `\n\n> 记忆提示：此前已于 ${mem.lastResearched} 研究过该 founder。`;
    if (hasProfile) {
      memoryNote += `已有档案：\`${mem.profilePath}\`，如有需要可通过 read_file 工具读取对比。`;
    }
  }

  const userPrompt = prof.task
    .replace(/\{founder\}/g, entity.founder)
    .replace(/\{founder_en\}/g, entity.founder_en || entity.founder)
    .replace(/\{company\}/g, entity.company)
    .replace(/\{valuation\}/g, entity.valuation || '未知')
    .replace(/\{date\}/g, new Date().toLocaleDateString('zh-CN'))
    .replace(/\{research_results\}/g, researchResults)
    .replace(/\{extra_context\}/g, extraContext ? `**用户补充资料：**\n${extraContext}` : '');

  // Stage 3 uses reactLoop with browse_url only (Plan B: agent fetches full articles when needed)
  const { reactLoop, SYNTHESIS_TOOLS } = getProvider();
  const profile = await reactLoop(sys.role + memoryNote, userPrompt, send, 8, SYNTHESIS_TOOLS);

  send({ type: 'stage', name: 'synthesis', status: 'done' });
  return profile;
}

// Main entry point
// contextFiles: local file paths, contextUrls: paywalled/specific URLs to pre-fetch
async function runFounderResearch(input, send, contextFiles = [], contextUrls = []) {
  // Stage 1
  const entity = await resolveEntity(input, send);
  if (!entity.confirmed) {
    throw new Error(`无法确认「${input}」对应估值 2 亿美金以上的华人创始人，请提供更多信息`);
  }

  // Load user-provided local files and URLs
  let extraContext = '';
  const hasContext = contextFiles.length > 0 || contextUrls.length > 0;
  if (hasContext) {
    const { readFile } = require('../tools/read_file');
    const { browseUrl } = require('../tools/browse_url');
    send({ type: 'stage', name: 'context', status: 'start', label: '读取补充资料' });

    for (const filePath of contextFiles) {
      const { content, error } = await readFile(filePath);
      if (content) extraContext += `\n\n[文件: ${path.basename(filePath)}]\n${content}`;
      else send({ type: 'context_error', path: filePath, error });
    }

    for (const url of contextUrls) {
      const { content, error } = await browseUrl(url);
      if (content) extraContext += `\n\n[网页: ${url}]\n${content}`;
      else send({ type: 'context_error', path: url, error });
    }

    send({ type: 'stage', name: 'context', status: 'done' });
  }

  // Stage 2a: Plan
  const plan = await planResearch(entity, send);

  // Stage 2b: Execute
  const resultsByDimension = await executeSearches(plan, send);

  // Stage 3: Synthesize
  const profile = await synthesize(entity, resultsByDimension, extraContext, send);

  const metrics = qualityCheck(profile, entity);
  send({ type: 'eval', metrics });

  return { profile, entity };
}

module.exports = { runFounderResearch, remember };
