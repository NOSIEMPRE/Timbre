const fs = require('fs');
const path = require('path');

const SUPPORTED = ['.md', '.txt', '.pdf', '.json', '.csv'];
const MAX_CHARS = 40000;

async function readFile(filePath) {
  const resolved = path.resolve(filePath);

  if (!fs.existsSync(resolved)) {
    return { content: null, error: `File not found: ${resolved}` };
  }

  const ext = path.extname(resolved).toLowerCase();
  if (!SUPPORTED.includes(ext)) {
    return { content: null, error: `Unsupported file type: ${ext}. Supported: ${SUPPORTED.join(', ')}` };
  }

  if (ext === '.pdf') {
    try {
      const pdfParse = require('pdf-parse');
      const buffer = fs.readFileSync(resolved);
      const data = await pdfParse(buffer);
      const text = data.text.slice(0, MAX_CHARS);
      return { content: text, error: null, pages: data.numpages };
    } catch (e) {
      return { content: null, error: `PDF parse failed: ${e.message}` };
    }
  }

  try {
    const raw = fs.readFileSync(resolved, 'utf8');
    return { content: raw.slice(0, MAX_CHARS), error: null };
  } catch (e) {
    return { content: null, error: `Read failed: ${e.message}` };
  }
}

module.exports = { readFile };
