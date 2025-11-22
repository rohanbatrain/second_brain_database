/**
 * Settings Page
 * Configuration for Models, RAG, and Application preferences
 */

'use client';

import { useState, useEffect } from 'react';
import { Save, RotateCcw, Monitor, Moon, Sun, Cpu, Database, Wrench } from 'lucide-react';
import { Header } from '@/components/layout/Header';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useTheme } from 'next-themes';
import { useChatStore } from '@/lib/store/chat-store';
import { config, type ModelId } from '@/lib/config';
import { toast } from 'sonner';

export default function SettingsPage() {
    const { theme, setTheme } = useTheme();
    const {
        selectedModel,
        setModel,
        useRAG,
        toggleRAG,
        useMCP,
        toggleMCP
    } = useChatStore();

    // Local state for settings that might not be in global store yet
    const [ragThreshold, setRagThreshold] = useState(0.7);
    const [ragLimit, setRagLimit] = useState(5);
    const [apiKey, setApiKey] = useState('');

    const handleSave = () => {
        // In a real app, this would persist to backend or local storage
        toast.success('Settings saved successfully');
    };

    const handleReset = () => {
        setRagThreshold(0.7);
        setRagLimit(5);
        setApiKey('');
        toast.info('Settings reset to defaults');
    };

    return (
        <div className="flex flex-col h-full bg-background/50">
            <Header title="Settings" subtitle="Configure Raunak AI preferences" />

            <div className="flex-1 p-6 overflow-y-auto">
                <div className="max-w-4xl mx-auto space-y-6">

                    <Tabs defaultValue="general" className="w-full">
                        <TabsList className="grid w-full grid-cols-4 mb-8">
                            <TabsTrigger value="general" className="gap-2">
                                <Monitor className="w-4 h-4" />
                                General
                            </TabsTrigger>
                            <TabsTrigger value="models" className="gap-2">
                                <Cpu className="w-4 h-4" />
                                Models
                            </TabsTrigger>
                            <TabsTrigger value="rag" className="gap-2">
                                <Database className="w-4 h-4" />
                                RAG
                            </TabsTrigger>
                            <TabsTrigger value="mcp" className="gap-2">
                                <Wrench className="w-4 h-4" />
                                MCP
                            </TabsTrigger>
                        </TabsList>

                        {/* General Settings */}
                        <TabsContent value="general">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Appearance</CardTitle>
                                    <CardDescription>Customize how Raunak AI looks and feels.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-6">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Theme</Label>
                                            <p className="text-sm text-muted-foreground">Select your preferred color theme.</p>
                                        </div>
                                        <Select value={theme} onValueChange={setTheme}>
                                            <SelectTrigger className="w-[180px]">
                                                <SelectValue placeholder="Select theme" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="light">
                                                    <div className="flex items-center gap-2">
                                                        <Sun className="w-4 h-4" /> Light
                                                    </div>
                                                </SelectItem>
                                                <SelectItem value="dark">
                                                    <div className="flex items-center gap-2">
                                                        <Moon className="w-4 h-4" /> Dark
                                                    </div>
                                                </SelectItem>
                                                <SelectItem value="system">
                                                    <div className="flex items-center gap-2">
                                                        <Monitor className="w-4 h-4" /> System
                                                    </div>
                                                </SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>

                        {/* Model Settings */}
                        <TabsContent value="models">
                            <Card>
                                <CardHeader>
                                    <CardTitle>AI Models</CardTitle>
                                    <CardDescription>Configure the AI models used for generation.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-6">
                                    <div className="space-y-4">
                                        <div className="space-y-2">
                                            <Label>Default Model</Label>
                                            <Select value={selectedModel} onValueChange={(v) => setModel(v as ModelId)}>
                                                <SelectTrigger>
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {config.models.map((model) => (
                                                        <SelectItem key={model.id} value={model.id}>
                                                            {model.name} - <span className="text-muted-foreground text-xs">{model.description}</span>
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>

                                        <div className="space-y-2">
                                            <Label>API Key (Optional)</Label>
                                            <Input
                                                type="password"
                                                placeholder="sk-..."
                                                value={apiKey}
                                                onChange={(e) => setApiKey(e.target.value)}
                                            />
                                            <p className="text-xs text-muted-foreground">
                                                Leave blank to use the system-configured API key.
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>

                        {/* RAG Settings */}
                        <TabsContent value="rag">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Retrieval Augmented Generation</CardTitle>
                                    <CardDescription>Fine-tune how Raunak AI uses your documents.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-6">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Enable RAG</Label>
                                            <p className="text-sm text-muted-foreground">Allow the AI to search your documents.</p>
                                        </div>
                                        <Switch checked={useRAG} onCheckedChange={toggleRAG} />
                                    </div>

                                    <div className="space-y-4">
                                        <div className="space-y-2">
                                            <div className="flex items-center justify-between">
                                                <Label>Similarity Threshold ({ragThreshold})</Label>
                                            </div>
                                            <Slider
                                                value={[ragThreshold]}
                                                min={0}
                                                max={1}
                                                step={0.05}
                                                onValueChange={([v]) => setRagThreshold(v)}
                                            />
                                            <p className="text-xs text-muted-foreground">
                                                Minimum score for a document chunk to be considered relevant.
                                            </p>
                                        </div>

                                        <div className="space-y-2">
                                            <div className="flex items-center justify-between">
                                                <Label>Max Chunks ({ragLimit})</Label>
                                            </div>
                                            <Slider
                                                value={[ragLimit]}
                                                min={1}
                                                max={20}
                                                step={1}
                                                onValueChange={([v]) => setRagLimit(v)}
                                            />
                                            <p className="text-xs text-muted-foreground">
                                                Maximum number of document chunks to include in the context.
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>

                        {/* MCP Settings */}
                        <TabsContent value="mcp">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Model Context Protocol</CardTitle>
                                    <CardDescription>Manage tool access and permissions.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-6">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Enable MCP Tools</Label>
                                            <p className="text-sm text-muted-foreground">Allow the AI to use external tools.</p>
                                        </div>
                                        <Switch checked={useMCP} onCheckedChange={toggleMCP} />
                                    </div>

                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Auto-Approve Tools</Label>
                                            <p className="text-sm text-muted-foreground">Run safe tools without asking for confirmation.</p>
                                        </div>
                                        <Switch defaultChecked />
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>
                    </Tabs>

                    <div className="flex justify-end gap-4">
                        <Button variant="outline" onClick={handleReset} className="gap-2">
                            <RotateCcw className="w-4 h-4" />
                            Reset Defaults
                        </Button>
                        <Button onClick={handleSave} className="gap-2">
                            <Save className="w-4 h-4" />
                            Save Changes
                        </Button>
                    </div>

                </div>
            </div>
        </div>
    );
}
