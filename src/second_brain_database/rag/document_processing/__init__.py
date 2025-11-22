"""
Document Processing Service for RAG

Simple wrapper around the existing DocumentProcessor to adapt it for RAG workflows.
The existing DocumentProcessor already handles all major formats with comprehensive features.
"""

from pathlib import Path
import time
import uuid
from typing import Any, BinaryIO, Dict, List, Optional

from second_brain_database.integrations.docling_processor import DocumentProcessor
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.rag.core.config import DocumentProcessingConfig
from second_brain_database.rag.core.exceptions import DocumentParsingError, UnsupportedDocumentFormatError
from second_brain_database.rag.core.types import Document, DocumentChunk, DocumentMetadata, DocumentStatus

logger = get_logger()


class RAGDocumentService:
    """
    RAG Document Processing Service.
    
    Adapts the existing comprehensive DocumentProcessor for RAG workflows,
    converting processed documents to RAG Document format with chunking.
    """
    
    def __init__(self, config: DocumentProcessingConfig):
        """
        Initialize RAG document service.
        
        Args:
            config: Document processing configuration
        """
        self.config = config
        self.processor = DocumentProcessor()
        self.supported_formats = ["pdf", "docx", "pptx", "html", "htm", "xlsx", "md", "csv", "txt"]
        
        logger.info("Initialized RAG Document Service with existing DocumentProcessor")
    
    def supports_format(self, filename: str) -> bool:
        """
        Check if document format is supported.
        
        Args:
            filename: Name of the file
            
        Returns:
            True if format is supported
        """
        extension = Path(filename).suffix.lower().lstrip('.')
        return extension in self.supported_formats
    
    async def process_document(
        self,
        file_data: BinaryIO,
        filename: str,
        user_id: str = "",
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Document:
        """
        Process document for RAG system.
        
        Args:
            file_data: Binary file data
            filename: Name of the file
            user_id: User ID for processing context
            tenant_id: Tenant ID for multi-tenancy
            **kwargs: Additional processing options
            
        Returns:
            RAG Document with content and chunks
            
        Raises:
            DocumentParsingError: If processing fails
            UnsupportedDocumentFormatError: If format not supported
        """
        if not self.supports_format(filename):
            extension = Path(filename).suffix.lower().lstrip('.')
            raise UnsupportedDocumentFormatError(
                file_type=extension,
                supported_formats=self.supported_formats
            )
        
        start_time = time.time()
        logger.info(f"Processing document '{filename}' for RAG system")
        
        try:
            # Read file data
            file_data.seek(0)
            file_bytes = file_data.read()
            
            # Process with existing DocumentProcessor
            processor_result = await self.processor.process_document(
                file_data=file_bytes,
                filename=filename,
                user_id=user_id or "rag_system",
                tenant_id=tenant_id,
                extract_images=kwargs.get('extract_images', True),
                output_format=kwargs.get('output_format', 'markdown')
            )
            
            # Convert to RAG Document format
            document = self._convert_to_rag_document(processor_result, filename, user_id, tenant_id)
            
            processing_time = time.time() - start_time
            logger.info(
                f"Successfully processed document '{filename}' in {processing_time:.2f}s "
                f"({len(document.chunks)} chunks)"
            )
            
            return document
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"Failed to process document '{filename}' after {processing_time:.2f}s: {e}"
            )
            
            if isinstance(e, (DocumentParsingError, UnsupportedDocumentFormatError)):
                raise
            
            raise DocumentParsingError(
                f"Document processing failed: {e}",
                file_path=filename,
                original_error=e
            )
    
    def _convert_to_rag_document(
        self,
        processor_result: Dict[str, Any],
        filename: str,
        user_id: str,
        tenant_id: Optional[str] = None
    ) -> Document:
        """
        Convert DocumentProcessor result to RAG Document format.
        
        Args:
            processor_result: Result from DocumentProcessor
            filename: Original filename
            user_id: User ID
            tenant_id: Tenant ID
            
        Returns:
            RAG Document with chunks
        """
        content = processor_result.get("content", "")
        metadata_dict = processor_result.get("metadata", {})
        
        # Create RAG metadata
        metadata = DocumentMetadata(
            title=metadata_dict.get("filename", Path(filename).stem),
            mime_type=self._get_mime_type(filename),
            file_size=metadata_dict.get("file_size", 0),
            processing_time=0.0,  # Will be updated by caller
            word_count=len(content.split()) if isinstance(content, str) else 0,
            page_count=metadata_dict.get("page_count", 1),
            extracted_tables=1 if metadata_dict.get("has_tables", False) else 0,
            extracted_images=len(processor_result.get("images", [])),
        )
        
        # Add processor-specific metadata
        metadata.custom_fields.update({
            "processor": "docling",
            "document_id": processor_result.get("document_id"),
            "has_tables": metadata_dict.get("has_tables", False),
            "has_images": metadata_dict.get("has_images", False),
            "format": metadata_dict.get("format", "unknown"),
            "processing_options": metadata_dict.get("processing_options", {}),
            "images": processor_result.get("images", []),
            "processed_at": processor_result.get("processed_at"),
        })
        
        # Generate document ID (use the one from processor or create new)
        document_id = processor_result.get("document_id") or f"doc_{uuid.uuid4().hex[:8]}"
        
        # Create document chunks with document_id
        chunks = self._create_chunks(content, metadata_dict, document_id, tenant_id)
        
        # Create RAG document
        document = Document(
            id=document_id,
            filename=filename,
            user_id=user_id,
            tenant_id=tenant_id,
            content=content if isinstance(content, str) else str(content),
            chunks=chunks,
            status=DocumentStatus.INDEXED,
            metadata=metadata
        )
        
        return document
    
    def _create_chunks(
        self,
        content: Any,
        metadata: Dict[str, Any],
        document_id: str = None,
        tenant_id: Optional[str] = None
    ) -> List[DocumentChunk]:
        """
        Create document chunks from processed content.
        
        Args:
            content: Processed document content
            metadata: Document metadata
            document_id: Document ID for the chunks
            
        Returns:
            List of document chunks
        """
        # Convert content to string if needed
        if not isinstance(content, str):
            content = str(content)
        
        if not content.strip():
            return []
        
        # Generate document_id if not provided
        if not document_id:
            document_id = metadata.get("document_id", f"doc_{uuid.uuid4().hex[:8]}")
        
        # Use configured chunking strategy
        if self.config.chunk_strategy == "fixed":
            return self._create_fixed_chunks(content, metadata, document_id, tenant_id)
        elif self.config.chunk_strategy == "recursive":
            return self._create_recursive_chunks(content, metadata, document_id, tenant_id)
        else:
            # Default to fixed chunking
            return self._create_fixed_chunks(content, metadata, document_id, tenant_id)
    
    def _create_fixed_chunks(
        self,
        content: str,
        metadata: Dict[str, Any],
        document_id: str,
        tenant_id: Optional[str] = None
    ) -> List[DocumentChunk]:
        """Create fixed-size chunks."""
        chunks = []
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap
        
        # Split content into chunks
        start = 0
        chunk_index = 0
        
        while start < len(content):
            end = start + chunk_size
            chunk_text = content[start:end]
            
            # Avoid splitting words at the end
            if end < len(content) and not content[end].isspace():
                # Find last space within the chunk
                last_space = chunk_text.rfind(' ')
                if last_space > chunk_size * 0.8:  # Only if we don't cut too much
                    end = start + last_space
                    chunk_text = content[start:end]
            
            chunk = DocumentChunk(
                document_id=document_id,
                tenant_id=tenant_id,
                chunk_index=chunk_index,
                content=chunk_text.strip(),
                start_char=start,
                end_char=end,
                metadata={
                    "chunk_type": "fixed",
                    "token_count": len(chunk_text.split()),
                    "page_numbers": self._estimate_page_numbers(start, end, content, metadata),
                }
            )
            
            chunks.append(chunk)
            
            # Move start position with overlap
            start = end - overlap if overlap > 0 else end
            chunk_index += 1
            
            # Prevent infinite loop
            if start >= len(content):
                break
        
        return chunks
    
    def _create_recursive_chunks(
        self,
        content: str,
        metadata: Dict[str, Any],
        document_id: str,
        tenant_id: Optional[str] = None
    ) -> List[DocumentChunk]:
        """Create recursive chunks that respect document structure."""
        chunks = []
        
        # Split by paragraphs first
        paragraphs = content.split('\n\n')
        current_chunk = ""
        chunk_index = 0
        start_char = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # If adding this paragraph exceeds chunk size, finalize current chunk
            if current_chunk and len(current_chunk) + len(paragraph) > self.config.chunk_size:
                # Create chunk from current content
                chunk = DocumentChunk(
                    document_id=document_id,
                    tenant_id=tenant_id,
                    chunk_index=chunk_index,
                    content=current_chunk.strip(),
                    start_char=start_char,
                    end_char=start_char + len(current_chunk),
                    metadata={
                        "chunk_type": "recursive",
                        "token_count": len(current_chunk.split()),
                        "page_numbers": self._estimate_page_numbers(
                            start_char, 
                            start_char + len(current_chunk), 
                            content, 
                            metadata
                        ),
                    }
                )
                chunks.append(chunk)
                
                # Start new chunk with overlap
                if self.config.chunk_overlap > 0:
                    overlap_text = current_chunk[-self.config.chunk_overlap:]
                    current_chunk = overlap_text + '\n\n' + paragraph
                else:
                    current_chunk = paragraph
                    start_char += len(chunk.content)
                
                chunk_index += 1
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += '\n\n' + paragraph
                else:
                    current_chunk = paragraph
        
        # Add final chunk if there's remaining content
        if current_chunk.strip():
            chunk = DocumentChunk(
                document_id=document_id,
                tenant_id=tenant_id,
                chunk_index=chunk_index,
                content=current_chunk.strip(),
                start_char=start_char,
                end_char=start_char + len(current_chunk),
                metadata={
                    "chunk_type": "recursive",
                    "token_count": len(current_chunk.split()),
                    "page_numbers": self._estimate_page_numbers(
                        start_char,
                        start_char + len(current_chunk),
                        content,
                        metadata
                    ),
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def _estimate_page_numbers(
        self,
        start_char: int,
        end_char: int,
        content: str,
        metadata: Dict[str, Any]
    ) -> List[int]:
        """
        Estimate which pages a chunk spans.
        
        Args:
            start_char: Start character position
            end_char: End character position
            content: Full document content
            metadata: Document metadata
            
        Returns:
            List of estimated page numbers
        """
        total_pages = metadata.get("page_count", 1)
        if total_pages <= 1:
            return [1]
        
        # Estimate based on character position
        content_length = len(content)
        if content_length == 0:
            return [1]
        
        start_page = max(1, int((start_char / content_length) * total_pages) + 1)
        end_page = max(1, int((end_char / content_length) * total_pages) + 1)
        
        return list(range(start_page, min(end_page + 1, total_pages + 1)))
    
    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type for file."""
        import mimetypes
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"
    
    async def extract_tables(self, file_data: BinaryIO, filename: str) -> List[Dict[str, Any]]:
        """
        Extract tables from document using existing processor.
        
        Args:
            file_data: Binary file data
            filename: Name of the file
            
        Returns:
            List of extracted tables
        """
        file_data.seek(0)
        file_bytes = file_data.read()
        
        return await self.processor.extract_tables(file_bytes, filename)
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats."""
        return self.supported_formats.copy()
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get information about the document service."""
        return {
            "name": "RAGDocumentService",
            "description": "RAG wrapper for existing DocumentProcessor with Docling integration",
            "supported_formats": self.supported_formats,
            "features": {
                "multi_format_support": True,
                "ocr_capabilities": True,
                "table_extraction": True,
                "image_extraction": True,
                "layout_analysis": True,
                "chunking_strategies": ["fixed", "recursive"],
                "metadata_extraction": True,
            },
            "chunking_config": {
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap,
                "strategy": self.config.chunk_strategy,
            }
        }