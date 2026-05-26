const { validate } = require('../schemas/founder_profile');

function qualityCheck(profile, entity) {
  const v = validate(profile);
  return {
    founder: entity.founder,
    company: entity.company,
    wordCount: v.wordCount,
    urlCount: v.urlCount,
    sectionsComplete: v.valid,
    issues: v.issues,
    score: v.valid ? 'pass' : 'needs_improvement',
    timestamp: new Date().toISOString(),
  };
}

module.exports = { qualityCheck };
