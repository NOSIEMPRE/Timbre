from __future__ import annotations
import re


def quality_check(profile: str, entity: dict) -> dict:
    word_count = len(profile.replace(" ", ""))
    url_count = len(re.findall(r"https?://\S+", profile))

    issues = []
    score = 100

    if word_count < 800:
        issues.append(f"档案偏短（{word_count} 字）")
        score -= 20
    if url_count < 3:
        issues.append(f"来源偏少（{url_count} 条链接）")
        score -= 15
    for sec in ["核心判断", "融资", "产品"]:
        if sec not in profile:
            issues.append(f"缺少 {sec} 部分")
            score -= 10
    founder = entity.get("founder", "")
    if founder and founder not in profile:
        issues.append("档案未提及创始人姓名")
        score -= 10

    return {
        "score": max(0, score),
        "word_count": word_count,
        "url_count": url_count,
        "issues": issues,
    }
