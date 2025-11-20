# RAG Document Upload - Frontend Integration Guide

## Overview

The Document Upload feature allows users to upload documents (PDF, DOCX, TXT, MD, etc.) to the RAG system for processing, indexing, and intelligent querying. This guide covers complete frontend integration with code examples for web, mobile, and desktop applications.

## Feature Capabilities

- ✅ **Multiple File Formats**: PDF, DOCX, PPTX, TXT, MD, images
- ✅ **Async & Sync Processing**: Choose between immediate or background processing
- ✅ **Progress Tracking**: Monitor upload and processing status via task IDs
- ✅ **Automatic Chunking**: Documents automatically split into searchable chunks
- ✅ **Metadata Extraction**: Extract titles, authors, dates, and custom metadata
- ✅ **Vector Indexing**: Automatic embedding generation and vector storage

## API Endpoints

### 1. Upload File (Multipart/Form-Data)
**Recommended for file uploads from forms**

```http
POST /api/rag/upload
Authorization: Bearer {jwt_token}
Content-Type: multipart/form-data
```

**Form Fields:**
- `file`: File to upload (required)
- `async_processing`: Boolean (default: true)

### 2. Upload Document (JSON)
**For programmatic uploads with text content**

```http
POST /api/rag/documents/upload
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "content": "Document text content...",
  "filename": "example.txt",
  "content_type": "text/plain",
  "metadata": {
    "author": "John Doe",
    "category": "research"
  },
  "process_async": true
}
```

**Response:**
```json
{
  "document_id": "doc_a1b2c3d4",
  "status": "processing",
  "task_id": "celery-task-uuid",
  "chunks_created": null,
  "processing_time": null,
  "message": "Document queued for async processing. Task ID: celery-task-uuid"
}
```

## Frontend Integration Examples

### React/TypeScript Web Application

#### 1. Setup API Client

```typescript
// src/api/rag.ts
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

export interface DocumentUploadResponse {
  document_id: string;
  status: 'processing' | 'completed' | 'failed';
  task_id?: string;
  chunks_created?: number;
  processing_time?: number;
  message: string;
}

export interface TaskStatusResponse {
  task_id: string;
  status: 'pending' | 'started' | 'success' | 'failure';
  result?: any;
  progress?: any;
  error?: string;
}

class RAGService {
  private token: string;

  constructor(token: string) {
    this.token = token;
  }

  /**
   * Upload a file for RAG processing
   */
  async uploadFile(
    file: File,
    asyncProcessing: boolean = true
  ): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('async_processing', String(asyncProcessing));

    const response = await axios.post(
      `${API_BASE_URL}/rag/upload`,
      formData,
      {
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            console.log(`Upload Progress: ${percentCompleted}%`);
          }
        },
      }
    );

    return response.data;
  }

  /**
   * Check processing task status
   */
  async getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    const response = await axios.get(
      `${API_BASE_URL}/rag/tasks/${taskId}/status`,
      {
        headers: {
          'Authorization': `Bearer ${this.token}`,
        },
      }
    );

    return response.data;
  }

  /**
   * Poll task status until completion
   */
  async waitForTaskCompletion(
    taskId: string,
    onProgress?: (status: TaskStatusResponse) => void,
    pollInterval: number = 2000,
    maxAttempts: number = 60
  ): Promise<TaskStatusResponse> {
    let attempts = 0;

    return new Promise((resolve, reject) => {
      const interval = setInterval(async () => {
        try {
          attempts++;
          const status = await this.getTaskStatus(taskId);

          if (onProgress) {
            onProgress(status);
          }

          if (status.status === 'success') {
            clearInterval(interval);
            resolve(status);
          } else if (status.status === 'failure') {
            clearInterval(interval);
            reject(new Error(status.error || 'Task failed'));
          } else if (attempts >= maxAttempts) {
            clearInterval(interval);
            reject(new Error('Task timeout'));
          }
        } catch (error) {
          clearInterval(interval);
          reject(error);
        }
      }, pollInterval);
    });
  }
}

export default RAGService;
```

