# Production React Components (Continued)

## MessageList Component

```tsx
// src/components/RAGChat/MessageList.tsx
import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Message } from '../../types/rag';
import SourceCard from './SourceCard';
import styles from './styles.module.css';

interface MessageListProps {
  messages: Message[];
}

const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  return (
    <div className={styles.messageList}>
      {messages.map((message) => (
        <div
          key={message.id}
          className={`${styles.message} ${
            message.role === 'user' ? styles.userMessage : styles.assistantMessage
          } ${message.error ? styles.errorMessage : ''}`}
        >
          <div className={styles.messageHeader}>
            <div className={styles.messageAvatar}>
              {message.role === 'user' ? '👤' : '🤖'}
            </div>
            <div className={styles.messageInfo}>
              <span className={styles.messageSender}>
                {message.role === 'user' ? 'You' : 'AI Assistant'}
              </span>
              <span className={styles.messageTime}>
                {message.timestamp.toLocaleTimeString()}
              </span>
            </div>
          </div>

          <div className={styles.messageContent}>
            <ReactMarkdown
              components={{
                code({ node, inline, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline && match ? (
                    <SyntaxHighlighter
                      style={vscDarkPlus}
                      language={match[1]}
                      PreTag="div"
                      {...props}
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Sources */}
          {message.sources && message.sources.length > 0 && (
            <div className={styles.sources}>
              <p className={styles.sourcesLabel}>
                📚 Sources ({message.sources.length}):
              </p>
              <div className={styles.sourcesList}>
                {message.sources.slice(0, 3).map((chunk, idx) => (
                  <SourceCard key={idx} chunk={chunk} />
                ))}
              </div>
              {message.sources.length > 3 && (
                <p className={styles.moreSources}>
                  +{message.sources.length - 3} more sources
                </p>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default MessageList;
```

## SourceCard Component

```tsx
// src/components/RAGChat/SourceCard.tsx
import React, { useState } from 'react';
import { DocumentChunk } from '../../types/rag';
import styles from './styles.module.css';

interface SourceCardProps {
  chunk: DocumentChunk;
}

const SourceCard: React.FC<SourceCardProps> = ({ chunk }) => {
  const [expanded, setExpanded] = useState(false);

  const fileName = chunk.metadata.filename || 'Unknown';
  const score = (chunk.score * 100).toFixed(0);
  const page = chunk.metadata.page;
  const preview = chunk.text.substring(0, 150);
  const hasMore = chunk.text.length > 150;

  return (
    <div className={styles.sourceCard}>
      <div className={styles.sourceHeader}>
        <div className={styles.sourceInfo}>
          <span className={styles.sourceIcon}>📄</span>
          <span className={styles.sourceName} title={fileName}>
            {fileName}
          </span>
        </div>
        <div className={styles.sourceScore}>
          <span className={styles.scoreValue}>{score}%</span>
          <span className={styles.scoreLabel}>relevance</span>
        </div>
      </div>

      {page && (
        <div className={styles.sourceMeta}>
          <span>Page {page}</span>
        </div>
      )}

      <div className={styles.sourceText}>
        {expanded ? chunk.text : preview}
        {hasMore && !expanded && '...'}
      </div>

      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className={styles.expandButton}
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}
    </div>
  );
};

export default SourceCard;
```

## MessageInput Component

```tsx
// src/components/RAGChat/MessageInput.tsx
import React, { useState, useRef, KeyboardEvent } from 'react';
import styles from './styles.module.css';

interface MessageInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

const MessageInput: React.FC<MessageInputProps> = ({ onSend, disabled = false }) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput('');
      
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  return (
    <form onSubmit={handleSubmit} className={styles.inputForm}>
      <div className={styles.inputContainer}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your documents..."
          disabled={disabled}
          className={styles.input}
          rows={1}
        />
        <button
          type="submit"
          disabled={disabled || !input.trim()}
          className={styles.sendButton}
          aria-label="Send message"
        >
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
            />
          </svg>
        </button>
      </div>
      <p className={styles.inputHint}>
        Press <kbd>Enter</kbd> to send, <kbd>Shift+Enter</kbd> for new line
      </p>
    </form>
  );
};

export default MessageInput;
```

## Chat Styles

