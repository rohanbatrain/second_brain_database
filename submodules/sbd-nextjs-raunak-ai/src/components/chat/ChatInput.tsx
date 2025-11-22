/**
 * Chat Input Component
 * Handles text input, file uploads, and model settings
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import {
    Send,
    Paperclip,
    Bot,
    Database,
    Wrench,
    X,
    Loader2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger
} from '@/components/ui/tooltip';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';
import { useChatStore } from '@/lib/store/chat-store';
import { config, type ModelId } from '@/lib/config';
import { uploadDocument } from '@/lib/api/rag-client';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

export function ChatInput() {
    const [input, setInput] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const {
        sendMessage,
        isLoading,
        selectedModel,
        setModel,
        useRAG,
        toggleRAG,
        useMCP,
        toggleMCP
    } = useChatStore();

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, [input]);

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    const handleSubmit = async () => {
        if (!input.trim() || isLoading) return;

        const message = input;
        setInput('');

        // Reset height
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
        }

        await sendMessage(message);
    };

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setIsUploading(true);
        const toastId = toast.loading('Uploading document...');

        try {
            const response = await uploadDocument(file, (progress) => {
                // Could update a progress bar here
            });

            toast.success(`Uploaded ${response.filename}`, {
                id: toastId,
                description: `Processed ${response.chunks_created} chunks. Ready for RAG.`
            });

            // Auto-enable RAG if not already enabled
            if (!useRAG) toggleRAG();

        } catch (error) {
            toast.error('Upload failed', {
                id: toastId,
                description: error instanceof Error ? error.message : 'Unknown error'
            });
        } finally {
            setIsUploading(false);
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    };

    const currentModelName = config.models.find(m => m.id === selectedModel)?.name || selectedModel;

    return (
        <div className="p-4 border-t border-border/50 bg-background/50 backdrop-blur-sm">
            <div className="max-w-4xl mx-auto space-y-4">

                {/* Controls Bar */}
                <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide">
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="outline" size="sm" className="gap-2 h-8">
                                <Bot className="w-4 h-4 text-primary" />
                                <span className="text-xs font-medium">{currentModelName}</span>
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="start">
                            {config.models.map((model) => (
                                <DropdownMenuItem
                                    key={model.id}
                                    onClick={() => setModel(model.id as ModelId)}
                                    className="gap-2"
                                >
                                    {selectedModel === model.id && <div className="w-1.5 h-1.5 rounded-full bg-primary" />}
                                    <span className={selectedModel === model.id ? 'font-medium' : 'ml-3.5'}>
                                        {model.name}
                                    </span>
                                </DropdownMenuItem>
                            ))}
                        </DropdownMenuContent>
                    </DropdownMenu>

                    <div className="h-4 w-[1px] bg-border mx-1" />

                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant={useRAG ? "secondary" : "ghost"}
                                    size="sm"
                                    onClick={toggleRAG}
                                    className={cn("gap-2 h-8", useRAG && "bg-blue-500/10 text-blue-600 hover:bg-blue-500/20 dark:text-blue-400")}
                                >
                                    <Database className="w-4 h-4" />
                                    <span className="text-xs font-medium">RAG</span>
                                    {useRAG && <Badge variant="secondary" className="h-4 px-1 text-[10px] bg-blue-500/20 text-blue-600 dark:text-blue-400 border-0">ON</Badge>}
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>Retrieval-Augmented Generation</TooltipContent>
                        </Tooltip>
                    </TooltipProvider>

                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant={useMCP ? "secondary" : "ghost"}
                                    size="sm"
                                    onClick={toggleMCP}
                                    className={cn("gap-2 h-8", useMCP && "bg-amber-500/10 text-amber-600 hover:bg-amber-500/20 dark:text-amber-400")}
                                >
                                    <Wrench className="w-4 h-4" />
                                    <span className="text-xs font-medium">MCP Tools</span>
                                    {useMCP && <Badge variant="secondary" className="h-4 px-1 text-[10px] bg-amber-500/20 text-amber-600 dark:text-amber-400 border-0">ON</Badge>}
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>Model Context Protocol Tools</TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                </div>

                {/* Input Area */}
                <div className="relative flex items-end gap-2 p-2 rounded-xl border border-border/50 bg-background shadow-sm focus-within:ring-1 focus-within:ring-ring/50 transition-all">
                    <input
                        type="file"
                        ref={fileInputRef}
                        className="hidden"
                        onChange={handleFileUpload}
                        accept={config.defaults.allowedFileTypes.join(',')}
                    />

                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-9 w-9 rounded-lg flex-shrink-0 text-muted-foreground hover:text-foreground"
                                    onClick={() => fileInputRef.current?.click()}
                                    disabled={isUploading || isLoading}
                                >
                                    {isUploading ? (
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                    ) : (
                                        <Paperclip className="w-5 h-5" />
                                    )}
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>Upload document for RAG</TooltipContent>
                        </Tooltip>
                    </TooltipProvider>

                    <Textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask Raunak anything..."
                        className="min-h-[36px] max-h-[200px] resize-none border-0 shadow-none focus-visible:ring-0 p-1.5 bg-transparent"
                        rows={1}
                    />

                    <Button
                        size="icon"
                        className={cn(
                            "h-9 w-9 rounded-lg flex-shrink-0 transition-all",
                            input.trim()
                                ? "bg-primary text-primary-foreground shadow-md hover:bg-primary/90"
                                : "bg-muted text-muted-foreground hover:bg-muted/80"
                        )}
                        onClick={handleSubmit}
                        disabled={!input.trim() || isLoading}
                    >
                        <Send className="w-4 h-4" />
                    </Button>
                </div>

                <div className="text-center">
                    <p className="text-[10px] text-muted-foreground">
                        Raunak AI can make mistakes. Check important info.
                    </p>
                </div>
            </div>
        </div>
    );
}