#### 2. React Component with Upload

```tsx
// src/components/DocumentUpload.tsx
import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import RAGService from '../api/rag';

interface UploadState {
  uploading: boolean;
  processing: boolean;
  progress: number;
  error: string | null;
  documentId: string | null;
  taskId: string | null;
}

const DocumentUpload: React.FC<{ token: string }> = ({ token }) => {
  const [state, setState] = useState<UploadState>({
    uploading: false,
    processing: false,
    progress: 0,
    error: null,
    documentId: null,
    taskId: null,
  });

  const ragService = new RAGService(token);

  const handleUpload = async (files: File[]) => {
    if (files.length === 0) return;

    const file = files[0];

    setState({
      uploading: true,
      processing: false,
      progress: 0,
      error: null,
      documentId: null,
      taskId: null,
    });

    try {
      // Upload file
      const uploadResult = await ragService.uploadFile(file, true);

      setState(prev => ({
        ...prev,
        uploading: false,
        processing: true,
        documentId: uploadResult.document_id,
        taskId: uploadResult.task_id || null,
      }));

      // Wait for processing to complete
      if (uploadResult.task_id) {
        const finalStatus = await ragService.waitForTaskCompletion(
          uploadResult.task_id,
          (status) => {
            // Update progress
            if (status.progress?.percent) {
              setState(prev => ({
                ...prev,
                progress: status.progress.percent,
              }));
            }
          }
        );

        setState(prev => ({
          ...prev,
          processing: false,
          progress: 100,
        }));

        console.log('Document processed:', finalStatus);
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        uploading: false,
        processing: false,
        error: error instanceof Error ? error.message : 'Upload failed',
      }));
    }
  };

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      handleUpload(acceptedFiles);
    },
    [token]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
    },
    maxFiles: 1,
  });

  return (
    <div className="document-upload">
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? 'active' : ''}`}
        style={{
          border: '2px dashed #ccc',
          borderRadius: '8px',
          padding: '40px',
          textAlign: 'center',
          cursor: 'pointer',
        }}
      >
        <input {...getInputProps()} />
        {isDragActive ? (
          <p>Drop the file here...</p>
        ) : (
          <p>Drag & drop a document here, or click to select</p>
        )}
      </div>

      {state.uploading && (
        <div className="upload-status">
          <p>Uploading...</p>
        </div>
      )}

      {state.processing && (
        <div className="processing-status">
          <p>Processing document... {state.progress}%</p>
          <progress value={state.progress} max={100} />
        </div>
      )}

      {state.error && (
        <div className="error-message" style={{ color: 'red' }}>
          <p>Error: {state.error}</p>
        </div>
      )}

      {state.documentId && !state.processing && (
        <div className="success-message" style={{ color: 'green' }}>
          <p>✓ Document uploaded successfully!</p>
          <p>Document ID: {state.documentId}</p>
        </div>
      )}
    </div>
  );
};

export default DocumentUpload;
```

### Flutter Mobile Application

```dart
// lib/services/rag_service.dart
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:path/path.dart' as path;

class DocumentUploadResponse {
  final String documentId;
  final String status;
  final String? taskId;
  final int? chunksCreated;
  final double? processingTime;
  final String message;

  DocumentUploadResponse({
    required this.documentId,
    required this.status,
    this.taskId,
    this.chunksCreated,
    this.processingTime,
    required this.message,
  });

  factory DocumentUploadResponse.fromJson(Map<String, dynamic> json) {
    return DocumentUploadResponse(
      documentId: json['document_id'],
      status: json['status'],
      taskId: json['task_id'],
      chunksCreated: json['chunks_created'],
      processingTime: json['processing_time']?.toDouble(),
      message: json['message'],
    );
  }
}

