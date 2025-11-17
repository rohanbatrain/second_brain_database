# 🧠 Second Brain RAG Streamlit Application

A modern, production-ready web interface for the Second Brain Database RAG (Retrieval-Augmented Generation) system. This application provides an intuitive chat interface with document management, real-time processing status, and comprehensive analytics.

## ✨ Features

### 🎯 Core Functionality
- **Interactive Chat Interface**: Natural language queries with conversation memory
- **Document Upload & Processing**: Support for PDF, Word, PowerPoint, images, and text files
- **Real-time Status Tracking**: Monitor document processing with live updates
- **Document Management**: Browse, search, reindex, and delete documents
- **Analytics Dashboard**: Usage statistics, query trends, and performance metrics
- **System Monitoring**: Health checks, Celery worker status, and system diagnostics

### 🔧 Technical Features
- **Async Processing**: Background document processing via Celery
- **Auto-refresh**: Real-time updates for processing status
- **Error Handling**: Comprehensive error handling with user-friendly messages
- **Responsive Design**: Modern UI that works on desktop and mobile
- **Authentication**: Secure token-based authentication
- **Production Ready**: Optimized for deployment with proper logging and monitoring

## 🚀 Quick Start

### Prerequisites
- Second Brain Database API running on `localhost:8000`
- Python 3.8+ with pip
- Valid authentication token from the main application

### Installation

1. **Install dependencies:**
```bash
pip install -r streamlit_requirements.txt
```

2. **Launch the application:**
```bash
./start_streamlit_app.sh
```

3. **Access the interface:**
   - Open your browser to `http://localhost:8501`
   - Enter your API token in the sidebar
   - Click "Connect" to authenticate

### Custom Configuration

**Launch on custom port:**
```bash
./start_streamlit_app.sh 8502
```

**Launch on custom host and port:**
```bash
./start_streamlit_app.sh 8502 0.0.0.0
```

**Direct Streamlit launch:**
```bash
streamlit run streamlit_rag_app.py --server.port 8501
```

## 📱 User Interface Guide

### 1. Authentication (Sidebar)
- Enter your API token from the main Second Brain Database application
- Click "Connect" to establish connection
- Green checkmark indicates successful connection

### 2. Chat Interface
- **Natural Language Queries**: Ask questions about your documents in plain English
- **AI Configuration**: Toggle AI generation, adjust result count and similarity threshold
- **Conversation Memory**: Maintains context across queries in the same session
- **Source Attribution**: View which documents contributed to each answer
- **Chat History**: Review previous queries and responses

### 3. Document Upload
- **Multi-file Support**: Upload multiple documents simultaneously
- **Format Support**: PDF, DOCX, PPTX, TXT, MD, PNG, JPG, JPEG
- **Processing Options**: Choose synchronous or asynchronous processing
- **Real-time Status**: Monitor processing progress with auto-refresh
- **Error Handling**: Clear feedback on upload success/failure

### 4. Document Manager
- **Document Library**: View all uploaded documents with metadata
- **Search & Filter**: Find documents by name, type, or upload date
- **Management Actions**: Reindex or delete documents
- **Storage Analytics**: View document sizes and storage usage

### 5. Analytics Dashboard
- **Usage Metrics**: Query volume, processing statistics, response times
- **Time-based Analysis**: View data for 1, 7, 30, or 90 days
- **Performance Insights**: Cache hit rates, error rates, popular queries
- **Visual Charts**: Interactive charts for trend analysis

### 6. System Monitor
- **Health Status**: Real-time system health and component status
- **Performance Metrics**: Response times, worker status, resource usage
- **Auto-refresh**: Optional automatic status updates every 5 seconds
- **Diagnostic Information**: Detailed system information for troubleshooting

## 🔧 Configuration

### Environment Variables
```bash
API_BASE_URL=http://localhost:8000    # Second Brain API base URL
STREAMLIT_PORT=8501                   # Streamlit port
STREAMLIT_HOST=localhost              # Streamlit host
```

### Streamlit Configuration
The application automatically creates `~/.streamlit/config.toml` with optimized settings:

```toml
[server]
port = 8501
address = "localhost"
headless = true
enableCORS = false
enableXsrfProtection = true

[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

## 🚨 Troubleshooting

### Common Issues

**"Please connect to the RAG system first"**
- Ensure the Second Brain API is running on `localhost:8000`
- Check your API token is valid
- Verify network connectivity

**Document upload fails**
- Check file format is supported
- Ensure file size is reasonable (< 100MB recommended)
- Verify sufficient disk space on server

**Slow processing times**
- Check Celery workers are running (`System Monitor` page)
- Monitor system resources (CPU, memory, disk)
- Consider using async processing for large files

**Chat responses are poor quality**
- Upload more relevant documents
- Adjust similarity threshold (try 0.6-0.8)
- Increase max results for broader context
- Ensure documents are properly indexed

### Performance Optimization

**For better response times:**
1. Enable async processing for document uploads
2. Use appropriate similarity thresholds (0.7 is usually good)
3. Limit max results to 5-10 for faster queries
4. Monitor and optimize your document collection

**For better accuracy:**
1. Upload high-quality, relevant documents
2. Use descriptive filenames and metadata
3. Regularly reindex documents after updates
4. Monitor analytics to understand query patterns

## 🔐 Security Considerations

- **Authentication**: Always use secure API tokens
- **Network Security**: Use HTTPS in production deployments
- **File Upload**: Validate file types and scan for malware
- **Access Control**: Implement proper user permissions in the main API
- **Data Privacy**: Ensure compliance with data protection regulations

## 🏭 Production Deployment

### Docker Deployment (Recommended)

1. **Create Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY streamlit_requirements.txt .
RUN pip install -r streamlit_requirements.txt

COPY streamlit_rag_app.py .
COPY start_streamlit_app.sh .

EXPOSE 8501
CMD ["./start_streamlit_app.sh", "8501", "0.0.0.0"]
```

2. **Build and run:**
```bash
docker build -t second-brain-streamlit .
docker run -p 8501:8501 -e API_BASE_URL=http://your-api:8000 second-brain-streamlit
```

### Reverse Proxy Setup (Nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### SSL/HTTPS Configuration

```bash
# Using Let's Encrypt
sudo certbot --nginx -d your-domain.com
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

This project is part of the Second Brain Database system. See the main repository for license information.

## 🆘 Support

- **Documentation**: Check the main Second Brain Database documentation
- **Issues**: Report bugs and request features in the main repository
- **Discussions**: Use GitHub Discussions for questions and community support

## 🔗 Related Projects

- **Main API**: Second Brain Database FastAPI backend
- **Inspiration**: [fahdmirza/doclingwithollama](https://github.com/fahdmirza/doclingwithollama)
- **Docling**: Advanced document processing library

---

**🚀 Built with ❤️ using Streamlit, FastAPI, MongoDB, Celery, and modern Python practices.**