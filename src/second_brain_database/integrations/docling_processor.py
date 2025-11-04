"""Document processing with Docling integration.

Handles:
- PDF, DOCX, PPTX, HTML document conversion
- OCR and image extraction
- Markdown/JSON export
- Integration with AI agents
"""
from typing import Dict, Any, Optional, List, BinaryIO
from pathlib import Path
import tempfile
import asyncio
from datetime import datetime, timezone

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

from ..managers.logging_manager import get_logger
from ..database import db_manager
from ..config import settings

logger = get_logger(prefix="[DoclingProcessor]")


class DocumentProcessor:
    """Production document processor using Docling."""
    
    def __init__(self):
        """Initialize Docling converter with production settings."""
        # Configure PDF pipeline with OCR
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options.do_cell_matching = True
        
        # Initialize converter
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                    backend=PyPdfiumDocumentBackend
                )
            }
        )
        
        logger.info("Docling DocumentProcessor initialized")
    
    async def process_document(
        self,
        file_data: bytes,
        filename: str,
        user_id: str,
        extract_images: bool = True,
        output_format: str = "markdown"
    ) -> Dict[str, Any]:
        """Process document and extract structured content.
        
        Args:
            file_data: Document bytes
            filename: Original filename
            user_id: User ID for tracking
            extract_images: Whether to extract images
            output_format: Output format (markdown, json, text)
            
        Returns:
            Processing result with extracted content
        """
        try:
            # Save to temp file
            suffix = Path(filename).suffix
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_data)
                tmp_path = tmp.name
            
            # Convert document
            result = await asyncio.to_thread(
                self.converter.convert,
                tmp_path
            )
            
            # Extract content based on format
            if output_format == "markdown":
                content = result.document.export_to_markdown()
            elif output_format == "json":
                content = result.document.export_to_dict()
            else:
                content = result.document.export_to_text()
            
            # Extract metadata
            metadata = {
                "filename": filename,
                "file_size": len(file_data),
                "page_count": len(result.document.pages),
                "has_tables": any(
                    page.tables for page in result.document.pages
                ),
                "has_images": any(
                    page.images for page in result.document.pages
                ),
                "format": suffix[1:] if suffix else "unknown"
            }
            
            # Extract images if requested
            images = []
            if extract_images:
                for page_idx, page in enumerate(result.document.pages):
                    for img_idx, image in enumerate(page.images):
                        images.append({
                            "page": page_idx + 1,
                            "index": img_idx,
                            "bbox": image.bbox if hasattr(image, 'bbox') else None,
                            "size": image.size if hasattr(image, 'size') else None
                        })
            
            # Store in MongoDB
            doc_id = await self._store_document(
                user_id=user_id,
                filename=filename,
                content=content,
                metadata=metadata,
                images=images
            )
            
            # Cleanup temp file
            Path(tmp_path).unlink(missing_ok=True)
            
            result_data = {
                "document_id": str(doc_id),
                "content": content,
                "metadata": metadata,
                "images": images,
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(
                f"Processed document {filename} for user {user_id}",
                extra={
                    "user_id": user_id,
                    "pages": metadata["page_count"],
                    "format": metadata["format"]
                }
            )
            
            return result_data
            
        except Exception as e:
            logger.error(f"Error processing document {filename}: {e}", exc_info=True)
            raise
    
    async def _store_document(
        self,
        user_id: str,
        filename: str,
        content: Any,
        metadata: Dict[str, Any],
        images: List[Dict[str, Any]]
    ) -> Any:
        """Store processed document in MongoDB.
        
        Args:
            user_id: User ID
            filename: Filename
            content: Extracted content
            metadata: Document metadata
            images: Extracted images
            
        Returns:
            MongoDB document ID
        """
        collection = db_manager.get_collection("processed_documents")
        
        doc = {
            "user_id": user_id,
            "filename": filename,
            "content": content,
            "metadata": metadata,
            "images": images,
            "created_at": datetime.now(timezone.utc),
            "indexed": False
        }
        
        result = await collection.insert_one(doc)
        return result.inserted_id
    
    async def extract_tables(
        self,
        file_data: bytes,
        filename: str
    ) -> List[Dict[str, Any]]:
        """Extract tables from document.
        
        Args:
            file_data: Document bytes
            filename: Filename
            
        Returns:
            List of extracted tables
        """
        try:
            suffix = Path(filename).suffix
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_data)
                tmp_path = tmp.name
            
            result = await asyncio.to_thread(
                self.converter.convert,
                tmp_path
            )
            
            tables = []
            for page_idx, page in enumerate(result.document.pages):
                for table_idx, table in enumerate(page.tables):
                    tables.append({
                        "page": page_idx + 1,
                        "index": table_idx,
                        "rows": table.num_rows if hasattr(table, 'num_rows') else 0,
                        "cols": table.num_cols if hasattr(table, 'num_cols') else 0,
                        "data": table.export_to_dataframe().to_dict() if hasattr(table, 'export_to_dataframe') else None
                    })
            
            Path(tmp_path).unlink(missing_ok=True)
            
            logger.info(f"Extracted {len(tables)} tables from {filename}")
            
            return tables
            
        except Exception as e:
            logger.error(f"Error extracting tables: {e}", exc_info=True)
            return []
    
    async def chunk_for_rag(
        self,
        document_id: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[Dict[str, Any]]:
        """Chunk document for RAG/vector search.
        
        Args:
            document_id: MongoDB document ID
            chunk_size: Characters per chunk
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of text chunks with metadata
        """
        try:
            from bson import ObjectId
            
            # Get document
            collection = db_manager.get_collection("processed_documents")
            doc = await collection.find_one({"_id": ObjectId(document_id)})
            
            if not doc:
                raise ValueError(f"Document {document_id} not found")
            
            content = doc["content"]
            if isinstance(content, dict):
                # JSON format, extract text
                content = str(content)
            
            # Simple chunking (can be enhanced with semantic chunking)
            chunks = []
            start = 0
            chunk_idx = 0
            
            while start < len(content):
                end = start + chunk_size
                chunk_text = content[start:end]
                
                chunks.append({
                    "document_id": document_id,
                    "chunk_index": chunk_idx,
                    "text": chunk_text,
                    "start_char": start,
                    "end_char": end,
                    "metadata": {
                        "filename": doc["filename"],
                        "user_id": doc["user_id"],
                        "created_at": doc["created_at"]
                    }
                })
                
                start = end - chunk_overlap
                chunk_idx += 1
            
            # Store chunks for vector search
            chunks_collection = db_manager.get_collection("document_chunks")
            if chunks:
                await chunks_collection.insert_many(chunks)
            
            # Mark document as indexed
            await collection.update_one(
                {"_id": ObjectId(document_id)},
                {"$set": {"indexed": True, "chunk_count": len(chunks)}}
            )
            
            logger.info(f"Created {len(chunks)} chunks for document {document_id}")
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error chunking document: {e}", exc_info=True)
            raise


# Global processor instance
document_processor = DocumentProcessor()