class TaskStatusResponse {
  final String taskId;
  final String status;
  final dynamic result;
  final Map<String, dynamic>? progress;
  final String? error;

  TaskStatusResponse({
    required this.taskId,
    required this.status,
    this.result,
    this.progress,
    this.error,
  });

  factory TaskStatusResponse.fromJson(Map<String, dynamic> json) {
    return TaskStatusResponse(
      taskId: json['task_id'],
      status: json['status'],
      result: json['result'],
      progress: json['progress'],
      error: json['error'],
    );
  }
}

class RAGService {
  final String baseUrl;
  final String token;
  final Dio _dio;

  RAGService({
    required this.baseUrl,
    required this.token,
  }) : _dio = Dio(BaseOptions(
          baseUrl: baseUrl,
          headers: {
            'Authorization': 'Bearer $token',
          },
        ));

  /// Upload a file for RAG processing
  Future<DocumentUploadResponse> uploadFile(
    File file, {
    bool asyncProcessing = true,
    Function(int, int)? onUploadProgress,
  }) async {
    final fileName = path.basename(file.path);
    
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(
        file.path,
        filename: fileName,
      ),
      'async_processing': asyncProcessing.toString(),
    });

    final response = await _dio.post(
      '/rag/upload',
      data: formData,
      onSendProgress: onUploadProgress,
    );

    return DocumentUploadResponse.fromJson(response.data);
  }

  /// Get task status
  Future<TaskStatusResponse> getTaskStatus(String taskId) async {
    final response = await _dio.get('/rag/tasks/$taskId/status');
    return TaskStatusResponse.fromJson(response.data);
  }

  /// Poll task status until completion
  Future<TaskStatusResponse> waitForTaskCompletion(
    String taskId, {
    Function(TaskStatusResponse)? onProgress,
    Duration pollInterval = const Duration(seconds: 2),
    int maxAttempts = 60,
  }) async {
    int attempts = 0;

    while (attempts < maxAttempts) {
      await Future.delayed(pollInterval);
      
      final status = await getTaskStatus(taskId);
      
      if (onProgress != null) {
        onProgress(status);
      }

      if (status.status == 'success') {
        return status;
      } else if (status.status == 'failure') {
        throw Exception(status.error ?? 'Task failed');
      }

      attempts++;
    }

    throw Exception('Task timeout after $maxAttempts attempts');
  }
}
```

```dart
// lib/screens/document_upload_screen.dart
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../services/rag_service.dart';

class DocumentUploadScreen extends StatefulWidget {
  final String token;
  final String serverUrl;

  const DocumentUploadScreen({
    Key? key,
    required this.token,
    required this.serverUrl,
  }) : super(key: key);

  @override
  State<DocumentUploadScreen> createState() => _DocumentUploadScreenState();
}

class _DocumentUploadScreenState extends State<DocumentUploadScreen> {
  late RAGService _ragService;
  
  bool _uploading = false;
  bool _processing = false;
  double _uploadProgress = 0.0;
  double _processingProgress = 0.0;
  String? _error;
  String? _documentId;
  String? _taskId;

  @override
  void initState() {
    super.initState();
    _ragService = RAGService(
      baseUrl: widget.serverUrl,
      token: widget.token,
    );
  }

