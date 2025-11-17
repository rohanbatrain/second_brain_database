#!/usr/bin/env python3
"""
Production Streamlit RAG Application

Inspired by fahdmirza/doclingwithollama, this application provides a modern web interface
for the Second Brain Database RAG system with advanced document processing capabilities.

Features:
- Document upload with Docling integration
- Real-time processing status
- Interactive chat interface
- Document management and search
- Analytics and monitoring
- Production-ready error handling

Usage:
    streamlit run streamlit_rag_app.py --server.port 8501

Requirements:
    - Second Brain Database API running on localhost:8000
    - Docling installed for document processing
    - Valid authentication tokens
"""

import streamlit as st
import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
from pathlib import Path
import io
import base64

# Configure Streamlit page
st.set_page_config(
    page_title="Second Brain RAG System",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration
API_BASE_URL = "http://localhost:8000"
RAG_ENDPOINT = f"{API_BASE_URL}/rag"

class RAGClient:
    """Client for interacting with the Second Brain RAG API."""
    
    def __init__(self, api_base: str, token: Optional[str] = None):
        self.api_base = api_base
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def health_check(self) -> Dict[str, Any]:
        """Check RAG system health."""
        try:
            response = self.session.get(f"{self.api_base}/health", timeout=10)
            return response.json() if response.status_code == 200 else {"status": "unhealthy", "error": "API unreachable"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        try:
            response = self.session.get(f"{self.api_base}/status", timeout=15)
            return response.json() if response.status_code == 200 else {"error": "Failed to get status"}
        except Exception as e:
            return {"error": str(e)}
    
    def upload_document(self, file_content: bytes, filename: str, async_processing: bool = True) -> Dict[str, Any]:
        """Upload a document for processing."""
        try:
            files = {"file": (filename, file_content, "application/octet-stream")}
            data = {"async_processing": async_processing}
            
            response = self.session.post(
                f"{self.api_base}/upload",
                files=files,
                data=data,
                timeout=60
            )
            return response.json() if response.status_code in [200, 201, 202] else {"error": f"Upload failed: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def query_documents(self, query: str, **kwargs) -> Dict[str, Any]:
        """Query documents with RAG."""
        try:
            payload = {
                "query": query,
                "use_llm": kwargs.get("use_llm", True),
                "max_results": kwargs.get("max_results", 5),
                "similarity_threshold": kwargs.get("similarity_threshold", 0.7),
                "query_type": kwargs.get("query_type", "semantic"),  # semantic, keyword, or hybrid
                "conversation_id": kwargs.get("conversation_id"),
                "collection_name": kwargs.get("collection_name", "documents"),
                "include_metadata": kwargs.get("include_metadata", True),
                "temperature": kwargs.get("temperature", 0.7)
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            response = self.session.post(
                f"{self.api_base}/query",
                json=payload,
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_detail = response.json()
                    return {"error": f"Query failed: {response.status_code}", "detail": error_detail}
                except:
                    return {"error": f"Query failed: {response.status_code}", "text": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of an async task."""
        try:
            response = self.session.get(f"{self.api_base}/tasks/{task_id}", timeout=10)
            return response.json() if response.status_code == 200 else {"error": "Task not found"}
        except Exception as e:
            return {"error": str(e)}
    
    def list_documents(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List user documents."""
        try:
            params = {"limit": limit, "offset": offset, "include_content": False}
            response = self.session.get(f"{self.api_base}/documents", params=params, timeout=15)
            return response.json() if response.status_code == 200 else {"error": "Failed to list documents"}
        except Exception as e:
            return {"error": str(e)}
    
    def delete_document(self, document_id: str) -> Dict[str, Any]:
        """Delete a document."""
        try:
            response = self.session.delete(f"{self.api_base}/documents/{document_id}", timeout=15)
            return response.json() if response.status_code == 200 else {"error": "Failed to delete document"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Get usage analytics."""
        try:
            payload = {"days": days}
            response = self.session.post(f"{self.api_base}/analytics", json=payload, timeout=20)
            return response.json() if response.status_code == 200 else {"error": "Failed to get analytics"}
        except Exception as e:
            return {"error": str(e)}


def init_session_state():
    """Initialize Streamlit session state variables."""
    if "rag_client" not in st.session_state:
        st.session_state.rag_client = None
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = ""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if "current_tasks" not in st.session_state:
        st.session_state.current_tasks = {}
    if "documents" not in st.session_state:
        st.session_state.documents = []


def setup_sidebar():
    """Setup the sidebar with authentication and system status."""
    st.sidebar.title("🧠 Second Brain RAG")
    
    # Authentication
    st.sidebar.header("🔐 Authentication")
    
    # Option to load token from file
    if st.sidebar.checkbox("Load token from file", value=False):
        token_file = st.sidebar.text_input("Token file path", value="rag_token.txt")
        if st.sidebar.button("Load Token"):
            try:
                with open(token_file, 'r') as f:
                    token = f.read().strip()
                    st.session_state.auth_token = token
                    st.sidebar.success(f"✅ Token loaded from {token_file}")
            except Exception as e:
                st.sidebar.error(f"❌ Failed to load token: {e}")
    
    token = st.sidebar.text_input("API Token", type="password", value=st.session_state.auth_token,
                                  help="JWT token for API authentication")
    
    if st.sidebar.button("🔌 Connect", type="primary"):
        st.session_state.auth_token = token
        if token:
            st.session_state.rag_client = RAGClient(RAG_ENDPOINT, token)
            # Test connection
            health = st.session_state.rag_client.health_check()
            if health.get("status") == "healthy":
                st.sidebar.success("✅ Connected successfully!")
                # Show token info
                try:
                    import jwt
                    decoded = jwt.decode(token, options={"verify_signature": False})
                    st.sidebar.info(f"👤 User: {decoded.get('username', 'Unknown')}")
                except:
                    pass
            else:
                st.sidebar.error(f"❌ Connection failed: {health.get('error', 'Unknown error')}")
                if "detail" in health:
                    with st.sidebar.expander("Error Details"):
                        st.json(health["detail"])
        else:
            st.sidebar.warning("⚠️ Please enter a valid token")
    
    # System Status
    if st.session_state.rag_client:
        st.sidebar.header("📊 System Status")
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("🔄 Refresh"):
                st.rerun()
        with col2:
            if st.button("🔌 Disconnect"):
                st.session_state.rag_client = None
                st.session_state.auth_token = ""
                st.rerun()
        
        # Health check
        health = st.session_state.rag_client.health_check()
        if health.get("status") == "healthy":
            st.sidebar.success("✅ RAG System Online")
        else:
            st.sidebar.error("❌ System Offline")
        
        # Get detailed status
        status = st.session_state.rag_client.get_status()
        if "error" not in status:
            with st.sidebar.expander("📈 Details"):
                st.write(f"**Documents:** {status.get('document_count', 'N/A')}")
                st.write(f"**Collections:** {status.get('collection_count', 'N/A')}")
                if "uptime" in status:
                    st.write(f"**Uptime:** {status['uptime']}")
        
        # Show conversation ID
        st.sidebar.info(f"🗨️ Conv: {st.session_state.conversation_id[:8]}...")
    else:
        st.sidebar.warning("⚠️ Not connected to RAG system")
        st.sidebar.info("💡 Enter your API token above to connect")
    
    # Navigation
    st.sidebar.header("📑 Navigation")
    page = st.sidebar.radio(
        "Choose a page:",
        ["Chat Interface", "Document Upload", "Document Manager", "Analytics", "System Monitor"]
    )
    
    return page


def chat_interface():
    """Main chat interface for RAG queries."""
    st.header("💬 Chat with Your Documents")
    
    if not st.session_state.rag_client:
        st.warning("⚠️ Please connect to the RAG system first using the sidebar.")
        return
    
    # Chat configuration
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        use_llm = st.checkbox("Use AI Generation", value=True, help="Generate AI responses or just search")
    with col2:
        query_type = st.selectbox("Query Type", ["semantic", "keyword", "hybrid"], 
                                  help="Semantic: AI-based similarity | Keyword: Exact matching | Hybrid: Both")
    with col3:
        max_results = st.slider("Max Results", 1, 20, 5, help="Maximum number of document chunks to retrieve")
    with col4:
        similarity_threshold = st.slider("Similarity", 0.0, 1.0, 0.7, 0.1, help="Minimum similarity score")
    
    # Chat history display
    st.subheader("Conversation History")
    chat_container = st.container()
    
    with chat_container:
        for i, message in enumerate(st.session_state.chat_history):
            if message["role"] == "user":
                st.markdown(f"**🙋 You:** {message['content']}")
            else:
                st.markdown(f"**🤖 AI:** {message['content']}")
                
                # Show metadata
                metadata_parts = []
                if "chunks" in message:
                    metadata_parts.append(f"{message['chunks']} chunks")
                if "query_type" in message:
                    metadata_parts.append(f"type: {message['query_type']}")
                
                if metadata_parts:
                    st.caption(f"ℹ️ {' • '.join(metadata_parts)}")
                
                # Show sources if available
                if "sources" in message and message["sources"]:
                    with st.expander(f"📄 Sources ({len(message['sources'])})"):
                        for j, source in enumerate(message["sources"]):
                            st.markdown(f"{j+1}. {source}")
    
    # New query input
    st.subheader("Ask a Question")
    query = st.text_area("Your question:", height=100, placeholder="Ask anything about your documents...")
    
    col1, col2, col3 = st.columns([1, 1, 3])
    
    with col1:
        if st.button("🚀 Send Query", type="primary"):
            if query.strip():
                # Add user message to chat
                st.session_state.chat_history.append({
                    "role": "user",
                    "content": query,
                    "timestamp": datetime.now()
                })
                
                # Query RAG system
                with st.spinner("🔍 Searching documents..."):
                    result = st.session_state.rag_client.query_documents(
                        query=query,
                        use_llm=use_llm,
                        max_results=max_results,
                        similarity_threshold=similarity_threshold,
                        query_type=query_type,
                        conversation_id=st.session_state.conversation_id
                    )
                
                if "error" not in result:
                    # Add AI response to chat
                    answer = result.get("answer", result.get("response", "No answer generated"))
                    sources = result.get("sources", [])
                    chunks = result.get("chunks", result.get("documents", []))
                    
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources,
                        "chunks": len(chunks),
                        "timestamp": datetime.now(),
                        "query_type": query_type
                    })
                    st.rerun()
                else:
                    st.error(f"❌ Query failed: {result['error']}")
                    # Show detailed error if available
                    if "detail" in result:
                        with st.expander("Error Details"):
                            st.json(result["detail"])
                    elif "text" in result:
                        with st.expander("Raw Response"):
                            st.code(result["text"])
            else:
                st.warning("Please enter a question.")
    
    with col2:
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_history = []
            st.session_state.conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.rerun()


def document_upload():
    """Document upload interface with Docling integration."""
    st.header("📄 Upload Documents")
    
    if not st.session_state.rag_client:
        st.warning("⚠️ Please connect to the RAG system first using the sidebar.")
        return
    
    st.write("Upload documents to add them to your Second Brain. Supported formats: PDF, Word, PowerPoint, Images, Text files.")
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Choose files to upload:",
        accept_multiple_files=True,
        type=["pdf", "docx", "pptx", "txt", "md", "png", "jpg", "jpeg"]
    )
    
    # Upload settings
    col1, col2 = st.columns(2)
    
    with col1:
        async_processing = st.checkbox("Async Processing", value=True, help="Process files in background")
    with col2:
        auto_refresh = st.checkbox("Auto-refresh status", value=True, help="Automatically refresh task status")
    
    if uploaded_files:
        st.write(f"📁 Selected {len(uploaded_files)} files")
        
        # Show file details
        with st.expander("📋 File Details"):
            for file in uploaded_files:
                st.write(f"• {file.name} ({file.size:,} bytes)")
        
        if st.button("🚀 Upload All Files", type="primary"):
            progress_bar = st.progress(0)
            status_container = st.container()
            
            for i, file in enumerate(uploaded_files):
                progress_bar.progress((i) / len(uploaded_files))
                
                with status_container:
                    st.write(f"⏳ Uploading {file.name}...")
                
                # Upload file
                file_content = file.read()
                result = st.session_state.rag_client.upload_document(
                    file_content=file_content,
                    filename=file.name,
                    async_processing=async_processing
                )
                
                if "error" not in result:
                    if async_processing and "task_id" in result:
                        st.session_state.current_tasks[result["task_id"]] = {
                            "filename": file.name,
                            "started": datetime.now(),
                            "status": "processing"
                        }
                        st.success(f"✅ {file.name} uploaded - Processing in background")
                    else:
                        st.success(f"✅ {file.name} processed successfully")
                else:
                    st.error(f"❌ Failed to upload {file.name}: {result['error']}")
            
            progress_bar.progress(1.0)
            st.success("🎉 All files uploaded!")
    
    # Current tasks status
    if st.session_state.current_tasks:
        st.subheader("📊 Processing Status")
        
        # Auto-refresh logic
        if auto_refresh:
            time.sleep(2)  # Small delay for auto-refresh
            
        for task_id, task_info in list(st.session_state.current_tasks.items()):
            status_result = st.session_state.rag_client.get_task_status(task_id)
            
            if "error" not in status_result:
                task_status = status_result.get("status", "unknown")
                
                if task_status == "SUCCESS":
                    st.success(f"✅ {task_info['filename']} - Processing complete!")
                    del st.session_state.current_tasks[task_id]
                elif task_status == "FAILURE":
                    st.error(f"❌ {task_info['filename']} - Processing failed!")
                    del st.session_state.current_tasks[task_id]
                else:
                    elapsed = datetime.now() - task_info['started']
                    st.info(f"⏳ {task_info['filename']} - {task_status} ({elapsed.seconds}s)")
            else:
                # Task not found or error - assume completed
                st.warning(f"⚠️ {task_info['filename']} - Status unknown")
                del st.session_state.current_tasks[task_id]
        
        if auto_refresh and st.session_state.current_tasks:
            st.rerun()


def document_manager():
    """Document management interface."""
    st.header("📚 Document Manager")
    
    if not st.session_state.rag_client:
        st.warning("⚠️ Please connect to the RAG system first using the sidebar.")
        return
    
    # Fetch documents
    if st.button("🔄 Refresh Documents") or not st.session_state.documents:
        with st.spinner("📥 Loading documents..."):
            result = st.session_state.rag_client.list_documents(limit=100)
            if "error" not in result:
                st.session_state.documents = result if isinstance(result, list) else result.get("documents", [])
            else:
                st.error(f"❌ Failed to load documents: {result['error']}")
                return
    
    if not st.session_state.documents:
        st.info("📂 No documents found. Upload some documents to get started!")
        return
    
    st.write(f"📊 Total documents: {len(st.session_state.documents)}")
    
    # Document list with management options
    for i, doc in enumerate(st.session_state.documents):
        with st.expander(f"📄 {doc.get('filename', f'Document {i+1}')}"):
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.write(f"**ID:** {doc.get('id', 'Unknown')}")
                st.write(f"**Size:** {doc.get('size', 0):,} bytes")
                st.write(f"**Uploaded:** {doc.get('created_at', 'Unknown')}")
                if doc.get('metadata'):
                    st.write(f"**Type:** {doc['metadata'].get('content_type', 'Unknown')}")
            
            with col2:
                if st.button(f"🔄 Reindex", key=f"reindex_{i}"):
                    result = st.session_state.rag_client.session.post(
                        f"{st.session_state.rag_client.api_base}/documents/{doc['id']}/reindex"
                    )
                    if result.status_code == 200:
                        st.success("Reindexing started!")
                    else:
                        st.error("Reindexing failed!")
            
            with col3:
                if st.button(f"🗑️ Delete", key=f"delete_{i}", type="secondary"):
                    result = st.session_state.rag_client.delete_document(doc['id'])
                    if "error" not in result:
                        st.success("Document deleted!")
                        st.session_state.documents = [d for d in st.session_state.documents if d['id'] != doc['id']]
                        st.rerun()
                    else:
                        st.error(f"Delete failed: {result['error']}")


def analytics_dashboard():
    """Analytics and monitoring dashboard."""
    st.header("📊 Analytics Dashboard")
    
    if not st.session_state.rag_client:
        st.warning("⚠️ Please connect to the RAG system first using the sidebar.")
        return
    
    # Time period selection
    col1, col2 = st.columns([1, 3])
    
    with col1:
        days = st.selectbox("Time Period", [1, 7, 30, 90], index=1)
    
    with col2:
        if st.button("📈 Generate Analytics"):
            with st.spinner("📊 Generating analytics..."):
                result = st.session_state.rag_client.get_analytics(days=days)
                
                if "error" not in result:
                    # Display analytics
                    st.subheader(f"📈 Analytics for Last {days} Days")
                    
                    # Key metrics
                    metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
                    
                    with metrics_col1:
                        st.metric("Total Queries", result.get("total_queries", 0))
                    with metrics_col2:
                        st.metric("Documents Processed", result.get("documents_processed", 0))
                    with metrics_col3:
                        st.metric("Avg Response Time", f"{result.get('avg_response_time', 0):.2f}s")
                    with metrics_col4:
                        st.metric("Cache Hit Rate", f"{result.get('cache_hit_rate', 0):.1%}")
                    
                    # Charts
                    if result.get("daily_queries"):
                        st.subheader("📊 Daily Query Volume")
                        df = pd.DataFrame(result["daily_queries"])
                        st.line_chart(df.set_index("date")["queries"])
                    
                    if result.get("popular_queries"):
                        st.subheader("🔥 Popular Queries")
                        for query in result["popular_queries"][:10]:
                            st.write(f"• {query['query']} ({query['count']} times)")
                else:
                    st.error(f"❌ Analytics failed: {result['error']}")


def system_monitor():
    """System monitoring and health dashboard."""
    st.header("🔧 System Monitor")
    
    if not st.session_state.rag_client:
        st.warning("⚠️ Please connect to the RAG system first using the sidebar.")
        return
    
    # Auto-refresh toggle
    auto_refresh = st.checkbox("Auto-refresh (5s)", value=False)
    
    if st.button("🔄 Refresh Now") or auto_refresh:
        # System health
        health = st.session_state.rag_client.health_check()
        status = st.session_state.rag_client.get_status()
        
        # Health status
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏥 System Health")
            if health.get("status") == "healthy":
                st.success("✅ System Healthy")
            else:
                st.error("❌ System Issues Detected")
            
            if "services" in health:
                for service, status in health["services"].items():
                    if status == "up":
                        st.success(f"✅ {service}")
                    else:
                        st.error(f"❌ {service}")
        
        with col2:
            st.subheader("⚡ Performance Metrics")
            if "response_time_ms" in health:
                st.metric("Response Time", f"{health['response_time_ms']} ms")
            
            if "error" not in status:
                if status.get("celery", {}).get("workers_online", 0) > 0:
                    st.metric("Celery Workers", status["celery"]["workers_online"])
                else:
                    st.warning("No Celery workers online")
                
                st.metric("Total Documents", status.get("document_count", 0))
        
        # Detailed status
        if "error" not in status:
            st.subheader("📋 Detailed Status")
            st.json(status)
    
    if auto_refresh:
        time.sleep(5)
        st.rerun()


def main():
    """Main application entry point."""
    init_session_state()
    
    # Header
    st.title("🧠 Second Brain RAG System")
    st.markdown("---")
    
    # Sidebar setup
    page = setup_sidebar()
    
    # Main content based on selected page
    if page == "Chat Interface":
        chat_interface()
    elif page == "Document Upload":
        document_upload()
    elif page == "Document Manager":
        document_manager()
    elif page == "Analytics":
        analytics_dashboard()
    elif page == "System Monitor":
        system_monitor()
    
    # Footer
    st.markdown("---")
    st.markdown("🚀 **Second Brain Database** - Powered by FastAPI, MongoDB, Celery, and Streamlit")


if __name__ == "__main__":
    main()