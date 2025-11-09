"""Document comparison manager for comparing documents.

This module provides professional document comparison capabilities including:
- Content comparison with similarity scoring
- Structure comparison
- Difference identification
- Common element detection

Architecture:
- Separates comparison logic from task execution
- Provides clean API for document comparison operations
- Handles storage and retrieval of comparison results
- Supports multiple comparison types and configurations
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..config import settings
from ..database import db_manager
from ..managers.logging_manager import get_logger

logger = get_logger(prefix="[DocumentComparisonManager]")


class DocumentComparisonManager:
    """Professional manager for document comparison operations."""

    def __init__(self):
        """Initialize the document comparison manager."""
        self.enabled = settings.DOCLING_ENABLED
        if not self.enabled:
            logger.warning("Docling integration disabled, comparison features unavailable")

    def compare_content(
        self,
        doc1: Dict[str, Any],
        doc2: Dict[str, Any],
    ) -> Tuple[float, List[str]]:
        """Compare document content.

        Args:
            doc1: First document content
            doc2: Second document content

        Returns:
            Tuple of (similarity_score, differences_list)
        """
        try:
            content1 = doc1.get("content", "").lower()
            content2 = doc2.get("content", "").lower()

            # Simple similarity based on common words
            words1 = set(content1.split())
            words2 = set(content2.split())

            if not words1 or not words2:
                return 0.0, ["One document is empty"]

            intersection = words1.intersection(words2)
            union = words1.union(words2)

            similarity = len(intersection) / len(union) if union else 0.0

            # Find key differences
            differences = []
            unique_to_1 = words1 - words2
            unique_to_2 = words2 - words1

            if unique_to_1:
                differences.append(
                    f"Words only in {doc1.get('filename')}: {list(unique_to_1)[:10]}"
                )
            if unique_to_2:
                differences.append(
                    f"Words only in {doc2.get('filename')}: {list(unique_to_2)[:10]}"
                )

            return similarity, differences

        except Exception as e:
            logger.error(f"Error comparing content: {e}", exc_info=True)
            raise

    def compare_structure(
        self,
        doc1: Dict[str, Any],
        doc2: Dict[str, Any],
    ) -> Tuple[float, List[str]]:
        """Compare document structure.

        Args:
            doc1: First document metadata
            doc2: Second document metadata

        Returns:
            Tuple of (similarity_score, differences_list)
        """
        try:
            metadata1 = doc1.get("metadata", {})
            metadata2 = doc2.get("metadata", {})

            # Compare basic structure elements
            structure_score = 0.0
            total_elements = 0
            differences = []

            # Compare page count
            pages1 = metadata1.get("page_count", 1)
            pages2 = metadata2.get("page_count", 1)
            if pages1 == pages2:
                structure_score += 1
            else:
                differences.append(f"Different page counts: {pages1} vs {pages2}")
            total_elements += 1

            # Compare table presence
            tables1 = metadata1.get("has_tables", False)
            tables2 = metadata2.get("has_tables", False)
            if tables1 == tables2:
                structure_score += 1
            else:
                differences.append(f"Table presence differs: {tables1} vs {tables2}")
            total_elements += 1

            # Compare image presence
            images1 = metadata1.get("has_images", False)
            images2 = metadata2.get("has_images", False)
            if images1 == images2:
                structure_score += 1
            else:
                differences.append(f"Image presence differs: {images1} vs {images2}")
            total_elements += 1

            similarity = structure_score / total_elements if total_elements > 0 else 0.0

            return similarity, differences

        except Exception as e:
            logger.error(f"Error comparing structure: {e}", exc_info=True)
            raise

    async def compare_documents(
        self,
        doc1: Dict[str, Any],
        doc2: Dict[str, Any],
        comparison_type: str = "content",
    ) -> Dict[str, Any]:
        """Compare two documents comprehensively.

        Args:
            doc1: First document
            doc2: Second document
            comparison_type: Type of comparison ('content', 'structure', 'both')

        Returns:
            Comparison results
        """
        try:
            comparison_result = {
                "document_1": {
                    "id": doc1.get("document_id"),
                    "filename": doc1.get("filename"),
                },
                "document_2": {
                    "id": doc2.get("document_id"),
                    "filename": doc2.get("filename"),
                },
                "comparison_type": comparison_type,
                "similarity_score": 0.0,
                "differences": [],
                "common_elements": [],
            }

            if comparison_type in ["content", "both"]:
                content_similarity, content_diffs = self.compare_content(doc1, doc2)
                comparison_result["content_similarity"] = content_similarity
                comparison_result["content_differences"] = content_diffs

            if comparison_type in ["structure", "both"]:
                structure_similarity, structure_diffs = self.compare_structure(doc1, doc2)
                comparison_result["structure_similarity"] = structure_similarity
                comparison_result["structure_differences"] = structure_diffs

            # Calculate overall similarity
            if comparison_type == "both":
                comparison_result["similarity_score"] = (
                    comparison_result["content_similarity"] * 0.7 +
                    comparison_result["structure_similarity"] * 0.3
                )
            else:
                similarity_key = f"{comparison_type}_similarity"
                comparison_result["similarity_score"] = comparison_result.get(similarity_key, 0.0)

            logger.info(
                f"Compared documents: {comparison_result['similarity_score']:.2f} similarity",
                extra={
                    "doc1": doc1.get("document_id"),
                    "doc2": doc2.get("document_id"),
                    "type": comparison_type,
                }
            )

            return comparison_result

        except Exception as e:
            logger.error(f"Error in document comparison: {e}", exc_info=True)
            raise

    async def store_comparison(self, comparison: Dict[str, Any]) -> None:
        """Store document comparison results in database.

        Args:
            comparison: Comparison results
        """
        try:
            collection = db_manager.get_collection("document_comparisons")

            comparison["created_at"] = datetime.now(timezone.utc)

            await collection.insert_one(comparison)

            logger.info(
                "Stored document comparison",
                extra={
                    "doc1": comparison["document_1"]["id"],
                    "doc2": comparison["document_2"]["id"],
                }
            )

        except Exception as e:
            logger.error(f"Failed to store document comparison: {e}", exc_info=True)
            raise


# Global instance
document_comparison_manager = DocumentComparisonManager()
