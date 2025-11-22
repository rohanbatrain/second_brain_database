/**
 * Message List Component
 * Renders the list of messages with auto-scrolling
 */

'use client';

import { useEffect, useRef } from 'react';
import { useChatStore } from '@/lib/store/chat-store';
import { MessageItem } from './MessageItem';
import { Sparkles } from 'lucide-react';

export function MessageList() {
    const { messages } = useChatStore();
    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, messages.length]);

    if (messages.length === 0) {
        return (
            <div className="flex-1 flex items-center justify-center p-8">
                <div className="text-center space-y-4 max-w-2xl">
                    <div className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center animate-glow">
                        <Sparkles className="w-10 h-10 text-white" />
                    </div>

                    <h2 className="text-3xl font-bold gradient-text">
                        Welcome to Raunak AI
                    </h2>

                    <p className="text-muted-foreground text-lg">
                        Your intelligent second brain powered by advanced RAG, 140+ MCP tools, and local LLM models.
                    </p>

                    <div className="grid grid-cols-3 gap-4 mt-8">
                        <div className="glass p-4 rounded-lg">
                            <div className="text-2xl font-bold text-primary">RAG</div>
                            <div className="text-sm text-muted-foreground">Document Intelligence</div>
                        </div>
                        <div className="glass p-4 rounded-lg">
                            <div className="text-2xl font-bold text-secondary">140+</div>
                            <div className="text-sm text-muted-foreground">MCP Tools</div>
                        </div>
                        <div className="glass p-4 rounded-lg">
                            <div className="text-2xl font-bold text-accent">3</div>
                            <div className="text-sm text-muted-foreground">LLM Models</div>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="flex-1 overflow-y-auto scroll-smooth">
            <div className="flex flex-col pb-4">
                {messages.map((message) => (
                    <MessageItem key={message.id} message={message} />
                ))}
                <div ref={bottomRef} />
            </div>
        </div>
    );
}