```css
/* src/components/RAGChat/styles.module.css */
.container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #ffffff;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid #e2e8f0;
  background-color: #f7fafc;
}

.headerContent {
  flex: 1;
}

.title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1a202c;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 14px;
  color: #718096;
}

.subtitle code {
  padding: 2px 6px;
  background-color: #e2e8f0;
  border-radius: 4px;
  font-family: 'Monaco', 'Courier New', monospace;
  font-size: 12px;
}

.clearButton {
  padding: 8px 16px;
  border: 1px solid #cbd5e0;
  border-radius: 6px;
  background-color: white;
  color: #2d3748;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.clearButton:hover {
  background-color: #f7fafc;
  border-color: #a0aec0;
}

.messagesContainer {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.emptyState {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: #718096;
}

.emptyIcon {
  width: 80px;
  height: 80px;
  margin-bottom: 16px;
  color: #cbd5e0;
}

.emptyState p {
  margin: 0 0 24px;
  font-size: 16px;
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 400px;
}

.suggestionsLabel {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 500;
  color: #4a5568;
}

.suggestions button {
  padding: 12px 16px;
  border: 1px solid #cbd5e0;
  border-radius: 8px;
  background-color: white;
  color: #2d3748;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.suggestions button:hover {
  background-color: #f7fafc;
  border-color: #4299e1;
  color: #4299e1;
}

.messageList {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: 12px;
  max-width: 80%;
}

.userMessage {
  align-self: flex-end;
  background-color: #ebf8ff;
  border: 1px solid #bee3f8;
}

.assistantMessage {
  align-self: flex-start;
  background-color: #f7fafc;
  border: 1px solid #e2e8f0;
}

.errorMessage {
  background-color: #fff5f5;
  border-color: #fc8181;
}

.messageHeader {
  display: flex;
  align-items: center;
  gap: 8px;
}

.messageAvatar {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.messageInfo {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.messageSender {
  font-size: 14px;
  font-weight: 600;
  color: #1a202c;
}

.messageTime {
  font-size: 12px;
  color: #718096;
}

.messageContent {
  line-height: 1.6;
  color: #2d3748;
}

.messageContent p {
  margin: 0 0 12px;
}

.messageContent p:last-child {
  margin-bottom: 0;
}

.messageContent code {
  padding: 2px 6px;
  background-color: #edf2f7;
  border-radius: 3px;
  font-family: 'Monaco', 'Courier New', monospace;
  font-size: 14px;
}

.messageContent pre {
  margin: 12px 0;
  padding: 0;
  border-radius: 8px;
  overflow: hidden;
}

.messageContent pre code {
  padding: 0;
  background-color: transparent;
}

.sources {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.sourcesLabel {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #4a5568;
}

.sourcesList {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sourceCard {
  padding: 12px;
  background-color: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.sourceCard:hover {
  border-color: #cbd5e0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.sourceHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.sourceInfo {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.sourceIcon {
  font-size: 14px;
  flex-shrink: 0;
}

.sourceName {
  font-size: 13px;
  font-weight: 500;
  color: #2d3748;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sourceScore {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  flex-shrink: 0;
}

.scoreValue {
  font-size: 14px;
  font-weight: 600;
  color: #4299e1;
}

.scoreLabel {
  font-size: 10px;
  color: #718096;
  text-transform: uppercase;
}

.sourceMeta {
  margin-bottom: 8px;
  font-size: 12px;
  color: #718096;
}

.sourceText {
  font-size: 13px;
  line-height: 1.5;
  color: #4a5568;
}

.expandButton {
  margin-top: 8px;
  padding: 4px 8px;
  border: none;
  background: none;
  color: #4299e1;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.2s ease;
}

.expandButton:hover {
  color: #2b6cb0;
}

.moreSources {
  margin: 8px 0 0;
  font-size: 12px;
  color: #718096;
  text-align: center;
}

.loadingIndicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px;
  color: #718096;
}

.loadingDots {
  display: flex;
  gap: 6px;
}

.loadingDots span {
  width: 8px;
  height: 8px;
  background-color: #4299e1;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out;
}

.loadingDots span:nth-child(1) {
  animation-delay: -0.32s;
}

.loadingDots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

.loadingIndicator p {
  margin: 0;
  font-size: 14px;
}

.inputForm {
  padding: 16px 24px;
  border-top: 1px solid #e2e8f0;
  background-color: white;
}

.inputContainer {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input {
  flex: 1;
  min-height: 44px;
  max-height: 150px;
  padding: 12px 16px;
  border: 1px solid #cbd5e0;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  resize: none;
  transition: border-color 0.2s ease;
}

.input:focus {
  outline: none;
  border-color: #4299e1;
  box-shadow: 0 0 0 3px rgba(66, 153, 225, 0.1);
}

.input:disabled {
  background-color: #f7fafc;
  color: #a0aec0;
  cursor: not-allowed;
}

.sendButton {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background-color: #4299e1;
  color: white;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.sendButton:hover:not(:disabled) {
  background-color: #3182ce;
}

.sendButton:disabled {
  background-color: #cbd5e0;
  cursor: not-allowed;
}

.sendButton svg {
  width: 20px;
  height: 20px;
}

.inputHint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #a0aec0;
  text-align: center;
}

.inputHint kbd {
  padding: 2px 6px;
  background-color: #f7fafc;
  border: 1px solid #e2e8f0;
  border-radius: 3px;
  font-family: inherit;
  font-size: 11px;
}
```

