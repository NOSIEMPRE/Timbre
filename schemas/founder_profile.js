const REQUIRED_SECTIONS = [
  'Founder 画像',
  '创始团队图谱',
  '公司与产品',
  '融资信息',
  '信息源清单',
];

function validate(markdown) {
  const issues = [];

  for (const section of REQUIRED_SECTIONS) {
    if (!markdown.includes(section)) {
      issues.push(`缺少章节：${section}`);
    }
  }

  const urls = (markdown.match(/https?:\/\/\S+/g) || []);
  if (urls.length < 3) {
    issues.push(`信息源不足（当前 ${urls.length} 个，需要至少 3 个）`);
  }

  const wordCount = markdown.replace(/\s+/g, ' ').length;
  if (wordCount < 800) {
    issues.push(`档案过短（${wordCount} 字符，建议 800+）`);
  }

  return { valid: issues.length === 0, issues, urlCount: urls.length, wordCount };
}

module.exports = { validate, REQUIRED_SECTIONS };
