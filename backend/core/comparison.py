"""Case comparison helpers for multi-document legal review."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


class ComparisonService:
    """Build structured comparisons for two archived cases."""

    def compare_cases(self, left_case: dict[str, Any], right_case: dict[str, Any]) -> dict[str, Any]:
        """Compare document bodies and legal conclusions for two cases."""

        left_text = self._document_text(left_case)
        right_text = self._document_text(right_case)
        left_summary = str(left_case.get("legal_summary") or left_case.get("summary") or "")
        right_summary = str(right_case.get("legal_summary") or right_case.get("summary") or "")
        left_recommendations = str(left_case.get("recommendations") or "")
        right_recommendations = str(right_case.get("recommendations") or "")

        return {
            "left_case": self._case_meta(left_case),
            "right_case": self._case_meta(right_case),
            "document": {
                "similarity": round(self._ratio(left_text, right_text), 4),
                "left_length": len(left_text),
                "right_length": len(right_text),
                "highlights": self._diff_highlights(left_text, right_text),
            },
            "analysis": {
                "summary_similarity": round(self._ratio(left_summary, right_summary), 4),
                "recommendations_similarity": round(self._ratio(left_recommendations, right_recommendations), 4),
                "laws_only_left": self._difference(
                    left_case.get("relevant_laws") or [],
                    right_case.get("relevant_laws") or [],
                    keys=("title", "article"),
                ),
                "laws_only_right": self._difference(
                    right_case.get("relevant_laws") or [],
                    left_case.get("relevant_laws") or [],
                    keys=("title", "article"),
                ),
                "practice_only_left": self._difference(
                    left_case.get("court_practice") or [],
                    right_case.get("court_practice") or [],
                    keys=("case", "court"),
                ),
                "practice_only_right": self._difference(
                    right_case.get("court_practice") or [],
                    left_case.get("court_practice") or [],
                    keys=("case", "court"),
                ),
            },
        }

    @staticmethod
    def _document_text(case_data: dict[str, Any]) -> str:
        return str(case_data.get("anonymized_text") or case_data.get("original_text") or "")

    @staticmethod
    def _ratio(left: str, right: str) -> float:
        if not left and not right:
            return 1.0
        return SequenceMatcher(None, left, right).ratio()

    @staticmethod
    def _case_meta(case_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": case_data.get("id"),
            "filename": case_data.get("filename"),
            "created_at": case_data.get("created_at"),
            "status": case_data.get("status"),
            "source": case_data.get("source"),
        }

    @staticmethod
    def _difference(
        left_items: list[dict[str, Any]],
        right_items: list[dict[str, Any]],
        *,
        keys: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        right_keys = {tuple(str(item.get(key) or "") for key in keys) for item in right_items}
        return [
            item
            for item in left_items
            if tuple(str(item.get(key) or "") for key in keys) not in right_keys
        ][:10]

    @staticmethod
    def _diff_highlights(left: str, right: str) -> list[dict[str, str]]:
        left_lines = [line.strip() for line in left.splitlines() if line.strip()]
        right_lines = [line.strip() for line in right.splitlines() if line.strip()]
        matcher = SequenceMatcher(None, left_lines, right_lines)
        highlights: list[dict[str, str]] = []
        for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
            if tag == "equal":
                continue
            highlights.append(
                {
                    "type": tag,
                    "left": "\n".join(left_lines[left_start:left_end])[:800],
                    "right": "\n".join(right_lines[right_start:right_end])[:800],
                }
            )
            if len(highlights) >= 12:
                break
        return highlights


comparison_service = ComparisonService()
