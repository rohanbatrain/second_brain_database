/**
 * Tool Card Component
 * Displays MCP tool details and provides execution trigger
 */

'use client';

import { Wrench, Play, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip';
import type { MCPTool } from '@/lib/types/mcp';

interface ToolCardProps {
    tool: MCPTool;
    onExecute: (tool: MCPTool) => void;
}

export function ToolCard({ tool, onExecute }: ToolCardProps) {
    return (
        <Card className="flex flex-col p-4 h-full hover:shadow-md transition-all hover:border-primary/50">
            <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400">
                        <Wrench className="w-5 h-5" />
                    </div>
                    <div>
                        <h3 className="font-medium leading-none">{tool.name}</h3>
                        {tool.category && (
                            <span className="text-xs text-muted-foreground">{tool.category}</span>
                        )}
                    </div>
                </div>

                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                                <Info className="w-4 h-4 text-muted-foreground" />
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p className="max-w-xs text-xs">{tool.description}</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
            </div>

            <p className="text-sm text-muted-foreground line-clamp-2 mb-4 flex-1">
                {tool.description}
            </p>

            <div className="flex items-center justify-between mt-auto pt-3 border-t border-border/50">
                <div className="flex gap-1">
                    {tool.tags?.slice(0, 2).map((tag) => (
                        <Badge key={tag} variant="secondary" className="text-[10px] h-5 px-1.5">
                            {tag}
                        </Badge>
                    ))}
                </div>

                <Button size="sm" onClick={() => onExecute(tool)} className="gap-1.5 h-8">
                    <Play className="w-3 h-3" />
                    Run
                </Button>
            </div>
        </Card>
    );
}
