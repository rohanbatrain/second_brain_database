/**
 * Tools Page
 * Browser for MCP tools
 */

'use client';

import { useState, useEffect } from 'react';
import { Search, Filter, Wrench, Loader2 } from 'lucide-react';
import { Header } from '@/components/layout/Header';
import { ToolCard } from '@/components/tools/ToolCard';
import { ToolExecutionDialog } from '@/components/tools/ToolExecutionDialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { listMCPTools } from '@/lib/api/mcp-client';
import type { MCPTool } from '@/lib/types/mcp';
import { toast } from 'sonner';

export default function ToolsPage() {
    const [tools, setTools] = useState<MCPTool[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedTool, setSelectedTool] = useState<MCPTool | null>(null);
    const [isExecutionOpen, setIsExecutionOpen] = useState(false);

    useEffect(() => {
        const fetchTools = async () => {
            setIsLoading(true);
            try {
                const response = await listMCPTools();
                setTools(response.tools);
            } catch (error) {
                toast.error('Failed to load tools');
                console.error(error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchTools();
    }, []);

    const handleExecute = (tool: MCPTool) => {
        setSelectedTool(tool);
        setIsExecutionOpen(true);
    };

    const filteredTools = tools.filter(tool =>
        tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tool.description.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="flex flex-col h-full bg-background/50">
            <Header title="MCP Tools" subtitle="Explore and execute available tools" />

            <div className="flex-1 p-6 overflow-y-auto">
                <div className="max-w-6xl mx-auto space-y-8">

                    {/* Actions Bar */}
                    <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
                        <div className="relative w-full sm:w-96">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input
                                placeholder="Search tools..."
                                className="pl-9 bg-background"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                        </div>

                        <div className="flex items-center gap-2 w-full sm:w-auto">
                            <Button variant="outline" size="icon">
                                <Filter className="w-4 h-4" />
                            </Button>
                        </div>
                    </div>

                    {/* Tools Grid */}
                    {isLoading ? (
                        <div className="flex items-center justify-center h-64">
                            <Loader2 className="w-8 h-8 animate-spin text-primary" />
                        </div>
                    ) : filteredTools.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {filteredTools.map((tool) => (
                                <ToolCard
                                    key={tool.name}
                                    tool={tool}
                                    onExecute={handleExecute}
                                />
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-20">
                            <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
                                <Wrench className="w-8 h-8 text-muted-foreground" />
                            </div>
                            <h3 className="text-lg font-medium">No tools found</h3>
                            <p className="text-muted-foreground mt-1">
                                Try adjusting your search query
                            </p>
                        </div>
                    )}
                </div>
            </div>

            <ToolExecutionDialog
                tool={selectedTool}
                open={isExecutionOpen}
                onOpenChange={setIsExecutionOpen}
            />
        </div>
    );
}
