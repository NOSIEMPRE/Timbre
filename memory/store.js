const fs = require('fs');
const path = require('path');

const STORE_PATH = path.join(__dirname, 'store.json');

function load() {
  if (!fs.existsSync(STORE_PATH)) return {};
  try { return JSON.parse(fs.readFileSync(STORE_PATH, 'utf8')); }
  catch { return {}; }
}

function save(store) {
  fs.writeFileSync(STORE_PATH, JSON.stringify(store, null, 2), 'utf8');
}

function entityKey(entity) {
  return `${entity.founder}::${entity.company}`.toLowerCase();
}

// Save entity after research completes
function remember(entity, profilePath) {
  const store = load();
  const key = entityKey(entity);
  store[key] = {
    founder: entity.founder,
    founder_en: entity.founder_en || null,
    company: entity.company,
    valuation: entity.valuation || null,
    lastResearched: new Date().toISOString().slice(0, 10),
    profilePath: path.resolve(profilePath),
  };
  save(store);
}

// Recall prior research relevant to a query string
function recall(query) {
  const store = load();
  const q = query.toLowerCase();
  return Object.values(store).filter(entry =>
    q.includes(entry.founder.toLowerCase()) ||
    q.includes(entry.company.toLowerCase()) ||
    (entry.founder_en && q.includes(entry.founder_en.toLowerCase()))
  );
}

function listAll() {
  return Object.values(load()).sort((a, b) => b.lastResearched.localeCompare(a.lastResearched));
}

module.exports = { remember, recall, listAll };
