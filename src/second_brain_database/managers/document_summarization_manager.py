"""Document summarization manager for creating document summaries.

This module provides professional document summarization capabilities including:
- Extractive summarization using key sentences
- Abstractive summarization (with LLM integration)
- Key point extraction
- Summary storage and retrieval

Architecture:
- Separates summarization logic from task execution
- Provides clean API for summarization operations
- Handles storage and retrieval of summaries
- Supports multiple summarization strategies
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..config import settings
from ..database import db_manager
from ..managers.logging_manager import get_logger

logger = get_logger(prefix="[DocumentSummarizationManager]")


class DocumentSummarizationManager:
    """Professional manager for document summarization operations."""

    def __init__(self):
        """Initialize the document summarization manager."""
        self.enabled = settings.DOCLING_ENABLED
        if not self.enabled:
            logger.warning("Docling integration disabled, summarization features unavailable")

    def extractive_summarization(
        self,
        content: str,
        max_length: int = 300,
    ) -> Tuple[str, List[str]]:
        """Perform extractive summarization using key sentences.

        Args:
            content: Document content to summarize
            max_length: Maximum summary length in words

        Returns:
            Tuple of (summary_text, key_points)
        """
        try:
            sentences = [s.strip() for s in content.split('.') if s.strip()]

            if not sentences:
                return content[:max_length * 5], []  # Fallback

            # Score sentences based on position and length
            scored_sentences = []
            for i, sentence in enumerate(sentences):
                # Position score (prefer first and last sentences)
                position_score = 1.0
                if i == 0 or i == len(sentences) - 1:
                    position_score = 1.5

                # Length score (prefer medium-length sentences)
                word_count = len(sentence.split())
                length_score = 1.0
                if 5 <= word_count <= 20:
                    length_score = 1.2

                # Keyword score (sentences with important words)
                keywords = ["important", "key", "summary", "conclusion", "result"]
                keyword_score = 1.0 + sum(sentence.lower().count(kw) * 0.1 for kw in keywords)

                total_score = position_score * length_score * keyword_score
                scored_sentences.append((sentence, total_score))

            # Sort by score and select top sentences
            scored_sentences.sort(key=lambda x: x[1], reverse=True)

            selected_sentences = []
            current_length = 0

            for sentence, _ in scored_sentences:
                sentence_length = len(sentence.split())
                if current_length + sentence_length <= max_length:
                    selected_sentences.append(sentence)
                    current_length += sentence_length
                else:
                    break

            # Sort selected sentences by original order
            original_order = []
            for sentence in sentences:
                if sentence in selected_sentences:
                    original_order.append(sentence)

            summary = '. '.join(original_order)
            key_points = [s[:100] + "..." if len(s) > 100 else s for s in original_order[:5]]

            logger.info(
                f"Generated extractive summary: {current_length} words from {len(content.split())} words",
                extra={"compression_ratio": current_length / len(content.split()) if content.split() else 0}
            )

            return summary, key_points

        except Exception as e:
            logger.error(f"Error in extractive summarization: {e}", exc_info=True)
            raise

    async def abstractive_summarization(
        self,
        content: str,
        max_length: int = 300,
        llm_manager=None,
    ) -> Tuple[str, List[str]]:
        """Perform abstractive summarization using LLM.

        Args:
            content: Document content to summarize
            max_length: Maximum summary length in words
            llm_manager: Optional LLM manager for abstractive summarization

        Returns:
            Tuple of (summary_text, key_points)
        """
        try:
            # If no LLM manager provided, fall back to extractive
            if llm_manager is None:
                logger.warning("No LLM manager provided, using extractive summarization")
                return self.extractive_summarization(content, max_length)

            # Use LLM for abstractive summarization
            prompt = f"""Summarize the following document in no more than {max_length} words. 
            Focus on the key points and main ideas.
            
            Document:
            {content[:4000]}  # Limit to avoid token limits
            
            Summary:"""

            summary = await llm_manager.generate_completion(prompt)
            
            # Extract key points from summary
            key_points = [s.strip() for s in summary.split('.') if s.strip()][:5]

            logger.info(
                "Generated abstractive summary using LLM",
                extra={"summary_length": len(summary.split())}
            )

            return summary, key_points

        except Exception as e:
            logger.error(f"Error in abstractive summarization: {e}", exc_info=True)
            # Fall back to extractive on error
            return self.extractive_summarization(content, max_length)

    async def summarize_document(
        self,
        content: str,
        summary_type: str = "extractive",
        max_length: int = 300,
        llm_manager=None,
    ) -> Dict[str, Any]:
        """Generate document summary.

        Args:
            content: Document content
            summary_type: Type of summarization ('extractive', 'abstractive')
            max_length: Maximum summary length in words
            llm_manager: Optional LLM manager for abstractive summarization

        Returns:
            Summary results
        """
        try:
            summary_result = {
                "summary_type": summary_type,
                "original_length": len(content.split()),
                "summary_length": 0,
                "summary": "",
                "key_points": [],
                "compression_ratio": 0.0,
            }

            if summary_type == "extractive":
                summary, key_points = self.extractive_summarization(content, max_length)
            elif summary_type == "abstractive":
                summary, key_points = await self.abstractive_summarization(content, max_length, llm_manager)
            else:
                raise ValueError(f"Unsupported summary type: {summary_type}")

            summary_result["summary"] = summary
            summary_result["key_points"] = key_points
            summary_result["summary_length"] = len(summary.split())
            summary_result["compression_ratio"] = (
                summary_result["summary_length"] / summary_result["original_length"]
                if summary_result["original_length"] > 0 else 0.0
            )

            logger.info(
                f"Generated {summary_type} summary",
                extra={
                    "type": summary_type,
                    "compression": summary_result["compression_ratio"],
                }
            )

            return summary_result

        except Exception as e:
            logger.error(f"Error in summarization: {e}", exc_info=True)
            raise

    async def store_summary(
        self,
        document_id: str,
        summary: Dict[str, Any],
    ) -> None:
        """Store document summary in database.

        Args:
            document_id: Document ID
            summary: Summary results
        """
        try:
            collection = db_manager.get_collection("document_summaries")

            summary["document_id"] = document_id
            summary["created_at"] = datetime.now(timezone.utc)

            await collection.insert_one(summary)

            logger.info(
                f"Stored summary for document {document_id}",
                extra={"document_id": document_id, "type": summary["summary_type"]}
            )

        except Exception as e:
            logger.error(f"Failed to store document summary: {e}", exc_info=True)
            raise


# Global instance
document_summarization_manager = DocumentSummarizationManager()
