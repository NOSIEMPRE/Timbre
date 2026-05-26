function getProvider() {
  const provider = (process.env.MODEL_PROVIDER || 'anthropic').toLowerCase();
  if (provider === 'openai') return require('./openai');
  return require('./anthropic');
}

module.exports = { getProvider };
