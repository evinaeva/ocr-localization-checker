"""
Reference section matching with scoring, confidence rules, and MANUAL triggers.

Implements deterministic scoring with priority boosts, placeholder penalties,
length penalties, and confidence thresholds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional

from shared.docx_section_extractor import (
    SectionCandidate,
    HIGH_PRIORITY_KEYWORDS,
    LOW_PRIORITY_KEYWORDS,
)


@dataclass
class SelectionResult:
    """Result of reference section selection."""
    
    chosen_section: Optional[SectionCandidate]
    chosen_text: str  # Cleaned content text
    score_top1: float
    score_top2: float
    delta: float
    warnings: List[str]
    manual_required: bool
    chosen_section_name: Optional[str] = None
    chosen_section_number: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dict for Firestore storage."""
        return {
            "chosen_section_name": self.chosen_section_name,
            "chosen_section_number": self.chosen_section_number,
            "score_top1": self.score_top1,
            "score_top2": self.score_top2,
            "delta": self.delta,
            "warnings": self.warnings,
            "manual_required": self.manual_required,
        }


# CTA bracket characters to remove
CTA_BRACKETS = re.compile(r"[\[\]<>]")

# Robust placeholder detection patterns
PLACEHOLDER_PATTERNS = [
    re.compile(r"%[^%]+%"),  # %skin%, %displayname%, %任何内容%
    re.compile(r"\[[^\]]+\]"),  # [subscriber_firstname_capitalized] and other bracket placeholders
]


def _remove_cta_brackets(text: str) -> str:
    """Remove CTA bracket characters: [ ] < >"""
    return CTA_BRACKETS.sub("", text)


def _has_placeholder(text: str) -> bool:
    """
    Check if text contains placeholder tokens.
    
    Detects:
    - %anything% (any characters between %)
    - [identifier] (ASCII identifier pattern)
    """
    for pattern in PLACEHOLDER_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _count_words(text: str) -> int:
    """Count words (split by whitespace)."""
    return len(text.split())


def _count_chars_no_whitespace(text: str) -> int:
    """Count characters excluding whitespace and CTA brackets."""
    cleaned = _remove_cta_brackets(text)
    return len(re.sub(r"\s+", "", cleaned))


def _compute_similarity(text1: str, text2: str) -> float:
    """
    Compute similarity score using SequenceMatcher (deterministic).
    
    Returns float in [0, 1].
    """
    return SequenceMatcher(None, text1, text2).ratio()


def _get_priority_multiplier(candidate: SectionCandidate) -> float:
    """
    Get priority boost/penalty multiplier for candidate.
    
    Returns:
        1.2 for high priority (BANNER, PIC, IM, POPUP)
        0.8 for low priority (NEWS, EMAIL, LETTER, SUBJECT)
        1.0 otherwise
    """
    if not candidate.section_name:
        return 1.0
    
    name_lower = candidate.section_name.lower()
    
    # Check high priority
    for keyword in HIGH_PRIORITY_KEYWORDS:
        if keyword in name_lower:
            return 1.2
    
    # Check low priority (ALWAYS applies, even for short sections)
    for keyword in LOW_PRIORITY_KEYWORDS:
        if keyword in name_lower:
            return 0.8
    
    return 1.0


def _get_placeholder_multiplier(text: str) -> float:
    """Return 0.5 if text contains placeholders, else 1.0."""
    return 0.5 if _has_placeholder(text) else 1.0


def _get_length_penalty_multiplier(candidate: SectionCandidate, language: str) -> float:
    """
    Apply penalty for long sections (banners are short).
    
    For non-Asian languages: penalize if >50 words
    For ja: penalize if >200 chars (no whitespace)
    For zh-Hans: penalize if >130 chars (no whitespace)
    
    Returns 0.7 if penalty applies, else 1.0.
    """
    if language in ("ja", "zh-Hans"):
        char_count = _count_chars_no_whitespace(candidate.content_text)
        threshold = 200 if language == "ja" else 130
        return 0.7 if char_count > threshold else 1.0
    else:
        word_count = _count_words(candidate.content_text)
        return 0.7 if word_count > 50 else 1.0


