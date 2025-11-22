/**
 * Tool Execution Dialog
 * Interface for entering tool parameters and viewing results
 */

'use client';

import { useState } from 'react';
import { Play, Loader2, CheckCircle2, AlertCircle, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { executeMCPTool } from '@/lib/api/mcp-client';
import type { MCPTool, MCPToolExecutionResponse } from '@/lib/types/mcp';
import { toast } from 'sonner';

interface ToolExecutionDialogProps {
    tool: MCPTool | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function ToolExecutionDialog({ tool, open, onOpenChange }: ToolExecutionDialogProps) {
    const [isExecuting, setIsExecuting] = useState(false);
    const [params, setParams] = useState<Record<string, string>>({});
    const [result, setResult] = useState<MCPToolExecutionResponse | null>(null);

    if (!tool) return null;

    const handleParamChange = (key: string, value: string) => {
        setParams(prev => ({ ...prev, [key]: value }));
    };

    const handleExecute = async () => {
        setIsExecuting(true);
        setResult(null);

        try {
            // Convert params to appropriate types if needed (simplified here)
            const response = await executeMCPTool({
                tool_name: tool.name,
                parameters: params
            });
            setResult(response);
            toast.success('Tool executed successfully');
        } catch (error) {
            toast.error('Execution failed', {
                description: error instanceof Error ? error.message : 'Unknown error'
            });
        } finally {
            setIsExecuting(false);
        }
    };

    const handleCopyResult = () => {
        if (result) {
            navigator.clipboard.writeText(JSON.stringify(result.result, null, 2));
            toast.success('Result copied to clipboard');
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Play className="w-5 h-5 text-primary" />
                        Execute {tool.name}
                    </DialogTitle>
                    <DialogDescription>
                        {tool.description}
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 overflow-y-auto py-4 space-y-6">
                    {/* Parameters Form */}
                    <div className="space-y-4">
                        <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Parameters</h4>
                        <div className="grid gap-4">
                            {Object.entries(tool.parameters.properties).map(([key, prop]: [string, any]) => (
                                <div key={key} className="grid gap-2">
                                    <Label htmlFor={key} className="flex items-center gap-2">
                                        {key}
                                        {tool.parameters.required?.includes(key) && (
                                            <span className="text-destructive text-xs">*</span>
                                        )}
                                    </Label>
                                    {prop.type === 'string' && prop.description?.length > 50 ? (
                                        <Textarea
                                            id={key}
                                            placeholder={prop.description}
                                            value={params[key] || ''}
                                            onChange={(e) => handleParamChange(key, e.target.value)}
                                        />
                                    ) : (
                                        <Input
                                            id={key}
                                            type={prop.type === 'integer' || prop.type === 'number' ? 'number' : 'text'}
                                            placeholder={prop.description}
                                            value={params[key] || ''}
                                            onChange={(e) => handleParamChange(key, e.target.value)}
                                        />
                                    )}
                                    {prop.description && (
                                        <p className="text-[10px] text-muted-foreground">{prop.description}</p>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Result Display */}
                    {result && (
                        <div className="space-y-2 animate-in fade-in slide-in-from-bottom-4">
                            <div className="flex items-center justify-between">
                                <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Result</h4>
                                <Button variant="ghost" size="sm" className="h-6 gap-1" onClick={handleCopyResult}>
                                    <Copy className="w-3 h-3" />
                                    Copy
                                </Button>
                            </div>
                            <div className={cn(
                                "rounded-lg border p-4 font-mono text-xs overflow-x-auto",
                                result.status === 'success'
                                    ? "bg-green-50/50 border-green-200 dark:bg-green-950/10 dark:border-green-900"
                                    : "bg-red-50/50 border-red-200 dark:bg-red-950/10 dark:border-red-900"
                            )}>
                                <pre>{JSON.stringify(result.result, null, 2)}</pre>
                            </div>
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Close
                    </Button>
                    <Button onClick={handleExecute} disabled={isExecuting}>
                        {isExecuting ? (
                            <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                Running...
                            </>
                        ) : (
                            <>
                                <Play className="w-4 h-4 mr-2" />
                                Execute Tool
                            </>
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