## Error Boundary

```tsx
// src/components/common/ErrorBoundary.tsx
import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
    
    // Send to error tracking service (e.g., Sentry)
    // Sentry.captureException(error, { extra: errorInfo });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
    });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          maxWidth: '600px',
          margin: '0 auto',
        }}>
          <h2>Something went wrong</h2>
          <p style={{ color: '#666', margin: '16px 0' }}>
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <button
            onClick={this.handleReset}
            style={{
              padding: '10px 24px',
              backgroundColor: '#4299e1',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
```

## Complete App Integration

```tsx
// src/App.tsx
import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ErrorBoundary from './components/common/ErrorBoundary';
import DocumentUpload from './components/DocumentUpload';
import RAGChat from './components/RAGChat';
import './App.css';

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'upload' | 'chat'>('chat');

  return (
    <ErrorBoundary>
      <div className="app">
        <nav className="navbar">
          <div className="nav-content">
            <h1 className="nav-title">Second Brain RAG</h1>
            <div className="nav-tabs">
              <button
                className={`nav-tab ${activeTab === 'chat' ? 'active' : ''}`}
                onClick={() => setActiveTab('chat')}
              >
                💬 Chat
              </button>
              <button
                className={`nav-tab ${activeTab === 'upload' ? 'active' : ''}`}
                onClick={() => setActiveTab('upload')}
              >
                📤 Upload
              </button>
            </div>
          </div>
        </nav>

        <main className="main-content">
          {activeTab === 'chat' && (
            <RAGChat
              onError={(error) => {
                console.error('Chat error:', error);
                // Show toast notification
              }}
            />
          )}
          
          {activeTab === 'upload' && (
            <div className="upload-container">
              <DocumentUpload
                onUploadComplete={(documentId) => {
                  console.log('Upload complete:', documentId);
                  // Show success notification
                  // Optionally switch to chat tab
                }}
                onError={(error) => {
                  console.error('Upload error:', error);
                  // Show error notification
                }}
              />
            </div>
          )}
        </main>
      </div>
    </ErrorBoundary>
  );
};

export default App;
```

```css
/* src/App.css */
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.app {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f7fafc;
}

.navbar {
  background-color: white;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.nav-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.nav-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #1a202c;
}

.nav-tabs {
  display: flex;
  gap: 8px;
}

.nav-tab {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  background-color: transparent;
  color: #718096;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-tab:hover {
  background-color: #f7fafc;
  color: #2d3748;
}

.nav-tab.active {
  background-color: #4299e1;
  color: white;
}

.main-content {
  flex: 1;
  overflow: hidden;
}

.upload-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 24px;
}
```

## Environment Variables

```env
# .env.production
REACT_APP_API_URL=https://api.yourproduction.com/api
REACT_APP_WS_URL=wss://api.yourproduction.com

# .env.development
REACT_APP_API_URL=http://localhost:8000/api
REACT_APP_WS_URL=ws://localhost:8000
```

## Package.json Dependencies

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "axios": "^1.6.0",
    "react-dropzone": "^14.2.3",
    "react-markdown": "^9.0.0",
    "react-syntax-highlighter": "^15.5.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@types/react-syntax-highlighter": "^15.5.10",
    "typescript": "^5.3.0"
  }
}
```

This completes the production-ready React integration with all components, styles, error handling, and best practices!