def _get_length_mismatch_penalty(ocr_len: int, candidate_len: int) -> float:
    """
    Penalize candidates whose length differs significantly from OCR.
    
    Returns multiplier in [0.6, 1.0] based on length ratio.
    """
    if candidate_len == 0:
        return 0.6
    
    ratio = ocr_len / candidate_len if candidate_len > ocr_len else candidate_len / ocr_len
    
    if ratio < 0.3:
        return 0.6
    elif ratio < 0.5:
        return 0.8
    else:
        return 1.0


def _score_candidate(
    ocr_text: str,
    candidate: SectionCandidate,
    ocr_text_soft: str,
    candidate_text_soft: str,
) -> float:
    """
    Compute score for a candidate.
    
    Args:
        ocr_text: Original OCR text (cleaned)
        candidate: Section candidate
        ocr_text_soft: Normalized soft OCR text
        candidate_text_soft: Normalized soft candidate text
    
    Returns:
        Score in [0, 1] (approximately)
    """
    # Base similarity
    similarity = _compute_similarity(ocr_text_soft, candidate_text_soft)
    
    # Priority boost/penalty
    priority_mult = _get_priority_multiplier(candidate)
    
    # Placeholder penalty (check BEFORE bracket removal)
    placeholder_mult = _get_placeholder_multiplier(candidate.content_text)
    
    # Long text penalty
    length_penalty = _get_length_penalty_multiplier(candidate, candidate.language)
    
    # Length mismatch penalty - use character count for ja/zh
    if candidate.language in ("ja", "zh-Hans"):
        ocr_len = _count_chars_no_whitespace(ocr_text_soft)
        candidate_len = _count_chars_no_whitespace(candidate_text_soft)
    else:
        ocr_len = len(ocr_text_soft.split())
        candidate_len = len(candidate_text_soft.split())
    
    length_mismatch = _get_length_mismatch_penalty(ocr_len, candidate_len)
    
    # Combined score
    score = similarity * priority_mult * placeholder_mult * length_penalty * length_mismatch
    
    return min(score, 1.0)  # Cap at 1.0


def _filter_by_hints(
    candidates: List[SectionCandidate],
    section_number: Optional[str],
    section_name: Optional[str],
) -> tuple[List[SectionCandidate], List[str]]:
    """
    Filter candidates by section hints (soft matching).
    
    Returns (filtered_candidates, warnings).
    """
    if not section_number and not section_name:
        return candidates, []
    
    filtered = []
    warnings = []
    
    for candidate in candidates:
        # Match section_number
        if section_number:
            if not candidate.section_number:
                continue
            
            # Normalize numbers: "3", "03", "03)" all match
            num_normalized = section_number.strip().rstrip(")").lstrip("0") or "0"
            cand_normalized = candidate.section_number.strip().rstrip(")").lstrip("0") or "0"
            
            if num_normalized != cand_normalized:
                continue
        
        # Match section_name (tolerant)
        if section_name:
            if not candidate.section_name:
                continue
            
            # Case-insensitive, handle plurals: BANNER matches Banner, Banners
            name_lower = section_name.lower().rstrip("s")
            cand_lower = candidate.section_name.lower().rstrip("s")
            
            if name_lower not in cand_lower and cand_lower not in name_lower:
                continue
        
        filtered.append(candidate)
    
    # Generate warnings if hints didn't match anything
    if not filtered and (section_number or section_name):
        hint_str = f"number={section_number}" if section_number else ""
        if section_name:
            hint_str += f" name={section_name}" if hint_str else f"name={section_name}"
        warnings.append(f"Section hints ({hint_str}) did not match any candidates")
    
    return filtered or candidates, warnings


