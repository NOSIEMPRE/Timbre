"""
timbre/eval/quality_check.py — Profile quality evaluation.

Two layers:

1. quality_check(profile, entity) → dict
   Fast, synchronous, heuristic.  Scores across 5 dimensions.
   Called automatically after every founder-research run.

2. quality_check_llm(profile, entity, provider) → dict   (async)
   LLM-as-Judge.  Single LLM call using eval_judge.yaml prompt.
   Called only when heuristic score < LLM_JUDGE_THRESHOLD (default 75).

Scoring dimensions (quality_check):
  sections      40 pts  — 5 pts per required section present and non-empty
  citations     25 pts  — [N] citation markers in the body
  risk_flags    15 pts  — P0 / P1 / P2 risk annotations
  length        10 pts  — minimum viable content length
  honesty        5 pts  — uses 「暂无公开数据」 for missing data (not silence)
  sources        5 pts  — src URLs present

Total max = 100 pts.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

# ── Scoring constants ─────────────────────────────────────────────────────────

LLM_JUDGE_THRESHOLD = 75   # run LLM judge when heuristic score is below this

# The 8 standard sections from founder_profile.yaml output_template.
# Keys: identifier used in scoring;  value: regex that matches the section heading.
_REQUIRED_SECTIONS: list[tuple[str, str]] = [
    ("一句话定位",    r"##\s*一句话定位"),
    ("投资亮点",     r"##\s*投资亮点"),
    ("创始人画像",   r"##\s*创始人画像"),
    ("创始团队",     r"##\s*创始团队"),
    ("公司与产品",   r"##\s*公司.{0,4}产品"),
    ("业务牵引力",   r"##\s*业务牵引力"),
    ("融资信息",     r"##\s*融资信息"),
    ("近期动态",     r"##\s*近期动态"),
]

_SECTION_POINTS = 40 // len(_REQUIRED_SECTIONS)  # 5 pts per section

# Citation pattern: [1] [2] [14] etc.
_CITATION_RE = re.compile(r"\[\d+\]")

# Risk flag pattern
_RISK_RE = re.compile(r"\bP[012]\b")

# Honesty signal
_HONESTY_RE = re.compile(r"暂无公开数据")

# Minimum meaningful section body (chars after the heading)
_MIN_SECTION_BODY = 30


# ── Heuristic scorer ──────────────────────────────────────────────────────────

def quality_check(profile: str, entity: dict) -> dict:
    """
    Synchronous heuristic quality check.

    Returns:
        score        int  0–100
        word_count   int  CJK + latin char count (no spaces)
        url_count    int  https?:// URLs found
        citation_count int [N] markers found
        issues       list[str]  human-readable problem list
        dimensions   dict  per-dimension score breakdown
    """
    issues: list[str] = []
    dims: dict[str, int] = {}

    # ── Dimension 1: Section completeness (40 pts) ───────────────────────────
    section_score = 0
    for label, pattern in _REQUIRED_SECTIONS:
        m = re.search(pattern, profile, re.MULTILINE)
        if m:
            # Check the section has non-trivial content (not just the heading)
            body_start = m.end()
            next_heading = re.search(r"^##", profile[body_start:], re.MULTILINE)
            body = profile[body_start: body_start + (next_heading.start() if next_heading else len(profile))]
            has_content = len(body.replace("暂无公开数据", "").strip()) >= _MIN_SECTION_BODY
            if has_content:
                section_score += _SECTION_POINTS
            else:
                issues.append(f"节段「{label}」内容为空或仅写「暂无公开数据」")
        else:
            issues.append(f"缺少节段：{label}")
    dims["sections"] = section_score

    # ── Dimension 2: Citation anchoring (25 pts) ─────────────────────────────
    citations = _CITATION_RE.findall(profile)
    citation_count = len(citations)
    unique_citations = len(set(citations))
    if citation_count >= 10:
        cite_score = 25
    elif citation_count >= 5:
        cite_score = 18
    elif citation_count >= 2:
        cite_score = 10
    elif citation_count == 1:
        cite_score = 5
    else:
        cite_score = 0
        issues.append("档案无任何 [N] 来源引用标注")
    dims["citations"] = cite_score

    # ── Dimension 3: Risk flags (15 pts) ─────────────────────────────────────
    risk_matches = _RISK_RE.findall(profile)
    risk_count = len(risk_matches)
    if risk_count >= 3:
        risk_score = 15
    elif risk_count >= 1:
        risk_score = 9
    else:
        risk_score = 0
        issues.append("未标注任何 P0/P1/P2 风险等级")
    dims["risk_flags"] = risk_score

    # ── Dimension 4: Length (10 pts) ─────────────────────────────────────────
    word_count = len(profile.replace(" ", "").replace("\n", ""))
    if word_count >= 1500:
        len_score = 10
    elif word_count >= 800:
        len_score = 6
    elif word_count >= 400:
        len_score = 3
    else:
        len_score = 0
        issues.append(f"档案过短（{word_count} 字），内容可能严重不足")
    dims["length"] = len_score

    # ── Dimension 5: Honesty signals (5 pts) ─────────────────────────────────
    has_honesty = bool(_HONESTY_RE.search(profile))
    honesty_score = 5 if has_honesty else 0
    if not has_honesty and section_score < 30:
        issues.append("档案既无「暂无公开数据」也缺少节段，存在捏造风险")
    dims["honesty"] = honesty_score

    # ── Dimension 6: Sources (5 pts) ─────────────────────────────────────────
    url_count = len(re.findall(r"https?://\S+", profile))
    src_score = 5 if url_count >= 3 else (3 if url_count >= 1 else 0)
    if url_count == 0:
        issues.append("档案未列任何参考链接")
    dims["sources"] = src_score

    # ── Founder name check ────────────────────────────────────────────────────
    founder = entity.get("founder", "") or entity.get("founder_en", "")
    if founder and len(founder) >= 2 and founder not in profile:
        issues.append(f"档案未提及创始人姓名「{founder}」")

    score = sum(dims.values())

    return {
        "score": score,
        "word_count": word_count,
        "url_count": url_count,
        "citation_count": citation_count,
        "issues": issues,
        "dimensions": dims,
    }


# ── LLM-as-Judge ─────────────────────────────────────────────────────────────

async def quality_check_llm(profile: str, entity: dict, provider) -> dict:
    """
    LLM-as-Judge evaluation. Makes one LLM call via the provided provider.

    Returns:
        grounding       int  0–10
        completeness    int  0–10
        precision       int  0–10
        risk_quality    int  0–10
        fabrication_risk bool
        verdict         str  one-sentence Chinese summary
        llm_score       int  0–100 (normalized composite)
        error           str  (only present if the call failed)
    """
    import yaml

    prompts_dir = Path(__file__).parent.parent / "prompts"
    with open(prompts_dir / "eval_judge.yaml", encoding="utf-8") as f:
        p = yaml.safe_load(f)

    # Truncate profile to avoid blowing the context — first 3500 chars covers
    # all sections even for long profiles.
    excerpt = profile[:3500] + ("\n\n[... 内容已截断]" if len(profile) > 3500 else "")

    task = (
        p["task"]
        .replace("{founder}", entity.get("founder") or entity.get("founder_en") or "Unknown")
        .replace("{company}", entity.get("company") or "Unknown")
        .replace("{profile_excerpt}", excerpt)
    )

    try:
        raw = await provider.complete(system=p["system"], user=task)
        # Strip markdown fences if the model wrapped output
        raw = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`").strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(m.group()) if m else {}
    except Exception as e:
        return {"error": str(e), "llm_score": None}

    # Composite score: grounding 35% + completeness 30% + precision 20% + risk 15%
    g = int(result.get("grounding", 0))
    c = int(result.get("completeness", 0))
    pr = int(result.get("precision", 0))
    r = int(result.get("risk_quality", 0))
    llm_score = round(g * 3.5 + c * 3.0 + pr * 2.0 + r * 1.5)

    return {
        "grounding":        g,
        "completeness":     c,
        "precision":        pr,
        "risk_quality":     r,
        "fabrication_risk": bool(result.get("fabrication_risk", False)),
        "verdict":          result.get("verdict", ""),
        "llm_score":        llm_score,
    }
