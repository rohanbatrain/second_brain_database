/**
 * Documents Page
 * Manages document list, uploading, and searching
 */

'use client';

import { useState, useEffect } from 'react';
import { Search, Filter, Plus } from 'lucide-react';
import { Header } from '@/components/layout/Header';
import { DocumentCard } from '@/components/documents/DocumentCard';
import { DocumentUploadArea } from '@/components/documents/DocumentUploadArea';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from '@/components/ui/dialog';
import { listDocuments, deleteDocument } from '@/lib/api/rag-client';
import type { Document } from '@/lib/types/rag';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';

export default function DocumentsPage() {
    const [documents, setDocuments] = useState<Document[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [isUploadOpen, setIsUploadOpen] = useState(false);

    const fetchDocuments = async () => {
        setIsLoading(true);
        try {
            const response = await listDocuments(1, 100); // Fetch all for now
            setDocuments(response.documents);
        } catch (error) {
            toast.error('Failed to load documents');
            console.error(error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchDocuments();
    }, []);

    const handleDelete = async (id: string) => {
        await deleteDocument(id);
        toast.success('Document deleted');
        setDocuments(documents.filter(doc => doc.id !== id));
    };

    const filteredDocuments = documents.filter(doc =>
        doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="flex flex-col h-full bg-background/50">
            <Header title="Documents" subtitle="Manage your knowledge base" />

            <div className="flex-1 p-6 overflow-y-auto">
                <div className="max-w-6xl mx-auto space-y-8">

                    {/* Actions Bar */}
                    <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
                        <div className="relative w-full sm:w-96">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input
                                placeholder="Search documents..."
                                className="pl-9 bg-background"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                        </div>

                        <div className="flex items-center gap-2 w-full sm:w-auto">
                            <Button variant="outline" size="icon">
                                <Filter className="w-4 h-4" />
                            </Button>

                            <Dialog open={isUploadOpen} onOpenChange={setIsUploadOpen}>
                                <DialogTrigger asChild>
                                    <Button className="gap-2 flex-1 sm:flex-none">
                                        <Plus className="w-4 h-4" />
                                        Upload Document
                                    </Button>
                                </DialogTrigger>
                                <DialogContent className="sm:max-w-xl">
                                    <DialogHeader>
                                        <DialogTitle>Upload Document</DialogTitle>
                                    </DialogHeader>
                                    <div className="mt-4">
                                        <DocumentUploadArea onUploadComplete={() => {
                                            setIsUploadOpen(false);
                                            fetchDocuments();
                                        }} />
                                    </div>
                                </DialogContent>
                            </Dialog>
                        </div>
                    </div>

                    {/* Documents Grid */}
                    {isLoading ? (
                        <div className="flex items-center justify-center h-64">
                            <Loader2 className="w-8 h-8 animate-spin text-primary" />
                        </div>
                    ) : filteredDocuments.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {filteredDocuments.map((doc) => (
                                <DocumentCard
                                    key={doc.id}
                                    document={doc}
                                    onDelete={handleDelete}
                                />
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-20">
                            <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
                                <Search className="w-8 h-8 text-muted-foreground" />
                            </div>
                            <h3 className="text-lg font-medium">No documents found</h3>
                            <p className="text-muted-foreground mt-1">
                                {searchQuery ? 'Try adjusting your search query' : 'Upload your first document to get started'}
                            </p>
                            {!searchQuery && (
                                <Button
                                    variant="outline"
                                    className="mt-4"
                                    onClick={() => setIsUploadOpen(true)}
                                >
                                    Upload Document
                                </Button>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
