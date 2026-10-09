"""Document Summarizer & Compaction Skill.

Provides deterministic token-frugal document compaction and key points extraction
to fit large context into model prompt budgets.
"""

from __future__ import annotations

import re


def compact_document(text: str, max_chars: int = 2000) -> str:
    """Compact a long document or context string to fit within max_chars.

    Extracts high-signal structural elements (titles, headings, bullet points,
    opening summary, and conclusion) while maintaining strict length guarantees.

    Args:
        text: Original input document or context.
        max_chars: Upper bound character limit (default: 2000).

    Returns:
        Compacted string representation guaranteed to be <= max_chars.
    """
    if max_chars <= 0:
        return ""
    if not text:
        return ""

    text = text.strip()
    if len(text) <= max_chars:
        return text

    # Extract lines
    lines = [line.strip() for line in text.splitlines()]

    # Collect structural components
    headings: list[str] = []
    bullet_points: list[str] = []
    paragraphs: list[str] = []
    current_para: list[str] = []

    for line in lines:
        if not line:
            if current_para:
                paragraphs.append(" ".join(current_para))
                current_para = []
            continue

        if line.startswith("#"):
            headings.append(line)
        elif re.match(r"^[-*•]\s+", line) or re.match(r"^\d+\.\s+", line):
            bullet_points.append(line)
        else:
            current_para.append(line)

    if current_para:
        paragraphs.append(" ".join(current_para))

    # Structured compaction strategy
    # Budget allocation:
    # 1. Header/Intro: ~35% of max_chars
    # 2. Key findings/bullets: ~40% of max_chars
    # 3. Headings/Outline: ~15% of max_chars
    # 4. Closing: ~10% of max_chars

    parts: list[str] = []
    budget = max_chars - 120  # Reserve 120 chars for formatting markers

    # 1. Add intro paragraph
    intro = paragraphs[0] if paragraphs else ""
    if intro:
        intro_budget = min(int(budget * 0.35), len(intro))
        if len(intro) > intro_budget:
            intro = intro[: intro_budget - 3].rstrip() + "..."
        parts.append(f"### Overview\n{intro}")

    # 2. Add outline of sections if headings exist
    if headings:
        outline_str = "\n".join(f"- {h}" for h in headings[:10])
        if len(outline_str) < int(budget * 0.20):
            parts.append(f"### Key Sections\n{outline_str}")

    # 3. Add high-signal bullet points
    if bullet_points:
        selected_bullets: list[str] = []
        curr_len = 0
        bullet_budget = int(budget * 0.40)
        for b in bullet_points:
            if curr_len + len(b) + 1 > bullet_budget:
                break
            selected_bullets.append(b)
            curr_len += len(b) + 1
        if selected_bullets:
            parts.append("### Key Takeaways\n" + "\n".join(selected_bullets))

    # 4. Add conclusion / final paragraph if distinct from intro
    if len(paragraphs) > 1:
        concl = paragraphs[-1]
        concl_budget = min(int(budget * 0.20), len(concl))
        if len(concl) > concl_budget:
            concl = concl[: concl_budget - 3].rstrip() + "..."
        parts.append(f"### Conclusion\n{concl}")

    result = "\n\n".join(parts)

    # Fallback if structured extraction produced too little or text was unstructured
    if len(result) < int(max_chars * 0.3) or not parts:
        # Fall back to head and tail excerpt
        half = (max_chars - 60) // 2
        omitted = len(text) - (half * 2)
        head = text[:half].rstrip()
        tail = text[-half:].lstrip()
        result = f"{head}\n\n[... {omitted} characters truncated ...]\n\n{tail}"

    # Final safeguard: strict slice if still exceeding max_chars
    if len(result) > max_chars:
        if max_chars >= 3:
            result = result[: max_chars - 3].rstrip() + "..."
            if len(result) > max_chars:
                result = result[:max_chars]
        else:
            result = result[:max_chars]

    return result


def summarize_key_points(text: str, max_points: int = 5) -> list[str]:
    """Extract up to max_points concise key bullet points from text.

    Args:
        text: Input text.
        max_points: Maximum number of points to extract.

    Returns:
        List of key point strings.
    """
    if max_points <= 0 or not text:
        return []

    lines = [line.strip() for line in text.splitlines()]
    points: list[str] = []

    # First look for existing bullet points or numbered lists
    for line in lines:
        cleaned = re.sub(r"^[-*•]\s+", "", line)
        cleaned = re.sub(r"^\d+\.\s+", "", cleaned).strip()
        if cleaned and (line.startswith(("-", "*", "•")) or re.match(r"^\d+\.", line)):
            if len(cleaned) > 10 and cleaned not in points:
                points.append(cleaned)
                if len(points) >= max_points:
                    return points

    # If not enough bullets found, extract sentences from paragraphs
    if len(points) < max_points:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for s in sentences:
            s_clean = s.strip()
            if 20 <= len(s_clean) <= 200 and not s_clean.startswith("#"):
                if s_clean not in points:
                    points.append(s_clean)
                    if len(points) >= max_points:
                        break

    return points
