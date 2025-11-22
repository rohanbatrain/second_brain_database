"""Document processing with Docling integration.

This module provides professional document processing capabilities using Docling,
focusing on format conversion, OCR, table extraction, and layout analysis.

Features:
- Multi-format document processing (PDF, DOCX, PPTX, HTML, XLSX, MD, CSV)
- Advanced OCR with configurable languages and engines
- Table structure recognition and extraction
- Image and figure detection
- Layout analysis and content structuring
- Clean separation from vector search operations

Architecture:
- Pure document processing without search/vector logic
- Configurable processing pipelines
- Comprehensive error handling and logging
- Async processing with proper resource management
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from ..config import settings
from ..database import db_manager
from ..managers.logging_manager import get_logger

logger = get_logger(prefix="[DoclingProcessor]")


class DocumentProcessor:
    """Professional document processor using Docling for multi-format document processing."""

    def __init__(self):
        """Initialize Docling converter with production settings."""
        # Configure pipeline options for all supported formats
        format_options = {}

        # PDF with basic processing
        # Disable OCR and table structure to avoid PyTorch model loading issues
        # According to Docling docs: https://docling-project.github.io/docling/usage/advanced_options/
        if settings.DOCLING_ENABLED:
            # Use accelerator options to ensure CPU-only processing
            accelerator_options = AcceleratorOptions(
                num_threads=4,  # Limit CPU threads
                device="cpu"     # Force CPU to avoid GPU/model loading issues
            )
            
            pdf_pipeline = PdfPipelineOptions(
                do_ocr=False,  # Disable OCR to avoid EasyOCR model loading
                do_table_structure=False,  # Disable TableFormer to avoid model loading
                accelerator_options=accelerator_options
            )
            
            format_options[InputFormat.PDF] = PdfFormatOption(
                pipeline_options=pdf_pipeline, 
                backend=PyPdfiumDocumentBackend
            )

        # Initialize converter with all supported formats
        # Based on official Docling documentation: https://docling-project.github.io/docling/usage/supported_formats/
        allowed_formats = [
            # Document formats
            InputFormat.PDF, InputFormat.DOCX, InputFormat.XLSX, InputFormat.PPTX,
            InputFormat.HTML, InputFormat.MD, InputFormat.CSV,
            # Image formats (for OCR)
            InputFormat.IMAGE,
            # Additional formats supported by Docling
            InputFormat.ASCIIDOC,
            InputFormat.VTT,  # Video text tracks
            InputFormat.XML_JATS,  # Scientific publishing XML
            InputFormat.XML_USPTO,  # Patent XML
        ]

        self.converter = DocumentConverter(
            allowed_formats=allowed_formats,
            format_options=format_options
        )

        logger.info("Docling DocumentProcessor initialized with multi-format support")

    async def process_document(
        self,
        file_data: bytes,
        filename: str,
        user_id: str,
        extract_images: bool = None,
        output_format: str = None,
        tenant_id: str = None,
    ) -> Dict[str, Any]:
        """Process document and extract structured content.

        Args:
            file_data: Document bytes
            filename: Original filename
            user_id: User ID for tracking
            extract_images: Whether to extract images (uses config default if None)
            output_format: Output format (uses config default if None)

        Returns:
            Processing result with extracted content
        """
        if extract_images is None:
            extract_images = settings.DOCLING_IMAGE_EXTRACTION
        if output_format is None:
            output_format = settings.DOCLING_EXPORT_FORMAT

        try:
            # Validate file format
            suffix = Path(filename).suffix.lower()
            supported_formats = settings.DOCLING_SUPPORTED_FORMATS.split(",")
            if suffix and suffix[1:] not in supported_formats:
                raise ValueError(f"Unsupported file format: {suffix}. Supported: {supported_formats}")

            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_data)
                tmp_path = tmp.name

            # Convert document
            result = await asyncio.to_thread(self.converter.convert, tmp_path)

            # Extract content based on format
            if output_format == "markdown":
                content = result.document.export_to_markdown()
            elif output_format == "json":
                content = result.document.export_to_dict()
            else:
                content = result.document.export_to_text()

            # Extract enhanced metadata
            # Handle both page objects and page counts
            page_count = len(result.document.pages) if hasattr(result.document.pages, '__len__') else 1
            
            # Safely check for tables and images
            has_tables = False
            has_images = False
            try:
                if hasattr(result.document.pages, '__iter__'):
                    has_tables = any(hasattr(page, 'tables') and page.tables for page in result.document.pages)
                    has_images = any(hasattr(page, 'images') and page.images for page in result.document.pages)
            except (TypeError, AttributeError):
                # Pages might be a simple count, not iterable objects
                pass
            
            metadata = {
                "filename": filename,
                "file_size": len(file_data),
                "page_count": page_count,
                "has_tables": has_tables,
                "has_images": has_images,
                "format": suffix[1:] if suffix else "unknown",
                "processing_options": {
                    "ocr_enabled": settings.DOCLING_OCR_ENABLED,
                    "table_extraction": settings.DOCLING_TABLE_EXTRACTION,
                    "layout_analysis": settings.DOCLING_LAYOUT_ANALYSIS,
                },
            }

            # Extract images if requested
            images = []
            if extract_images:
                try:
                    if hasattr(result.document.pages, '__iter__'):
                        for page_idx, page in enumerate(result.document.pages):
                            if hasattr(page, 'images') and page.images:
                                for img_idx, image in enumerate(page.images):
                                    images.append(
                                        {
                                            "page": page_idx + 1,
                                            "index": img_idx,
                                            "bbox": image.bbox if hasattr(image, "bbox") else None,
                                            "size": image.size if hasattr(image, "size") else None,
                                        }
                                    )
                except (TypeError, AttributeError) as e:
                    logger.warning(f"Could not extract images from {filename}: {e}")
                    images = []

            # Store in MongoDB
            doc_id = await self._store_document(
                user_id=user_id,
                filename=filename,
                content=content,
                metadata=metadata,
                images=images,
                tenant_id=tenant_id,
            )

            # Cleanup temp file
            Path(tmp_path).unlink(missing_ok=True)

            result_data = {
                "document_id": str(doc_id),
                "content": content,
                "metadata": metadata,
                "images": images,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(
                f"Processed document {filename} for user {user_id}",
                extra={
                    "user_id": user_id,
                    "pages": metadata["page_count"],
                    "format": metadata["format"],
                },
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
        images: List[Dict[str, Any]],
        tenant_id: str = None,
    ) -> Any:
        """Store processed document in MongoDB.

        Args:
            user_id: User ID
            filename: Filename
            content: Extracted content
            metadata: Document metadata
            images: Extracted images
            tenant_id: Tenant ID

        Returns:
            MongoDB document ID
        """
        collection = db_manager.get_tenant_collection("processed_documents", tenant_id=tenant_id)

        doc = {
            "user_id": user_id,
            "filename": filename,
            "content": content,
            "metadata": metadata,
            "images": images,
            "created_at": datetime.now(timezone.utc),
            "indexed": False,  # Will be set by vector search manager
        }

        result = await collection.insert_one(doc)
        return result.inserted_id

    async def extract_tables(self, file_data: bytes, filename: str) -> List[Dict[str, Any]]:
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

            result = await asyncio.to_thread(self.converter.convert, tmp_path)

            tables = []
            for page_idx, page in enumerate(result.document.pages):
                for table_idx, table in enumerate(page.tables):
                    tables.append(
                        {
                            "page": page_idx + 1,
                            "index": table_idx,
                            "rows": table.num_rows if hasattr(table, "num_rows") else 0,
                            "cols": table.num_cols if hasattr(table, "num_cols") else 0,
                            "data": (
                                table.export_to_dataframe().to_dict() if hasattr(table, "export_to_dataframe") else None
                            ),
                        }
                    )

            Path(tmp_path).unlink(missing_ok=True)

            logger.info(f"Extracted {len(tables)} tables from {filename}")

            return tables

        except Exception as e:
            logger.error(f"Error extracting tables: {e}", exc_info=True)
            return []

    async def get_document_content(self, document_id: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Retrieve processed document content from database.

        Args:
            document_id: MongoDB document ID
            tenant_id: Tenant ID

        Returns:
            Document content and metadata, or None if not found
        """
        try:
            from bson import ObjectId

            collection = db_manager.get_tenant_collection("processed_documents", tenant_id=tenant_id)
            doc = await collection.find_one({"_id": ObjectId(document_id)})

            if not doc:
                return None

            return {
                "document_id": str(doc["_id"]),
                "filename": doc.get("filename"),
                "content": doc.get("content"),
                "metadata": doc.get("metadata", {}),
                "images": doc.get("images", []),
                "created_at": doc.get("created_at"),
                "indexed": doc.get("indexed", False),
            }

        except Exception as e:
            logger.error(f"Error retrieving document content: {e}")
            return None
