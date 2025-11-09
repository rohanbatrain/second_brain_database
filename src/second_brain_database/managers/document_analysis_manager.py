"""Document analysis manager for OCR, layout, and quality analysis.

This module provides professional document analysis capabilities including:
- OCR confidence scoring
- Layout analysis (basic, detailed, comprehensive)
- Quality assessment (OCR, content integrity, structure, readability)
- Document complexity analysis

Architecture:
- Separates analysis logic from task execution
- Provides clean API for document analysis operations
- Handles storage and retrieval of analysis results
- Supports multiple analysis depths and configurations
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..config import settings
from ..database import db_manager
from ..managers.logging_manager import get_logger

logger = get_logger(prefix="[DocumentAnalysisManager]")


class DocumentAnalysisManager:
    """Professional manager for document analysis operations."""

    def __init__(self):
        """Initialize the document analysis manager."""
        self.enabled = settings.DOCLING_ENABLED
        if not self.enabled:
            logger.warning("Docling integration disabled, analysis features unavailable")

    def calculate_ocr_confidence(self, result: Dict[str, Any]) -> float:
        """Calculate OCR confidence score based on processing results.

        Args:
            result: Processing result with metadata and content

        Returns:
            Confidence score between 0.0 and 1.0
        """
        try:
            metadata = result.get("metadata", {})
            content = result.get("content", "")

            # Base confidence
            confidence = 0.8

            # Adjust based on content characteristics
            if metadata.get("has_tables"):
                confidence += 0.1  # Tables suggest good OCR

            if len(content.split()) > 100:
                confidence += 0.05  # Longer documents suggest better OCR

            # Check for OCR artifacts
            ocr_artifacts = ["|", "_", "•", "·"]
            artifact_count = sum(content.count(artifact) for artifact in ocr_artifacts)

            if artifact_count > len(content) * 0.01:  # More than 1% artifacts
                confidence -= 0.2

            return max(0.0, min(1.0, confidence))

        except Exception as e:
            logger.error(f"Error calculating OCR confidence: {e}")
            return 0.5  # Default confidence if calculation fails

    async def analyze_layout(
        self,
        doc_content: Dict[str, Any],
        depth: str = "detailed",
    ) -> Dict[str, Any]:
        """Perform layout analysis on document content.

        Args:
            doc_content: Document content with metadata
            depth: Analysis depth ('basic', 'detailed', 'comprehensive')

        Returns:
            Layout analysis results
        """
        try:
            if depth == "basic":
                return self._basic_layout_analysis(doc_content)
            elif depth == "detailed":
                return self._detailed_layout_analysis(doc_content)
            elif depth == "comprehensive":
                return self._comprehensive_layout_analysis(doc_content)
            else:
                raise ValueError(f"Invalid analysis depth: {depth}")

        except Exception as e:
            logger.error(f"Error in layout analysis: {e}", exc_info=True)
            raise

    def _basic_layout_analysis(self, doc_content: Dict[str, Any]) -> Dict[str, Any]:
        """Perform basic layout analysis.

        Args:
            doc_content: Document content

        Returns:
            Basic layout analysis results
        """
        content = doc_content.get("content", "")
        metadata = doc_content.get("metadata", {})

        return {
            "page_count": metadata.get("page_count", 1),
            "has_tables": metadata.get("has_tables", False),
            "has_images": metadata.get("has_images", False),
            "content_length": len(content),
            "estimated_reading_time": len(content.split()) // 200,  # ~200 words per minute
        }

    def _detailed_layout_analysis(self, doc_content: Dict[str, Any]) -> Dict[str, Any]:
        """Perform detailed layout analysis.

        Args:
            doc_content: Document content

        Returns:
            Detailed layout analysis results
        """
        content = doc_content.get("content", "")
        lines = content.split('\n')

        analysis = self._basic_layout_analysis(doc_content)
        analysis.update({
            "line_count": len(lines),
            "avg_line_length": sum(len(line) for line in lines) / len(lines) if lines else 0,
            "heading_count": sum(1 for line in lines if line.strip().startswith('#')),
            "list_items": sum(1 for line in lines if line.strip().startswith(('- ', '* ', '1. '))),
            "code_blocks": content.count('```'),
            "links": content.count('[') // 2,  # Approximate link count
        })

        return analysis

    def _comprehensive_layout_analysis(self, doc_content: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive layout analysis.

        Args:
            doc_content: Document content

        Returns:
            Comprehensive layout analysis results
        """
        analysis = self._detailed_layout_analysis(doc_content)
        content = doc_content.get("content", "")

        # Advanced analysis
        analysis.update({
            "paragraph_count": len([p for p in content.split('\n\n') if p.strip()]),
            "sentence_count": len(content.split('.')),
            "word_count": len(content.split()),
            "unique_words": len(set(content.lower().split())),
            "complexity_score": self._calculate_complexity_score(content),
        })

        return analysis

    def _calculate_complexity_score(self, content: str) -> float:
        """Calculate document complexity score.

        Args:
            content: Document content

        Returns:
            Complexity score between 0.0 and 1.0
        """
        words = content.split()
        sentences = content.split('.')

        if not words or not sentences:
            return 0.0

        avg_words_per_sentence = len(words) / len(sentences)
        unique_word_ratio = len(set(words)) / len(words)

        # Complexity based on sentence length and vocabulary diversity
        complexity = (avg_words_per_sentence * 0.6) + (unique_word_ratio * 0.4)

        return min(1.0, complexity)

    def extract_layout_elements(self, doc_content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract layout elements from document.

        Args:
            doc_content: Document content

        Returns:
            List of layout elements with metadata
        """
        content = doc_content.get("content", "")
        lines = content.split('\n')

        elements = []
        current_element = None

        for i, line in enumerate(lines):
            line = line.strip()

            # Detect headings
            if line.startswith('#'):
                if current_element:
                    elements.append(current_element)
                current_element = {
                    "type": "heading",
                    "level": len(line) - len(line.lstrip('#')),
                    "content": line.lstrip('#').strip(),
                    "line_number": i + 1,
                }

            # Detect lists
            elif line.startswith(('- ', '* ', '1. ')):
                if current_element and current_element["type"] != "list":
                    elements.append(current_element)
                if not current_element or current_element["type"] != "list":
                    current_element = {
                        "type": "list",
                        "items": [],
                        "line_number": i + 1,
                    }
                current_element["items"].append(line)

            # Detect code blocks
            elif line.startswith('```'):
                if current_element:
                    elements.append(current_element)
                current_element = {
                    "type": "code_block",
                    "language": line.replace('```', '').strip(),
                    "content": "",
                    "line_number": i + 1,
                }

            # Detect paragraphs
            elif line and not current_element:
                current_element = {
                    "type": "paragraph",
                    "content": line,
                    "line_number": i + 1,
                }

        if current_element:
            elements.append(current_element)

        return elements

    def analyze_element_relationships(self, doc_content: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze relationships between layout elements.

        Args:
            doc_content: Document content

        Returns:
            Element relationship analysis
        """
        elements = self.extract_layout_elements(doc_content)

        relationships = {
            "heading_hierarchy": [],
            "list_groupings": [],
            "code_paragraph_associations": [],
        }

        # Analyze heading hierarchy
        current_hierarchy = []
        for elem in elements:
            if elem["type"] == "heading":
                level = elem["level"]
                while len(current_hierarchy) >= level:
                    current_hierarchy.pop()
                current_hierarchy.append(elem["content"])
                relationships["heading_hierarchy"].append(current_hierarchy.copy())

        return relationships

    async def analyze_quality(self, doc_content: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze document quality including OCR confidence and content integrity.

        Args:
            doc_content: Document content with metadata

        Returns:
            Quality analysis results
        """
        try:
            quality_scores = {
                "overall_score": 0.0,
                "ocr_confidence": 0.0,
                "content_integrity": 0.0,
                "structure_quality": 0.0,
                "readability_score": 0.0,
                "issues": [],
            }

            # OCR Quality Analysis
            quality_scores["ocr_confidence"] = self._analyze_ocr_quality(doc_content)

            # Content Integrity Analysis
            quality_scores["content_integrity"] = self._analyze_content_integrity(doc_content)

            # Structure Quality Analysis
            quality_scores["structure_quality"] = self._analyze_structure_quality(doc_content)

            # Readability Analysis
            quality_scores["readability_score"] = self._analyze_readability(doc_content)

            # Calculate overall score
            quality_scores["overall_score"] = (
                quality_scores["ocr_confidence"] * 0.3 +
                quality_scores["content_integrity"] * 0.3 +
                quality_scores["structure_quality"] * 0.2 +
                quality_scores["readability_score"] * 0.2
            )

            # Identify issues
            quality_scores["issues"] = self._identify_quality_issues(quality_scores)

            return quality_scores

        except Exception as e:
            logger.error(f"Error in quality analysis: {e}", exc_info=True)
            raise

    def _analyze_ocr_quality(self, doc_content: Dict[str, Any]) -> float:
        """Analyze OCR quality.

        Args:
            doc_content: Document content

        Returns:
            OCR quality score
        """
        metadata = doc_content.get("metadata", {})
        content = doc_content.get("content", "")

        score = 0.8  # Base score

        # Check if OCR was performed
        if metadata.get("processing_options", {}).get("ocr_enabled"):
            score += 0.1

        # Check for OCR artifacts
        artifacts = ["|", "_", "•", "·", "€", "™"]
        artifact_ratio = sum(content.count(a) for a in artifacts) / len(content) if content else 0

        if artifact_ratio > 0.005:  # More than 0.5% artifacts
            score -= min(0.3, artifact_ratio * 50)

        return max(0.0, min(1.0, score))

    def _analyze_content_integrity(self, doc_content: Dict[str, Any]) -> float:
        """Analyze content integrity.

        Args:
            doc_content: Document content

        Returns:
            Content integrity score
        """
        content = doc_content.get("content", "")
        metadata = doc_content.get("metadata", {})

        score = 1.0

        # Check for truncated content
        if len(content) < 100 and metadata.get("page_count", 1) > 1:
            score -= 0.3

        # Check for empty pages
        if content.strip() == "":
            score -= 0.5

        # Check for encoding issues
        if "�" in content:  # Replacement character
            score -= 0.2

        return max(0.0, score)

    def _analyze_structure_quality(self, doc_content: Dict[str, Any]) -> float:
        """Analyze document structure quality.

        Args:
            doc_content: Document content

        Returns:
            Structure quality score
        """
        content = doc_content.get("content", "")
        metadata = doc_content.get("metadata", {})

        score = 0.7

        # Check for tables
        if metadata.get("has_tables"):
            score += 0.2

        # Check for headings
        if content.count('#') > 0:
            score += 0.1

        # Check for lists
        list_markers = content.count('- ') + content.count('* ') + content.count('1. ')
        if list_markers > 0:
            score += 0.1

        return min(1.0, score)

    def _analyze_readability(self, doc_content: Dict[str, Any]) -> float:
        """Analyze document readability.

        Args:
            doc_content: Document content

        Returns:
            Readability score
        """
        content = doc_content.get("content", "")

        if not content:
            return 0.0

        words = content.split()
        sentences = [s.strip() for s in content.split('.') if s.strip()]

        if not words or not sentences:
            return 0.0

        # Average words per sentence
        avg_words_per_sentence = len(words) / len(sentences)

        # Ideal range: 10-20 words per sentence
        if 10 <= avg_words_per_sentence <= 20:
            readability = 1.0
        elif avg_words_per_sentence < 10:
            readability = 0.8  # Too simple
        else:
            readability = max(0.3, 1.0 - (avg_words_per_sentence - 20) * 0.05)

        return readability

    def _identify_quality_issues(self, quality_scores: Dict[str, Any]) -> List[str]:
        """Identify specific quality issues.

        Args:
            quality_scores: Quality score dictionary

        Returns:
            List of identified issues
        """
        issues = []

        if quality_scores["ocr_confidence"] < 0.7:
            issues.append("Low OCR confidence - document may have scanning artifacts")

        if quality_scores["content_integrity"] < 0.8:
            issues.append("Content integrity issues - possible truncation or encoding problems")

        if quality_scores["structure_quality"] < 0.6:
            issues.append("Poor document structure - limited formatting detected")

        if quality_scores["readability_score"] < 0.7:
            issues.append("Low readability - sentences may be too long or complex")

        if quality_scores["overall_score"] < 0.6:
            issues.append("Overall document quality is poor")

        return issues

    async def store_analysis(
        self,
        document_id: str,
        analysis: Dict[str, Any],
        analysis_type: str,
    ) -> None:
        """Store analysis results in database.

        Args:
            document_id: Document ID
            analysis: Analysis results
            analysis_type: Type of analysis ('layout', 'quality', etc.)
        """
        try:
            collection_name = f"document_{analysis_type}_analysis"
            collection = db_manager.get_collection(collection_name)

            analysis["document_id"] = document_id
            analysis["created_at"] = datetime.now(timezone.utc)

            await collection.insert_one(analysis)

            logger.info(
                f"Stored {analysis_type} analysis for document {document_id}",
                extra={"document_id": document_id, "analysis_type": analysis_type}
            )

        except Exception as e:
            logger.error(f"Failed to store {analysis_type} analysis: {e}", exc_info=True)
            raise


# Global instance
document_analysis_manager = DocumentAnalysisManager()
