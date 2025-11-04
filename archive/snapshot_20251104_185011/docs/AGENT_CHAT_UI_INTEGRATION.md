# Agent Chat UI Integration Guide

> **Complete guide to integrating LangChain's Agent Chat UI with Second Brain Database**

---

## 📋 Overview

This guide shows you how to connect the [Agent Chat UI](https://github.com/langchain-ai/agent-chat-ui) to your Second Brain Database LangChain agents.

**Agent Chat UI** is a Next.js application that provides:
- 💬 Real-time conversational interface
- 🔧 Tool call visualization
- ⏱️ Time-travel debugging
- 🔍 State inspection
- 👤 Human-in-the-loop support

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Chat UI                             │
│                   (Next.js Frontend)                         │
│                                                              │
│  • Chat interface                                            │
│  • Tool visualization                                        │
│  • State inspection                                          │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           Second Brain Database FastAPI Backend             │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ LangGraph API Endpoints (/api/v1/ai)                   │ │
│  │                                                         │ │
│  │ • POST /sessions - Create chat session                 │ │
│  │ • POST /chat - Send message                            │ │
│  │ • GET /sessions/{id} - Get session info                │ │
│  │ • WS /sessions/{id}/stream - Streaming chat            │ │
│  │ • GET /threads - List conversation threads             │ │
│  └────────────────────────────────────────────────────────┘ │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ LangChainOrchestrator                                  │ │
│  │                                                         │ │
│  │ • Agent management                                      │ │
│  │ • Tool execution                                        │ │
│  │ • Memory handling                                       │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Option 1: Use Hosted Agent Chat UI

The easiest way to get started:

1. **Visit [agentchat.vercel.app](https://agentchat.vercel.app)**
2. **Configure connection:**
   - Graph ID: `SecondBrainDatabase`
   - Deployment URL: `http://localhost:8000` (or your deployed URL)
   - LangSmith API key: (optional, for tracing)
3. **Start chatting!**

### Option 2: Run Agent Chat UI Locally

For development or customization:

```bash
# Option A: Using npx
npx create-agent-chat-app --project-name second-brain-chat-ui
cd second-brain-chat-ui
pnpm install
pnpm dev

# Option B: Clone repository
git clone https://github.com/langchain-ai/agent-chat-ui.git second-brain-chat-ui
cd second-brain-chat-ui
pnpm install
pnpm dev
```

Then visit `http://localhost:3000` and configure:
- **Graph ID**: `SecondBrainDatabase`
- **Deployment URL**: `http://localhost:8000`

---

## 🔧 Backend Setup

### Step 1: Update LangGraph Routes

We need to add LangGraph-compatible endpoints. Update your `routes/langgraph/routes.py`:

<function_calls>
<invoke name="replace_string_in_file">
<parameter name="filePath">/Users/rohan/Documents/repos/second_brain_database/src/second_brain_database/routes/langgraph/routes.py