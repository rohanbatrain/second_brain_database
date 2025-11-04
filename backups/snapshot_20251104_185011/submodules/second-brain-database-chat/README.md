# second-brain-database-chat

An agent chat application built with LangGraph and Next.js.

## Getting Started

### Prerequisites

- Node.js 20 or later
- pnpm (will be installed automatically if not present)

### Installation

1. Install dependencies:
```bash
pnpm install
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your API keys
```

### Running the Application

Start both the web UI and LangGraph server:

```bash
pnpm dev
```

This will start:
- Web server at: http://localhost:3000
- LangGraph server at: http://localhost:2024

## Project Structure

- `apps/web` - Next.js web application
- `apps/agents` - LangGraph agents

## Available Agents

- **React Agent** - A general-purpose ReAct agent
- **Memory Agent** - Agent with memory capabilities
- **Research Agent** - Research and retrieval agent
- **Retrieval Agent** - Document retrieval agent
