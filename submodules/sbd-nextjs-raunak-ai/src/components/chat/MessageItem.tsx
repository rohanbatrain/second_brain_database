/**
 * Message Item Component
 * Renders individual chat messages (User/AI) with RAG sources and MCP tool calls
 */

'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
    User,
    Bot,
    Copy,
    Check,
    FileText,
    Wrench,
    ChevronDown,
    ChevronRight,
    ExternalLink
} from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { Message } from '@/lib/types/chat';
import type { RAGSource } from '@/lib/types/rag';
import type { MCPToolCall } from '@/lib/types/mcp';

interface MessageItemProps {
    message: Message;
}

export function MessageItem({ message }: MessageItemProps) {
    const isUser = message.role === 'user';
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(message.content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
                "flex gap-4 p-4 md:p-6 w-full max-w-4xl mx-auto",
                isUser ? "bg-muted/30" : "bg-background"
            )}
        >
            {/* Avatar */}
            <Avatar className={cn("w-8 h-8 mt-1", isUser ? "bg-muted" : "bg-primary/10")}>
                {isUser ? (
                    <AvatarFallback><User className="w-5 h-5 text-muted-foreground" /></AvatarFallback>
                ) : (
                    <AvatarFallback><Bot className="w-5 h-5 text-primary" /></AvatarFallback>
                )}
            </Avatar>

            {/* Content */}
            <div className="flex-1 space-y-2 overflow-hidden">
                <div className="flex items-center justify-between">
                    <span className="font-semibold text-sm">
                        {isUser ? 'You' : 'Raunak AI'}
                    </span>
                    {!isUser && (
                        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleCopy}>
                            {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                        </Button>
                    )}
                </div>

                {/* Message Text */}
                <div className="prose prose-sm dark:prose-invert max-w-none break-words whitespace-pre-wrap">
                    {message.content}
                    {message.streaming && (
                        <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse" />
                    )}
                </div>

                {/* RAG Sources */}
                {message.rag_sources && message.rag_sources.length > 0 && (
                    <RAGSources sources={message.rag_sources} />
                )}

                {/* MCP Tool Calls */}
                {message.mcp_tool_calls && message.mcp_tool_calls.length > 0 && (
                    <MCPToolCalls toolCalls={message.mcp_tool_calls} />
                )}
            </div>
        </motion.div>
    );
}

function RAGSources({ sources }: { sources: RAGSource[] }) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className="mt-4">
            <Button
                variant="outline"
                size="sm"
                onClick={() => setExpanded(!expanded)}
                className="gap-2 h-8 text-xs"
            >
                <FileText className="w-3 h-3 text-blue-500" />
                {sources.length} Source{sources.length !== 1 ? 's' : ''} Used
                {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            </Button>

            {expanded && (
                <div className="grid gap-2 mt-2 animate-in slide-in-from-top-2 duration-200">
                    {sources.map((source, i) => (
                        <Card key={i} className="p-3 text-xs bg-muted/50 border-l-2 border-l-blue-500">
                            <div className="flex items-center justify-between mb-1">
                                <span className="font-medium truncate max-w-[200px]">
                                    {source.metadata.filename || 'Unknown Document'}
                                </span>
                                <Badge variant="secondary" className="text-[10px] h-4">
                                    {Math.round(source.score * 100)}% Match
                                </Badge>
                            </div>
                            <p className="text-muted-foreground line-clamp-2">{source.text}</p>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}

function MCPToolCalls({ toolCalls }: { toolCalls: MCPToolCall[] }) {
    return (
        <div className="mt-4 space-y-2">
            {toolCalls.map((tool, i) => (
                <Card key={i} className="p-3 text-xs bg-amber-50/50 dark:bg-amber-950/10 border-l-2 border-l-amber-500">
                    <div className="flex items-center gap-2 mb-2">
                        <Wrench className="w-3 h-3 text-amber-500" />
                        <span className="font-medium font-mono text-amber-700 dark:text-amber-400">
                            Used Tool: {tool.tool_name}
                        </span>
                    </div>

                    <div className="bg-background/50 p-2 rounded border border-border/50 font-mono overflow-x-auto">
                        <div className="text-muted-foreground mb-1">Input:</div>
                        <pre className="text-[10px]">{JSON.stringify(tool.parameters, null, 2)}</pre>

                        {tool.result !== undefined && tool.result !== null && (
                            <>
                                <div className="text-muted-foreground mt-2 mb-1">Result:</div>
                                <pre className="text-[10px] text-green-600 dark:text-green-400">
                                    {JSON.stringify(tool.result, null, 2)}
                                </pre>
                            </>
                        )}
                    </div>
                </Card>
            ))}
        </div>
    );
}