  Future<void> _pickAndUploadFile() async {
    // Pick file
    FilePickerResult? result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'docx', 'txt', 'md'],
    );

    if (result == null) return;

    final file = File(result.files.single.path!);

    setState(() {
      _uploading = true;
      _processing = false;
      _uploadProgress = 0.0;
      _processingProgress = 0.0;
      _error = null;
      _documentId = null;
      _taskId = null;
    });

    try {
      // Upload file
      final uploadResult = await _ragService.uploadFile(
        file,
        asyncProcessing: true,
        onUploadProgress: (sent, total) {
          setState(() {
            _uploadProgress = sent / total;
          });
        },
      );

      setState(() {
        _uploading = false;
        _processing = true;
        _documentId = uploadResult.documentId;
        _taskId = uploadResult.taskId;
      });

      // Wait for processing
      if (uploadResult.taskId != null) {
        final finalStatus = await _ragService.waitForTaskCompletion(
          uploadResult.taskId!,
          onProgress: (status) {
            if (status.progress != null && status.progress!['percent'] != null) {
              setState(() {
                _processingProgress = status.progress!['percent'] / 100.0;
              });
            }
          },
        );

        setState(() {
          _processing = false;
          _processingProgress = 1.0;
        });

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('✓ Document processed successfully!'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (error) {
      setState(() {
        _uploading = false;
        _processing = false;
        _error = error.toString();
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: $error'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Upload Document'),
      ),
      body: Padding(
        padding: EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Upload button
            ElevatedButton.icon(
              onPressed: _uploading || _processing ? null : _pickAndUploadFile,
              icon: Icon(Icons.upload_file),
              label: Text('Select Document'),
              style: ElevatedButton.styleFrom(
                padding: EdgeInsets.all(16),
              ),
            ),
            
            SizedBox(height: 24),
            
            // Upload progress
            if (_uploading) ...[
              Text('Uploading...'),
              SizedBox(height: 8),
              LinearProgressIndicator(value: _uploadProgress),
              SizedBox(height: 8),
              Text('${(_uploadProgress * 100).toStringAsFixed(0)}%'),
            ],
            
            // Processing progress
            if (_processing) ...[
              Text('Processing document...'),
              SizedBox(height: 8),
              LinearProgressIndicator(value: _processingProgress),
              SizedBox(height: 8),
              Text('${(_processingProgress * 100).toStringAsFixed(0)}%'),
              if (_taskId != null)
                Text('Task ID: $_taskId', style: TextStyle(fontSize: 12)),
            ],
            
            // Error message
            if (_error != null) ...[
              SizedBox(height: 16),
              Container(
                padding: EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.red.shade100,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  'Error: $_error',
                  style: TextStyle(color: Colors.red.shade900),
                ),
              ),
            ],
            
            // Success message
            if (_documentId != null && !_processing) ...[
              SizedBox(height: 16),
              Container(
                padding: EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.green.shade100,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '✓ Document uploaded successfully!',
                      style: TextStyle(
                        color: Colors.green.shade900,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    SizedBox(height: 4),
                    Text(
                      'Document ID: $_documentId',
                      style: TextStyle(
                        color: Colors.green.shade900,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
```

### Python Desktop Application (PyQt/PySide)

```python
# rag_uploader.py
import sys
import requests
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QLabel, QProgressBar, QFileDialog, QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSignal

class UploadWorker(QThread):
    """Background worker for file upload"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, file_path, token, server_url):
        super().__init__()
        self.file_path = file_path
        self.token = token
        self.server_url = server_url

    def run(self):
        try:
            # Upload file
            with open(self.file_path, 'rb') as f:
                files = {'file': (Path(self.file_path).name, f)}
                data = {'async_processing': 'true'}
                headers = {'Authorization': f'Bearer {self.token}'}
                
                response = requests.post(
                    f'{self.server_url}/api/rag/upload',
                    files=files,
                    data=data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    self.progress.emit(100)
                    self.finished.emit(result)
                else:
                    self.error.emit(f'Upload failed: {response.text}')
                    
        except Exception as e:
            self.error.emit(str(e))

class DocumentUploaderWindow(QMainWindow):
    def __init__(self, token, server_url):
        super().__init__()
        self.token = token
        self.server_url = server_url
        self.upload_worker = None
        
        self.setWindowTitle('RAG Document Uploader')
        self.setGeometry(100, 100, 500, 300)
        
        self.init_ui()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Select file button
        self.select_btn = QPushButton('Select Document')
        self.select_btn.clicked.connect(self.select_file)
        layout.addWidget(self.select_btn)
        
        # File label
        self.file_label = QLabel('No file selected')
        layout.addWidget(self.file_label)
        
        # Upload button
        self.upload_btn = QPushButton('Upload')
        self.upload_btn.clicked.connect(self.upload_file)
        self.upload_btn.setEnabled(False)
        layout.addWidget(self.upload_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel('')
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            'Select Document',
            '',
            'Documents (*.pdf *.docx *.txt *.md);;All Files (*)'
        )
        
        if file_path:
            self.selected_file = file_path
            self.file_label.setText(f'Selected: {Path(file_path).name}')
            self.upload_btn.setEnabled(True)
    
    def upload_file(self):
        if not hasattr(self, 'selected_file'):
            return
        
        self.upload_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText('Uploading...')
        
        # Create and start upload worker
        self.upload_worker = UploadWorker(
            self.selected_file,
            self.token,
            self.server_url
        )
        self.upload_worker.progress.connect(self.on_progress)
        self.upload_worker.finished.connect(self.on_finished)
        self.upload_worker.error.connect(self.on_error)
        self.upload_worker.start()
    
    def on_progress(self, value):
        self.progress_bar.setValue(value)
    
    def on_finished(self, result):
        self.progress_bar.setVisible(False)
        self.upload_btn.setEnabled(True)
        self.select_btn.setEnabled(True)
        
        self.status_label.setText(
            f'✓ Upload successful! Document ID: {result["document_id"]}'
        )
        
        QMessageBox.information(
            self,
            'Success',
            f'Document uploaded successfully!\n\nDocument ID: {result["document_id"]}'
        )
    
    def on_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.upload_btn.setEnabled(True)
        self.select_btn.setEnabled(True)
        
        self.status_label.setText(f'Error: {error_msg}')
        
        QMessageBox.critical(self, 'Error', f'Upload failed:\n{error_msg}')

if __name__ == '__main__':
    # Replace with your actual token and server URL
    TOKEN = 'your_jwt_token_here'
    SERVER_URL = 'http://localhost:8000'
    
    app = QApplication(sys.argv)
    window = DocumentUploaderWindow(TOKEN, SERVER_URL)
    window.show()
    sys.exit(app.exec())
```

## Best Practices

### 1. Error Handling
```typescript
try {
  const result = await ragService.uploadFile(file);
} catch (error) {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 401) {
      // Token expired, redirect to login
      window.location.href = '/login';
    } else if (error.response?.status === 413) {
      // File too large
      alert('File is too large. Maximum size is 100MB.');
    } else {
      // Other errors
      console.error('Upload failed:', error.response?.data);
    }
  }
}
```

### 2. File Validation
```typescript
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB
const ALLOWED_TYPES = ['pdf', 'docx', 'txt', 'md'];

function validateFile(file: File): string | null {
  const extension = file.name.split('.').pop()?.toLowerCase();
  
  if (!extension || !ALLOWED_TYPES.includes(extension)) {
    return 'Invalid file type. Allowed: PDF, DOCX, TXT, MD';
  }
  
  if (file.size > MAX_FILE_SIZE) {
    return 'File too large. Maximum size is 100MB';
  }
  
  return null; // Valid
}
```

### 3. Progress Monitoring
```typescript
// Create WebSocket connection for real-time progress
const ws = new WebSocket(`ws://localhost:8000/ws/tasks/${taskId}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Progress:', data.progress);
};
```

## Testing

### cURL Examples

```bash
# Upload a file
curl -X POST "http://localhost:8000/api/rag/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@document.pdf" \
  -F "async_processing=true"

# Check task status
curl -X GET "http://localhost:8000/api/rag/tasks/TASK_ID/status" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Next Steps

- [RAG Query Integration](./02_rag_query.md)
- [Document Management](./03_document_management.md)
- [Vector Search](./04_vector_search.md)