def select_best_section(
    ocr_text: str,
    candidates: List[SectionCandidate],
    normalize_strict_fn,
    normalize_soft_fn,
    section_number: Optional[str] = None,
    section_name: Optional[str] = None,
) -> SelectionResult:
    """
    Select the best matching section from candidates.
    
    Args:
        ocr_text: OCR text extracted from image
        candidates: List of section candidates from DOCX
        normalize_strict_fn: Function for strict normalization
        normalize_soft_fn: Function for soft normalization
        section_number: Optional hint for section number
        section_name: Optional hint for section name
    
    Returns:
        SelectionResult with chosen section and metadata
    """
    warnings = []
    
    # Clean OCR text (remove CTA brackets)
    ocr_cleaned = _remove_cta_brackets(ocr_text)
    ocr_strict = normalize_strict_fn(ocr_cleaned)
    ocr_soft = normalize_soft_fn(ocr_cleaned)
    
    # Check if OCR is too short for confident matching
    ocr_tokens = len(ocr_strict.split())
    ocr_chars = len(ocr_strict)
    
    # Filter by hints
    filtered_candidates, hint_warnings = _filter_by_hints(candidates, section_number, section_name)
    warnings.extend(hint_warnings)
    
    if not filtered_candidates:
        warnings.append("No candidates available after filtering")
        return SelectionResult(
            chosen_section=None,
            chosen_text="",
            score_top1=0.0,
            score_top2=0.0,
            delta=0.0,
            warnings=warnings,
            manual_required=True,
        )
    
    # Score all candidates
    scored = []
    for candidate in filtered_candidates:
        # Clean candidate text
        candidate_cleaned = _remove_cta_brackets(candidate.content_text)
        candidate_strict = normalize_strict_fn(candidate_cleaned)
        candidate_soft = normalize_soft_fn(candidate_cleaned)
        
        # Compute score
        score = _score_candidate(ocr_cleaned, candidate, ocr_soft, candidate_soft)
        
        # Check strict equality
        strict_equal = (ocr_strict == candidate_strict)
        
        scored.append((score, strict_equal, candidate, candidate_cleaned, candidate_strict))
    
    # Sort by score (descending), then by strict_equal (True first)
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    
    # Get top 2
    top1_score, top1_strict, top1_cand, top1_cleaned, top1_strict_text = scored[0]
    top2_score = scored[1][0] if len(scored) > 1 else 0.0
    
    delta = top1_score - top2_score
    
    # Check if all candidates have placeholders
    all_have_placeholders = all(_has_placeholder(c.content_text) for c in filtered_candidates)
    
    if all_have_placeholders:
        warnings.append("All candidates contain placeholders")
        return SelectionResult(
            chosen_section=top1_cand,
            chosen_text=top1_cleaned,
            score_top1=top1_score,
            score_top2=top2_score,
            delta=delta,
            warnings=warnings,
            manual_required=True,
            chosen_section_name=top1_cand.section_name,
            chosen_section_number=top1_cand.section_number,
        )
    
    # Confidence rules: check if OCR is too short
    if (ocr_tokens <= 3 or ocr_chars <= 15) and not top1_strict:
        warnings.append("OCR too short / ambiguous")
        return SelectionResult(
            chosen_section=top1_cand,
            chosen_text=top1_cleaned,
            score_top1=top1_score,
            score_top2=top2_score,
            delta=delta,
            warnings=warnings,
            manual_required=True,
            chosen_section_name=top1_cand.section_name,
            chosen_section_number=top1_cand.section_number,
        )
    
    # Delta rule: if top candidates are too close and no strict match
    if delta < 0.05 and not top1_strict:
        warnings.append("Ambiguous top candidates (delta < 0.05)")
        return SelectionResult(
            chosen_section=top1_cand,
            chosen_text=top1_cleaned,
            score_top1=top1_score,
            score_top2=top2_score,
            delta=delta,
            warnings=warnings,
            manual_required=True,
            chosen_section_name=top1_cand.section_name,
            chosen_section_number=top1_cand.section_number,
        )
    
    # Check uniqueness for auto-pass with strict_equal
    if top1_strict:
        # Count how many other candidates have strict_equal
        strict_equal_count = sum(1 for _, se, _, _, _ in scored if se)
        
        if strict_equal_count > 1:
            # Multiple strict matches - need to check delta
            if delta < 0.05:
                warnings.append("Multiple strict matches with low delta")
                return SelectionResult(
                    chosen_section=top1_cand,
                    chosen_text=top1_cleaned,
                    score_top1=top1_score,
                    score_top2=top2_score,
                    delta=delta,
                    warnings=warnings,
                    manual_required=True,
                    chosen_section_name=top1_cand.section_name,
                    chosen_section_number=top1_cand.section_number,
                )
    
    # Auto-pass: strict_equal and good delta
    manual_required = not top1_strict
    
    return SelectionResult(
        chosen_section=top1_cand,
        chosen_text=top1_cleaned,
        score_top1=top1_score,
        score_top2=top2_score,
        delta=delta,
        warnings=warnings,
        manual_required=manual_required,
        chosen_section_name=top1_cand.section_name,
        chosen_section_number=top1_cand.section_number,
    )
