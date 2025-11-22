/**
 * Document Card Component
 * Displays individual document details with actions
 */

'use client';

import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
    FileText,
    MoreVertical,
    Trash2,
    Download,
    CheckCircle2,
    AlertCircle,
    Loader2,
    File
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { cn } from '@/lib/utils';
import type { Document } from '@/lib/types/rag';

interface DocumentCardProps {
    document: Document;
    onDelete: (id: string) => Promise<void>;
}

export function DocumentCard({ document, onDelete }: DocumentCardProps) {
    const [isDeleting, setIsDeleting] = useState(false);
    const [showDeleteDialog, setShowDeleteDialog] = useState(false);

    const handleDelete = async () => {
        setIsDeleting(true);
        try {
            await onDelete(document.id);
        } catch (error) {
            console.error('Failed to delete document:', error);
            setIsDeleting(false);
        }
        setShowDeleteDialog(false);
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'completed': return 'text-green-500 bg-green-500/10';
            case 'processing': return 'text-blue-500 bg-blue-500/10';
            case 'failed': return 'text-red-500 bg-red-500/10';
            default: return 'text-muted-foreground bg-muted';
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'completed': return <CheckCircle2 className="w-3 h-3" />;
            case 'processing': return <Loader2 className="w-3 h-3 animate-spin" />;
            case 'failed': return <AlertCircle className="w-3 h-3" />;
            default: return null;
        }
    };

    const formatSize = (bytes: number) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    };

    return (
        <>
            <Card className="group relative overflow-hidden transition-all hover:shadow-md hover:border-primary/50">
                <div className="p-4 flex items-start gap-4">
                    <div className="p-3 rounded-lg bg-primary/5 text-primary">
                        <FileText className="w-6 h-6" />
                    </div>

                    <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                            <h3 className="font-medium truncate pr-6" title={document.filename}>
                                {document.filename}
                            </h3>

                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="ghost" size="icon" className="h-8 w-8 -mt-1 -mr-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <MoreVertical className="w-4 h-4" />
                                    </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                    <DropdownMenuItem disabled>
                                        <Download className="w-4 h-4 mr-2" />
                                        Download
                                    </DropdownMenuItem>
                                    <DropdownMenuItem
                                        className="text-destructive focus:text-destructive"
                                        onClick={() => setShowDeleteDialog(true)}
                                    >
                                        <Trash2 className="w-4 h-4 mr-2" />
                                        Delete
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>

                        <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                            <span>{formatSize(document.size)}</span>
                            <span>•</span>
                            <span>{formatDistanceToNow(new Date(document.upload_date), { addSuffix: true })}</span>
                        </div>

                        <div className="flex items-center gap-2 mt-3">
                            <Badge variant="secondary" className={cn("gap-1.5 h-5 px-2 text-[10px] font-medium border-0", getStatusColor(document.status))}>
                                {getStatusIcon(document.status)}
                                <span className="capitalize">{document.status}</span>
                            </Badge>

                            {document.chunks_count > 0 && (
                                <Badge variant="outline" className="h-5 px-2 text-[10px] text-muted-foreground">
                                    {document.chunks_count} chunks
                                </Badge>
                            )}
                        </div>
                    </div>
                </div>
            </Card>

            <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will permanently delete "{document.filename}" and remove all its indexed chunks from the database. This action cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleDelete}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            disabled={isDeleting}
                        >
                            {isDeleting ? 'Deleting...' : 'Delete'}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
}
