'use client';

import { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { createCard } from '@/lib/api';
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';

export default function AddCard() {
    const { id } = useParams() as { id: string };
    const [front, setFront] = useState('');
    const [back, setBack] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!front.trim() || !back.trim()) return;

        setIsSubmitting(true);
        try {
            await createCard(id, front, back);
            // Clear form to allow adding more cards easily
            setFront('');
            setBack('');
            // Optional: Show success toast
        } catch (error) {
            console.error('Failed to create card:', error);
            alert('Failed to create card');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="container mx-auto p-8 max-w-2xl">
            <Link
                href={`/decks/${id}`}
                className="inline-flex items-center text-gray-500 hover:text-gray-700 mb-6 transition-colors"
            >
                <ArrowLeft size={20} className="mr-2" />
                Back to Deck
            </Link>

            <div className="bg-white dark:bg-gray-800 p-8 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
                <h1 className="text-2xl font-bold mb-6">Add New Card</h1>

                <form onSubmit={handleSubmit}>
                    <div className="mb-6">
                        <label htmlFor="front" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                            Front (Question)
                        </label>
                        <textarea
                            id="front"
                            value={front}
                            onChange={(e) => setFront(e.target.value)}
                            className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all min-h-[100px]"
                            placeholder="e.g., What is the speed of light?"
                            required
                        />
                    </div>

                    <div className="mb-6">
                        <label htmlFor="back" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                            Back (Answer)
                        </label>
                        <textarea
                            id="back"
                            value={back}
                            onChange={(e) => setBack(e.target.value)}
                            className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all min-h-[100px]"
                            placeholder="e.g., 299,792,458 m/s"
                            required
                        />
                    </div>

                    <div className="flex gap-4">
                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isSubmitting ? 'Adding...' : 'Add Card'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
