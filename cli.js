#!/usr/bin/env node
require('dotenv').config();

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { runFounderResearch } = require('./pipelines/founder_research');
const { remember, listAll } = require('./memory/store');
const { getProvider } = require('./providers');

const RESET = '\x1b[0m';
const DIM = '\x1b[2m';
const BOLD = '\x1b[1m';
const CYAN = '\x1b[36m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const RED = '\x1b[31m';

// ── Output directory ──────────────────────────────────────────────────────────

function getOutputDir() {
  const vaultPath = process.env.OBSIDIAN_VAULT_PATH;
  const subfolder = process.env.OBSIDIAN_SUBFOLDER || 'Timbre';
  if (vaultPath) {
    const dir = path.join(vaultPath, subfolder);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    return dir;
  }
  return path.join(__dirname, 'profiles');
}

// ── File helpers ──────────────────────────────────────────────────────────────

function slugify(str) {
  return str.toLowerCase().replace(/\s+/g, '-').replace(/[^\w一-鿿-]/g, '').slice(0, 60);
}

function buildFilename(entity) {
  const date = new Date().toISOString().slice(0, 10);
  return `${slugify(entity.founder_en || entity.founder)}-${slugify(entity.company)}-${date}.md`;
}

function buildFrontmatter(entity) {
  const date = new Date().toISOString().slice(0, 10);
  const tags = ['founder-profile'];
  if (entity.valuation) {
    const v = parseFloat(entity.valuation);
    if (v >= 10000) tags.push('decacorn');
    else if (v >= 1000) tags.push('unicorn');
  }
  const lines = ['---', `founder: "${entity.founder}"`];
  if (entity.founder_en && entity.founder_en !== entity.founder)
    lines.push(`founder_en: "${entity.founder_en}"`);
  lines.push(
    `company: "${entity.company}"`,
    entity.valuation ? `valuation: "${entity.valuation}"` : null,
    `created: ${date}`,
    `tags: [${tags.map(t => `"${t}"`).join(', ')}]`,
    `source: "见微·Timbre"`,
    '---', '',
  );
  return lines.filter(Boolean).join('\n');
}

function addWikiLinks(profile, entity) {
  let result = profile;
  const targets = [entity.company];
  if (entity.founder_en && entity.founder_en !== entity.founder) targets.push(entity.founder_en);
  for (const target of targets) {
    if (!target || target.length < 2) continue;
    const escaped = target.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    result = result.replace(new RegExp(`(?<!\\[\\[)\\b${escaped}\\b(?!\\]\\])`, ''), `[[${target}]]`);
  }
  return result;
}

// ── Intent classification ─────────────────────────────────────────────────────

async function classifyIntent(input, hasSession) {
  const { complete } = getProvider();
  const sessionNote = hasSession ? '（当前 session 已完成过一次研究）' : '（当前 session 尚未研究任何人）';

  const raw = await complete(
    '你是一个意图分类器，只输出分类结果，不输出任何其他内容。',
    `用户输入：「${input}」
当前状态：${sessionNote}

判断用户意图，从以下选项中选一个输出：
- research   （想研究某个创始人或公司）
- followup   （对刚才研究结果的追问或要求补充，只有 session 里有研究结果时才选这个）
- list       （查看已保存档案）
- memory     （查看历史研究记录）
- help       （需要帮助或想了解用法）
- exit       （想退出）

只输出一个单词。`,
  );

  return raw.trim().toLowerCase().split(/\s/)[0];
}

// ── Follow-up QA ──────────────────────────────────────────────────────────────

async function answerFollowUp(question, sessionCtx, send) {
  const { complete } = getProvider();
  send({ type: 'stage', name: 'followup', status: 'start', label: '基于档案回答中' });

  const answer = await complete(
    `你是一位一级市场研究员，刚刚完成了对「${sessionCtx.entity.founder}（${sessionCtx.entity.company}）」的调研。请基于以下档案回答用户追问，如档案中无相关信息请明确说明，不要捏造。`,
    `档案内容：\n\n${sessionCtx.profile}\n\n用户追问：${question}`,
  );

  send({ type: 'stage', name: 'followup', status: 'done' });
  return answer;
}

// ── @ref parsing ──────────────────────────────────────────────────────────────

function extractRefs(input) {
  const files = [], urls = [];
  const query = input.replace(/@([^\s]+)/g, (_, ref) => {
    if (ref.startsWith('http://') || ref.startsWith('https://')) urls.push(ref);
    else files.push(ref);
    return '';
  }).trim();
  return { query, files, urls };
}

// ── Display helpers ───────────────────────────────────────────────────────────

function listProfiles() {
  const dir = getOutputDir();
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.md') && f !== '.gitkeep');
  if (!files.length) { console.log(`${DIM}  还没有保存的档案。${RESET}`); return; }
  console.log(`${BOLD}  已保存档案 (${files.length}):${RESET}\n`);
  files.sort().reverse().forEach(f => {
    const size = Math.round(fs.statSync(path.join(dir, f)).size / 1024);
    console.log(`  ${GREEN}·${RESET} ${f.replace('.md', '')}  ${DIM}(${size} KB)${RESET}`);
  });
}

function listMemory() {
  const entries = listAll();
  if (!entries.length) { console.log(`${DIM}  还没有研究记录。${RESET}`); return; }
  console.log(`${BOLD}  研究记录 (${entries.length}):${RESET}\n`);
  entries.forEach(e => {
    const exists = e.profilePath && fs.existsSync(e.profilePath);
    console.log(`  ${exists ? GREEN : DIM}·${RESET} ${e.founder} · ${e.company}  ${DIM}${e.lastResearched}${RESET}`);
  });
}

function makeSend() {
  return function send(event) {
    switch (event.type) {
      case 'stage':
        if (event.status === 'start')
          process.stdout.write(`\n  ${CYAN}▸${RESET} ${event.label || event.name}  `);
        else if (event.status === 'done') {
          if (event.result) {
            const { founder, company, confidence } = event.result;
            process.stdout.write(`\n  ${DIM}→ ${founder} · ${company}  (置信度 ${Math.round((confidence || 0) * 100)}%)${RESET}`);
          }
          process.stdout.write('\n');
        }
        break;
      case 'tool_start':
        process.stdout.write(`${DIM}.${RESET}`);
        break;
      case 'plan_ready': {
        const dims = event.plan.dimensions || [];
        const total = dims.reduce((n, d) => n + (d.queries?.length || 0), 0);
        console.log(`\n  ${DIM}计划：${dims.map(d => d.label).join(' · ')}  共 ${total} 条搜索${RESET}`);
        break;
      }
      case 'memory_hit':
        console.log(`\n  ${YELLOW}↩${RESET}  ${DIM}发现已有记录：${event.entity.founder} · ${event.entity.company}（${event.entity.lastResearched}）${RESET}`);
        break;
      case 'context_error':
        console.log(`\n  ${YELLOW}⚠${RESET}  ${DIM}读取失败：${event.path} — ${event.error}${RESET}`);
        break;
      case 'eval': {
        const { score, wordCount, urlCount, issues } = event.metrics;
        const c = score >= 80 ? GREEN : score >= 60 ? YELLOW : RED;
        console.log(`\n  ${BOLD}质量评分${RESET}  ${c}${score}分${RESET}  字数 ${wordCount}  来源 ${urlCount}`);
        if (issues.length) issues.forEach(i => console.log(`  ${YELLOW}⚠${RESET}  ${i}`));
        break;
      }
    }
  };
}

// ── Main query handler ────────────────────────────────────────────────────────

async function handleQuery(input, rl, sessionCtx) {
  const trimmed = input.trim();
  if (!trimmed) { rl.prompt(); return sessionCtx; }

  rl.pause();
  const send = makeSend();

  try {
    // Classify intent with LLM
    process.stdout.write(`\n  ${DIM}…${RESET}`);
    const intent = await classifyIntent(trimmed, !!sessionCtx);
    process.stdout.write('\r  \r'); // clear the ellipsis

    if (intent === 'exit') {
      console.log(`\n  ${DIM}再见。${RESET}\n`);
      rl.close();
      process.exit(0);
    }

    if (intent === 'list') {
      console.log(''); listProfiles(); console.log('');
      rl.resume(); rl.prompt(); return sessionCtx;
    }

    if (intent === 'memory') {
      console.log(''); listMemory(); console.log('');
      rl.resume(); rl.prompt(); return sessionCtx;
    }

    if (intent === 'help') {
      console.log(`
  ${BOLD}Timbre 会理解你的自然语言，直接说你想做什么就好。${RESET}

  ${DIM}研究：${RESET}
    帮我研究一下梁文锋
    DeepSeek 的创始人背景
    月之暗面 @./notes.md @https://...

  ${DIM}追问（研究完之后）：${RESET}
    他的融资情况能详细说说吗
    联创团队背景呢
    和其他 AI 公司的创始人相比如何

  ${DIM}其他：${RESET}
    查看我保存的档案
    看看历史研究记录
    退出
      `);
      rl.resume(); rl.prompt(); return sessionCtx;
    }

    if (intent === 'followup' && sessionCtx) {
      const answer = await answerFollowUp(trimmed, sessionCtx, send);
      console.log('\n' + answer + '\n');
      rl.resume(); rl.prompt(); return sessionCtx;
    }

    // Default: research
    const { query, files, urls } = extractRefs(trimmed);
    if (files.length) console.log(`\n  ${DIM}附加文档：${files.join('、')}${RESET}`);
    if (urls.length) console.log(`\n  ${DIM}附加链接：${urls.join('、')}${RESET}`);

    const { profile, entity } = await runFounderResearch(query || trimmed, send, files, urls);

    const dir = getOutputDir();
    const filename = entity ? buildFilename(entity) : `profile-${Date.now()}.md`;
    const filepath = path.join(dir, filename);
    const content = entity ? buildFrontmatter(entity) + addWikiLinks(profile, entity) : profile;
    fs.writeFileSync(filepath, content, 'utf8');
    if (entity) remember(entity, filepath);

    const isObsidian = !!process.env.OBSIDIAN_VAULT_PATH;
    const displayPath = isObsidian
      ? `${process.env.OBSIDIAN_VAULT_PATH}/${process.env.OBSIDIAN_SUBFOLDER || 'Timbre'}/${filename}`
      : `profiles/${filename}`;
    console.log(`\n  ${GREEN}✓${RESET}  已保存至 ${BOLD}${displayPath}${RESET}\n`);

    return entity ? { entity, profile, profilePath: filepath } : sessionCtx;

  } catch (err) {
    console.error(`\n  ${RED}✗${RESET}  ${err.message}\n`);
    return sessionCtx;
  } finally {
    rl.resume();
    rl.prompt();
  }
}

// ── Entry point ───────────────────────────────────────────────────────────────

function start() {
  const dest = process.env.OBSIDIAN_VAULT_PATH
    ? `${DIM}Obsidian: ${process.env.OBSIDIAN_VAULT_PATH}/${process.env.OBSIDIAN_SUBFOLDER || 'Timbre'}${RESET}`
    : `${DIM}→ profiles/${RESET}`;

  console.log(`\n  ${BOLD}${CYAN}见微 · Timbre${RESET}  ${dest}`);
  console.log(`  ${DIM}直接说你想研究谁，或者研究完之后继续追问。${RESET}\n`);

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    prompt: `${CYAN}timbre${RESET} › `,
  });

  let sessionCtx = null;

  rl.prompt();

  rl.on('line', async (line) => {
    sessionCtx = await handleQuery(line, rl, sessionCtx);
  });

  rl.on('close', () => {
    console.log(`\n  ${DIM}再见。${RESET}\n`);
    process.exit(0);
  });
}

start();
