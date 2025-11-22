/**
 * Document Upload Area Component
 * Drag and drop zone for uploading files
 */

'use client';

import { useState, useRef } from 'react';
import { UploadCloud, File, X, Loader2, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { config } from '@/lib/config';
import { uploadDocument } from '@/lib/api/rag-client';
import { toast } from 'sonner';

interface DocumentUploadAreaProps {
    onUploadComplete?: () => void;
}

export function DocumentUploadArea({ onUploadComplete }: DocumentUploadAreaProps) {
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);

        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            await handleUpload(files[0]);
        }
    };

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(e.target.files || []);
        if (files.length > 0) {
            await handleUpload(files[0]);
        }
    };

    const handleUpload = async (file: File) => {
        // Validate file type
        const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
        if (!config.defaults.allowedFileTypes.includes(fileExtension)) {
            toast.error('Invalid file type', {
                description: `Allowed types: ${config.defaults.allowedFileTypes.join(', ')}`
            });
            return;
        }

        // Validate file size
        if (file.size > config.defaults.maxFileSize) {
            toast.error('File too large', {
                description: `Maximum size: ${config.defaults.maxFileSize / 1024 / 1024}MB`
            });
            return;
        }

        setIsUploading(true);
        setUploadProgress(0);

        try {
            const response = await uploadDocument(file, (progress) => {
                setUploadProgress(progress);
            });

            toast.success(`Uploaded ${response.filename}`, {
                description: `Successfully processed ${response.chunks_created} chunks.`
            });

            if (onUploadComplete) {
                onUploadComplete();
            }
        } catch (error) {
            toast.error('Upload failed', {
                description: error instanceof Error ? error.message : 'Unknown error'
            });
        } finally {
            setIsUploading(false);
            setUploadProgress(0);
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    };

    return (
        <div
            className={cn(
                "relative border-2 border-dashed rounded-xl p-8 transition-all duration-200 ease-in-out text-center",
                isDragging
                    ? "border-primary bg-primary/5 scale-[1.01]"
                    : "border-border hover:border-primary/50 hover:bg-muted/50",
                isUploading && "pointer-events-none opacity-80"
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            <input
                type="file"
                ref={fileInputRef}
                className="hidden"
                onChange={handleFileSelect}
                accept={config.defaults.allowedFileTypes.join(',')}
            />

            <div className="flex flex-col items-center gap-4">
                <div className={cn(
                    "w-16 h-16 rounded-full flex items-center justify-center transition-colors",
                    isDragging ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                )}>
                    {isUploading ? (
                        <Loader2 className="w-8 h-8 animate-spin" />
                    ) : (
                        <UploadCloud className="w-8 h-8" />
                    )}
                </div>

                <div className="space-y-1">
                    <h3 className="font-semibold text-lg">
                        {isUploading ? 'Uploading Document...' : 'Upload Documents'}
                    </h3>
                    <p className="text-sm text-muted-foreground max-w-xs mx-auto">
                        Drag and drop your files here, or click to browse.
                        Supported formats: PDF, TXT, MD, DOCX
                    </p>
                </div>

                {!isUploading && (
                    <Button
                        variant="secondary"
                        onClick={() => fileInputRef.current?.click()}
                    >
                        Select File
                    </Button>
                )}

                {isUploading && (
                    <div className="w-full max-w-xs space-y-2">
                        <Progress value={uploadProgress} className="h-2" />
                        <p className="text-xs text-muted-foreground">{Math.round(uploadProgress)}% complete</p>
                    </div>
                )}
            </div>
        </div>
    );
}
