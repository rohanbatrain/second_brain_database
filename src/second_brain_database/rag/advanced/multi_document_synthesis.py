"""
Advanced RAG Features - Multi-Document Synthesis

Sophisticated multi-document synthesis system that can combine information
from multiple documents, detect contradictions, synthesize comprehensive 
answers, and provide source attribution for complex queries.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.rag.core.exceptions import RAGError
from second_brain_database.rag.core.types import DocumentChunk, QueryRequest, QueryResponse

logger = get_logger()


class SynthesisStrategy(str, Enum):
    """Document synthesis strategies."""
    CHRONOLOGICAL = "chronological"     # Order by time/sequence
    CONSENSUS = "consensus"              # Find common themes
    COMPARATIVE = "comparative"          # Compare and contrast
    HIERARCHICAL = "hierarchical"       # By importance/relevance
    COMPREHENSIVE = "comprehensive"     # All-encompassing synthesis


class ContradictionLevel(str, Enum):
    """Levels of contradiction between sources."""
    NONE = "none"
    MINOR = "minor"           # Small discrepancies
    MODERATE = "moderate"     # Significant differences
    MAJOR = "major"           # Direct contradictions


@dataclass
class DocumentSource:
    """Information about a document source."""
    document_id: str
    filename: str
    title: str
    author: Optional[str] = None
    date: Optional[str] = None
    reliability_score: float = 1.0
    source_type: str = "document"  # document, webpage, article, etc.


@dataclass
class SynthesizedChunk:
    """A chunk of synthesized information from multiple sources."""
    content: str
    sources: List[DocumentSource]
    confidence_score: float
    synthesis_method: str
    contradictions: List[Dict[str, Any]]
    supporting_evidence: List[str]


@dataclass
class SynthesisResult:
    """Result of multi-document synthesis."""
    synthesized_answer: str
    chunks: List[SynthesizedChunk]
    source_attribution: Dict[str, List[str]]
    contradiction_analysis: Dict[str, Any]
    confidence_score: float
    synthesis_strategy: SynthesisStrategy
    metadata: Dict[str, Any]


class MultiDocumentSynthesizer:
    """
    Advanced multi-document synthesis system.
    
    Combines information from multiple documents to create comprehensive,
    well-sourced answers with contradiction detection and source attribution.
    """
    
    def __init__(
        self,
        default_strategy: SynthesisStrategy = SynthesisStrategy.COMPREHENSIVE,
        min_sources: int = 2,
        max_sources: int = 10,
        confidence_threshold: float = 0.6
    ):
        """
        Initialize multi-document synthesizer.
        
        Args:
            default_strategy: Default synthesis strategy
            min_sources: Minimum number of sources for synthesis
            max_sources: Maximum number of sources to consider
            confidence_threshold: Minimum confidence for synthesis
        """
        self.default_strategy = default_strategy
        self.min_sources = min_sources
        self.max_sources = max_sources
        self.confidence_threshold = confidence_threshold
        
        logger.info(f"Initialized multi-document synthesizer with {default_strategy} strategy")
    
    async def synthesize_documents(
        self,
        chunks: List[DocumentChunk],
        query: str,
        strategy: Optional[SynthesisStrategy] = None,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> SynthesisResult:
        """
        Synthesize information from multiple document chunks.
        
        Args:
            chunks: List of relevant document chunks
            query: Original user query
            strategy: Synthesis strategy to use
            user_preferences: User preferences for synthesis
            
        Returns:
            Comprehensive synthesis result
        """
        try:
            strategy = strategy or self.default_strategy
            logger.info(f"Starting multi-document synthesis with {strategy} strategy")
            
            if len(chunks) < self.min_sources:
                raise RAGError(f"Insufficient sources for synthesis: {len(chunks)} < {self.min_sources}")
            
            # Limit chunks to max sources
            chunks = chunks[:self.max_sources]
            
            # Extract document sources
            sources = await self._extract_document_sources(chunks)
            
            # Group chunks by document for better analysis
            doc_groups = await self._group_chunks_by_document(chunks)
            
            # Detect contradictions between sources
            contradictions = await self._detect_contradictions(doc_groups, query)
            
            # Apply synthesis strategy
            synthesized_chunks = await self._apply_synthesis_strategy(
                doc_groups, query, strategy, contradictions
            )
            
            # Generate final synthesized answer
            synthesized_answer = await self._generate_synthesized_answer(
                synthesized_chunks, query, strategy
            )
            
            # Create source attribution
            source_attribution = self._create_source_attribution(synthesized_chunks)
            
            # Calculate overall confidence
            confidence_score = self._calculate_synthesis_confidence(
                synthesized_chunks, contradictions
            )
            
            # Prepare contradiction analysis
            contradiction_analysis = self._analyze_contradictions(contradictions)
            
            result = SynthesisResult(
                synthesized_answer=synthesized_answer,
                chunks=synthesized_chunks,
                source_attribution=source_attribution,
                contradiction_analysis=contradiction_analysis,
                confidence_score=confidence_score,
                synthesis_strategy=strategy,
                metadata={
                    "total_sources": len(sources),
                    "total_chunks": len(chunks),
                    "query": query,
                    "synthesis_timestamp": datetime.utcnow().isoformat()
                }
            )
            
            logger.info(
                f"Completed synthesis with {len(synthesized_chunks)} chunks, "
                f"confidence: {confidence_score:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Multi-document synthesis failed: {e}")
            raise RAGError(f"Synthesis failed: {e}")
    
    async def _extract_document_sources(
        self, 
        chunks: List[DocumentChunk]
    ) -> List[DocumentSource]:
        """Extract unique document sources from chunks."""
        sources = {}
        
        for chunk in chunks:
            doc_id = chunk.document_id
            if doc_id not in sources:
                # Extract source information from chunk metadata
                metadata = chunk.metadata or {}
                
                source = DocumentSource(
                    document_id=doc_id,
                    filename=metadata.get("filename", f"Document {doc_id}"),
                    title=metadata.get("title", metadata.get("filename", "Unknown")),
                    author=metadata.get("author"),
                    date=metadata.get("creation_date") or metadata.get("date"),
                    reliability_score=metadata.get("reliability_score", 1.0),
                    source_type=metadata.get("source_type", "document")
                )
                sources[doc_id] = source
        
        return list(sources.values())
    
    async def _group_chunks_by_document(
        self, 
        chunks: List[DocumentChunk]
    ) -> Dict[str, List[DocumentChunk]]:
        """Group chunks by their source document."""
        groups = defaultdict(list)
        
        for chunk in chunks:
            groups[chunk.document_id].append(chunk)
        
        # Sort chunks within each document by position
        for doc_id in groups:
            groups[doc_id].sort(key=lambda x: x.chunk_index)
        
        return dict(groups)
    
    async def _detect_contradictions(
        self,
        doc_groups: Dict[str, List[DocumentChunk]],
        query: str
    ) -> List[Dict[str, Any]]:
        """Detect contradictions between different documents."""
        contradictions = []
        
        # Get all document pairs
        doc_ids = list(doc_groups.keys())
        for i, doc_id1 in enumerate(doc_ids):
            for doc_id2 in doc_ids[i+1:]:
                # Compare chunks from different documents
                chunks1 = doc_groups[doc_id1]
                chunks2 = doc_groups[doc_id2]
                
                contradiction = await self._compare_document_chunks(
                    chunks1, chunks2, doc_id1, doc_id2, query
                )
                
                if contradiction:
                    contradictions.append(contradiction)
        
        return contradictions
    
    async def _compare_document_chunks(
        self,
        chunks1: List[DocumentChunk],
        chunks2: List[DocumentChunk],
        doc_id1: str,
        doc_id2: str,
        query: str
    ) -> Optional[Dict[str, Any]]:
        """Compare chunks from two documents for contradictions."""
        # Simple contradiction detection based on opposing keywords
        # In production, use semantic similarity and NLI models
        
        text1 = " ".join(chunk.content for chunk in chunks1)
        text2 = " ".join(chunk.content for chunk in chunks2)
        
        # Look for opposing patterns
        opposing_pairs = [
            ("true", "false"), ("correct", "incorrect"), ("yes", "no"),
            ("increase", "decrease"), ("positive", "negative"),
            ("effective", "ineffective"), ("safe", "unsafe"),
            ("recommend", "not recommend"), ("should", "should not")
        ]
        
        contradictions_found = []
        
        for word1, word2 in opposing_pairs:
            if (word1 in text1.lower() and word2 in text2.lower()) or \
               (word2 in text1.lower() and word1 in text2.lower()):
                contradictions_found.append({
                    "type": "opposing_terms",
                    "terms": [word1, word2],
                    "document1": doc_id1,
                    "document2": doc_id2
                })
        
        if contradictions_found:
            return {
                "document1": doc_id1,
                "document2": doc_id2,
                "level": ContradictionLevel.MODERATE,
                "contradictions": contradictions_found,
                "text1_sample": text1[:200],
                "text2_sample": text2[:200]
            }
        
        return None
    
    async def _apply_synthesis_strategy(
        self,
        doc_groups: Dict[str, List[DocumentChunk]],
        query: str,
        strategy: SynthesisStrategy,
        contradictions: List[Dict[str, Any]]
    ) -> List[SynthesizedChunk]:
        """Apply the specified synthesis strategy."""
        if strategy == SynthesisStrategy.CHRONOLOGICAL:
            return await self._chronological_synthesis(doc_groups, query)
        elif strategy == SynthesisStrategy.CONSENSUS:
            return await self._consensus_synthesis(doc_groups, query, contradictions)
        elif strategy == SynthesisStrategy.COMPARATIVE:
            return await self._comparative_synthesis(doc_groups, query, contradictions)
        elif strategy == SynthesisStrategy.HIERARCHICAL:
            return await self._hierarchical_synthesis(doc_groups, query)
        elif strategy == SynthesisStrategy.COMPREHENSIVE:
            return await self._comprehensive_synthesis(doc_groups, query, contradictions)
        else:
            raise RAGError(f"Unknown synthesis strategy: {strategy}")
    
    async def _chronological_synthesis(
        self,
        doc_groups: Dict[str, List[DocumentChunk]],
        query: str
    ) -> List[SynthesizedChunk]:
        """Synthesize documents in chronological order."""
        synthesized_chunks = []
        
        # Sort documents by date if available
        docs_with_dates = []
        for doc_id, chunks in doc_groups.items():
            date_str = None
            for chunk in chunks:
                if chunk.metadata and chunk.metadata.get("date"):
                    date_str = chunk.metadata["date"]
                    break
            docs_with_dates.append((doc_id, chunks, date_str or "9999"))
        
        # Sort by date (unknown dates go last)
        docs_with_dates.sort(key=lambda x: x[2])
        
        for i, (doc_id, chunks, date_str) in enumerate(docs_with_dates):
            # Combine chunks from this document
            content = self._combine_chunk_content(chunks)
            sources = [self._chunk_to_source(chunks[0])]
            
            synthesized_chunk = SynthesizedChunk(
                content=content,
                sources=sources,
                confidence_score=0.8,  # High confidence for chronological
                synthesis_method="chronological",
                contradictions=[],
                supporting_evidence=[f"Chronological position: {i+1}"]
            )
            
            synthesized_chunks.append(synthesized_chunk)
        
        return synthesized_chunks
    
    async def _consensus_synthesis(
        self,
        doc_groups: Dict[str, List[DocumentChunk]],
        query: str,
        contradictions: List[Dict[str, Any]]
    ) -> List[SynthesizedChunk]:
        """Synthesize based on consensus between documents."""
        synthesized_chunks = []
        
        # Find common themes across documents
        all_content = []
        for chunks in doc_groups.values():
            content = self._combine_chunk_content(chunks)
            all_content.append(content)
        
        # Simple consensus: find common keywords
        common_themes = self._find_common_themes(all_content)
        
        for theme, documents in common_themes.items():
            if len(documents) >= len(doc_groups) * 0.6:  # 60% consensus
                # Create synthesized chunk for this theme
                supporting_sources = []
                supporting_content = []
                
                for doc_id in documents:
                    chunks = doc_groups[doc_id]
                    supporting_sources.append(self._chunk_to_source(chunks[0]))
                    supporting_content.append(self._combine_chunk_content(chunks))
                
                synthesized_content = f"Consensus on {theme}: " + \
                                    " | ".join(supporting_content[:3])
                
                synthesized_chunk = SynthesizedChunk(
                    content=synthesized_content,
                    sources=supporting_sources,
                    confidence_score=0.9,  # High confidence for consensus
                    synthesis_method="consensus",
                    contradictions=[],
                    supporting_evidence=[f"Supported by {len(documents)} sources"]
                )
                
                synthesized_chunks.append(synthesized_chunk)
        
        return synthesized_chunks
    
    async def _comparative_synthesis(
        self,
        doc_groups: Dict[str, List[DocumentChunk]],
        query: str,
        contradictions: List[Dict[str, Any]]
    ) -> List[SynthesizedChunk]:
        """Synthesize by comparing and contrasting sources."""
        synthesized_chunks = []
        
        if len(doc_groups) < 2:
            return await self._comprehensive_synthesis(doc_groups, query, contradictions)
        
        # Create comparative analysis
        doc_ids = list(doc_groups.keys())
        
        for i, doc_id1 in enumerate(doc_ids):
            for doc_id2 in doc_ids[i+1:]:
                chunks1 = doc_groups[doc_id1]
                chunks2 = doc_groups[doc_id2]
                
                content1 = self._combine_chunk_content(chunks1)
                content2 = self._combine_chunk_content(chunks2)
                
                # Find similarities and differences
                similarities = self._find_similarities(content1, content2)
                differences = self._find_differences(content1, content2)
                
                # Create comparative synthesis
                comparative_content = f"Comparing sources:\n"
                comparative_content += f"Similarities: {similarities}\n"
                comparative_content += f"Differences: {differences}"
                
                sources = [
                    self._chunk_to_source(chunks1[0]),
                    self._chunk_to_source(chunks2[0])
                ]
                
                # Check for contradictions between these documents
                doc_contradictions = [
                    c for c in contradictions 
                    if (c["document1"] == doc_id1 and c["document2"] == doc_id2) or
                       (c["document1"] == doc_id2 and c["document2"] == doc_id1)
                ]
                
                synthesized_chunk = SynthesizedChunk(
                    content=comparative_content,
                    sources=sources,
                    confidence_score=0.7,  # Medium confidence for comparison
                    synthesis_method="comparative",
                    contradictions=doc_contradictions,
                    supporting_evidence=["Comparative analysis"]
                )
                
                synthesized_chunks.append(synthesized_chunk)
        
        return synthesized_chunks
    
    async def _hierarchical_synthesis(
        self,
        doc_groups: Dict[str, List[DocumentChunk]],
        query: str
    ) -> List[SynthesizedChunk]:
        """Synthesize based on source importance/relevance."""
        synthesized_chunks = []
        
        # Score documents by relevance and reliability
        doc_scores = {}
        for doc_id, chunks in doc_groups.items():
            relevance_score = self._calculate_relevance_score(chunks, query)
            reliability_score = chunks[0].metadata.get("reliability_score", 1.0) if chunks[0].metadata else 1.0
            doc_scores[doc_id] = relevance_score * reliability_score
        
        # Sort by score (highest first)
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        
        for rank, (doc_id, score) in enumerate(sorted_docs):
            chunks = doc_groups[doc_id]
            content = self._combine_chunk_content(chunks)
            
            # Add hierarchical context
            if rank == 0:
                content = f"Primary source: {content}"
            elif rank == 1:
                content = f"Secondary source: {content}"
            else:
                content = f"Supporting source: {content}"
            
            sources = [self._chunk_to_source(chunks[0])]
            
            synthesized_chunk = SynthesizedChunk(
                content=content,
                sources=sources,
                confidence_score=max(0.5, 1.0 - rank * 0.1),  # Decreasing confidence
                synthesis_method="hierarchical",
                contradictions=[],
                supporting_evidence=[f"Relevance rank: {rank + 1}"]
            )
            
            synthesized_chunks.append(synthesized_chunk)
        
        return synthesized_chunks
    
    async def _comprehensive_synthesis(
        self,
        doc_groups: Dict[str, List[DocumentChunk]],
        query: str,
        contradictions: List[Dict[str, Any]]
    ) -> List[SynthesizedChunk]:
        """Comprehensive synthesis combining all approaches."""
        synthesized_chunks = []
        
        # Start with consensus items
        consensus_chunks = await self._consensus_synthesis(doc_groups, query, contradictions)
        synthesized_chunks.extend(consensus_chunks)
        
        # Add hierarchical information
        hierarchical_chunks = await self._hierarchical_synthesis(doc_groups, query)
        synthesized_chunks.extend(hierarchical_chunks[:3])  # Top 3 sources
        
        # Add comparative analysis if there are contradictions
        if contradictions:
            comparative_chunks = await self._comparative_synthesis(doc_groups, query, contradictions)
            synthesized_chunks.extend(comparative_chunks[:2])  # Top 2 comparisons
        
        return synthesized_chunks
    
    def _combine_chunk_content(self, chunks: List[DocumentChunk]) -> str:
        """Combine content from multiple chunks."""
        return " ".join(chunk.content for chunk in chunks)
    
    def _chunk_to_source(self, chunk: DocumentChunk) -> DocumentSource:
        """Convert a chunk to a document source."""
        metadata = chunk.metadata or {}
        return DocumentSource(
            document_id=chunk.document_id,
            filename=metadata.get("filename", f"Document {chunk.document_id}"),
            title=metadata.get("title", metadata.get("filename", "Unknown")),
            author=metadata.get("author"),
            date=metadata.get("creation_date") or metadata.get("date"),
            reliability_score=metadata.get("reliability_score", 1.0)
        )
    
    def _find_common_themes(self, contents: List[str]) -> Dict[str, List[int]]:
        """Find common themes across content pieces."""
        # Simple keyword-based theme detection
        themes = {}
        
        for i, content in enumerate(contents):
            words = set(content.lower().split())
            for word in words:
                if len(word) > 4:  # Skip short words
                    if word not in themes:
                        themes[word] = []
                    themes[word].append(i)
        
        # Return themes that appear in multiple documents
        return {theme: docs for theme, docs in themes.items() if len(docs) > 1}
    
    def _find_similarities(self, content1: str, content2: str) -> str:
        """Find similarities between two content pieces."""
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        common_words = words1 & words2
        
        # Filter meaningful words
        meaningful_common = [w for w in common_words if len(w) > 4]
        
        return ", ".join(meaningful_common[:5]) if meaningful_common else "No significant similarities"
    
    def _find_differences(self, content1: str, content2: str) -> str:
        """Find differences between two content pieces."""
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        unique1 = words1 - words2
        unique2 = words2 - words1
        
        # Get meaningful unique words
        meaningful_unique1 = [w for w in unique1 if len(w) > 4][:3]
        meaningful_unique2 = [w for w in unique2 if len(w) > 4][:3]
        
        differences = []
        if meaningful_unique1:
            differences.append(f"Source 1 unique: {', '.join(meaningful_unique1)}")
        if meaningful_unique2:
            differences.append(f"Source 2 unique: {', '.join(meaningful_unique2)}")
        
        return " | ".join(differences) if differences else "No significant differences"
    
    def _calculate_relevance_score(self, chunks: List[DocumentChunk], query: str) -> float:
        """Calculate relevance score for chunks given a query."""
        query_words = set(query.lower().split())
        
        total_score = 0
        for chunk in chunks:
            chunk_words = set(chunk.content.lower().split())
            overlap = len(query_words & chunk_words)
            total_score += overlap / max(len(query_words), 1)
        
        return total_score / max(len(chunks), 1)
    
    async def _generate_synthesized_answer(
        self,
        synthesized_chunks: List[SynthesizedChunk],
        query: str,
        strategy: SynthesisStrategy
    ) -> str:
        """Generate final synthesized answer from chunks."""
        if not synthesized_chunks:
            return "No synthesis possible with available sources."
        
        # Combine high-confidence chunks
        high_confidence_chunks = [
            chunk for chunk in synthesized_chunks 
            if chunk.confidence_score >= self.confidence_threshold
        ]
        
        if not high_confidence_chunks:
            high_confidence_chunks = synthesized_chunks[:3]  # Use top 3 if none meet threshold
        
        # Create structured answer based on strategy
        answer_parts = []
        
        if strategy == SynthesisStrategy.CONSENSUS:
            answer_parts.append("Based on consensus from multiple sources:")
        elif strategy == SynthesisStrategy.COMPARATIVE:
            answer_parts.append("Comparing information from different sources:")
        elif strategy == SynthesisStrategy.HIERARCHICAL:
            answer_parts.append("Based on source reliability and relevance:")
        else:
            answer_parts.append("Synthesizing information from multiple sources:")
        
        for i, chunk in enumerate(high_confidence_chunks):
            source_names = [s.title for s in chunk.sources]
            answer_parts.append(
                f"\n{i+1}. {chunk.content} "
                f"(Sources: {', '.join(source_names[:2])}"
                f"{'...' if len(source_names) > 2 else ''})"
            )
        
        return " ".join(answer_parts)
    
    def _create_source_attribution(
        self, 
        synthesized_chunks: List[SynthesizedChunk]
    ) -> Dict[str, List[str]]:
        """Create source attribution mapping."""
        attribution = {}
        
        for chunk in synthesized_chunks:
            content_preview = chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content
            
            for source in chunk.sources:
                if source.document_id not in attribution:
                    attribution[source.document_id] = []
                attribution[source.document_id].append(content_preview)
        
        return attribution
    
    def _calculate_synthesis_confidence(
        self,
        synthesized_chunks: List[SynthesizedChunk],
        contradictions: List[Dict[str, Any]]
    ) -> float:
        """Calculate overall confidence in the synthesis."""
        if not synthesized_chunks:
            return 0.0
        
        # Average confidence of chunks
        avg_confidence = sum(chunk.confidence_score for chunk in synthesized_chunks) / len(synthesized_chunks)
        
        # Reduce confidence based on contradictions
        contradiction_penalty = min(0.3, len(contradictions) * 0.1)
        
        return max(0.1, avg_confidence - contradiction_penalty)
    
    def _analyze_contradictions(self, contradictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze and summarize contradictions."""
        if not contradictions:
            return {"level": "none", "count": 0, "summary": "No contradictions detected"}
        
        # Count contradiction levels
        levels = [c.get("level", ContradictionLevel.MINOR) for c in contradictions]
        level_counts = {level: levels.count(level) for level in ContradictionLevel}
        
        # Determine overall level
        if level_counts.get(ContradictionLevel.MAJOR, 0) > 0:
            overall_level = ContradictionLevel.MAJOR
        elif level_counts.get(ContradictionLevel.MODERATE, 0) > 0:
            overall_level = ContradictionLevel.MODERATE
        else:
            overall_level = ContradictionLevel.MINOR
        
        summary = f"Found {len(contradictions)} contradictions. "
        summary += f"Overall level: {overall_level}. "
        summary += "Review source reliability and consider seeking additional sources."
        
        return {
            "level": overall_level,
            "count": len(contradictions),
            "summary": summary,
            "details": contradictions,
            "level_breakdown": level_counts
        }