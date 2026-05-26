// Single-turn chat (memo / equity / blog tabs)
async function askClaude(prompt, { model, maxTokens } = {}) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, model, maxTokens }),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const d = await res.json(); if (d.error) msg = d.error; } catch (_) {}
    throw new Error(msg);
  }
  const data = await res.json();
  if (!data.content) throw new Error('Empty response');
  return data.content;
}

// Founder pipeline — SSE streaming
// onStage(event): called on stage changes  { type:'stage', name, status, label }
// onTool(event):  called on each search    { type:'tool_start'|'tool_done', name, input }
// Returns: final markdown string
async function askFounder(input, { onStage, onTool } = {}) {
  const res = await fetch('/api/founder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input }),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const d = await res.json(); if (d.error) msg = d.error; } catch (_) {}
    throw new Error(msg);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalContent = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split('\n');
    buffer = lines.pop();

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const raw = line.slice(6).trim();
      if (raw === '[DONE]') return finalContent;
      try {
        const evt = JSON.parse(raw);
        if (evt.type === 'done') { finalContent = evt.content; }
        else if (evt.type === 'error') { throw new Error(evt.message); }
        else if (evt.type === 'stage' && onStage) { onStage(evt); }
        else if ((evt.type === 'tool_start' || evt.type === 'tool_done') && onTool) { onTool(evt); }
      } catch (e) {
        if (e.message && !e.message.startsWith('JSON')) throw e;
      }
    }
  }
  return finalContent;
}
