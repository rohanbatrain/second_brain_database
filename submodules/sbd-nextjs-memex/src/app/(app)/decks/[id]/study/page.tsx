'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getStudyCards, reviewCard } from '@/lib/api';
import { ArrowLeft, Check, X } from 'lucide-react';
import Link from 'next/link';
import { Card } from '@/types';

export default function Study() {
    const { id } = useParams() as { id: string };
    const router = useRouter();
    const queryClient = useQueryClient();

    const [currentCardIndex, setCurrentCardIndex] = useState(0);
    const [showAnswer, setShowAnswer] = useState(false);
    const [sessionCards, setSessionCards] = useState<Card[]>([]);

    const { data: cards, isLoading } = useQuery({
        queryKey: ['study', id],
        queryFn: () => getStudyCards(id),
    });

    useEffect(() => {
        if (cards) {
            setSessionCards(cards);
        }
    }, [cards]);

    const reviewMutation = useMutation({
        mutationFn: ({ cardId, rating }: { cardId: string; rating: number }) =>
            reviewCard(cardId, rating),
        onSuccess: () => {
            // Move to next card
            setShowAnswer(false);
            setCurrentCardIndex(prev => prev + 1);
            // Invalidate queries to refresh data if needed
            queryClient.invalidateQueries({ queryKey: ['cards', id] });
        },
    });

    const handleRating = (rating: number) => {
        const currentCard = sessionCards[currentCardIndex];
        if (!currentCard) return;

        reviewMutation.mutate({ cardId: currentCard._id, rating });
    };

    if (isLoading) return <div className="p-8 text-center">Loading study session...</div>;

    if (sessionCards.length === 0) {
        return (
            <div className="container mx-auto p-8 text-center max-w-2xl">
                <div className="bg-white dark:bg-gray-800 p-12 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
                    <h2 className="text-2xl font-bold mb-4">All caught up!</h2>
                    <p className="text-gray-500 mb-8">You have no cards due for review in this deck.</p>
                    <Link
                        href={`/decks/${id}`}
                        className="inline-flex items-center text-blue-600 hover:underline"
                    >
                        <ArrowLeft size={20} className="mr-2" />
                        Back to Deck
                    </Link>
                </div>
            </div>
        );
    }

    if (currentCardIndex >= sessionCards.length) {
        return (
            <div className="container mx-auto p-8 text-center max-w-2xl">
                <div className="bg-white dark:bg-gray-800 p-12 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
                    <h2 className="text-2xl font-bold mb-4">Session Complete!</h2>
                    <p className="text-gray-500 mb-8">You have reviewed all {sessionCards.length} cards for this session.</p>
                    <Link
                        href={`/decks/${id}`}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium transition-colors"
                    >
                        Back to Deck
                    </Link>
                </div>
            </div>
        );
    }

    const currentCard = sessionCards[currentCardIndex];

    return (
        <div className="container mx-auto p-8 max-w-3xl h-screen flex flex-col">
            <div className="flex justify-between items-center mb-8">
                <Link
                    href={`/decks/${id}`}
                    className="text-gray-500 hover:text-gray-700 transition-colors"
                >
                    <ArrowLeft size={24} />
                </Link>
                <div className="text-sm font-medium text-gray-500">
                    Card {currentCardIndex + 1} of {sessionCards.length}
                </div>
            </div>

            <div className="flex-1 flex flex-col justify-center">
                <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden min-h-[400px] flex flex-col">
                    <div className="flex-1 p-12 flex items-center justify-center text-center border-b border-gray-100 dark:border-gray-700">
                        <div className="text-2xl font-medium">
                            {currentCard.front_content}
                        </div>
                    </div>

                    {showAnswer ? (
                        <div className="flex-1 p-12 flex flex-col items-center justify-center text-center bg-gray-50 dark:bg-gray-900/50 animate-in fade-in duration-300">
                            <div className="text-xl text-gray-700 dark:text-gray-300 mb-8">
                                {currentCard.back_content}
                            </div>

                            <div className="grid grid-cols-4 gap-4 w-full max-w-lg">
                                <button
                                    onClick={() => handleRating(0)}
                                    className="p-4 rounded-xl bg-red-100 text-red-700 hover:bg-red-200 transition-colors font-medium text-sm"
                                >
                                    Again
                                    <div className="text-xs opacity-70 mt-1">&lt; 1m</div>
                                </button>
                                <button
                                    onClick={() => handleRating(3)}
                                    className="p-4 rounded-xl bg-orange-100 text-orange-700 hover:bg-orange-200 transition-colors font-medium text-sm"
                                >
                                    Hard
                                    <div className="text-xs opacity-70 mt-1">2d</div>
                                </button>
                                <button
                                    onClick={() => handleRating(4)}
                                    className="p-4 rounded-xl bg-green-100 text-green-700 hover:bg-green-200 transition-colors font-medium text-sm"
                                >
                                    Good
                                    <div className="text-xs opacity-70 mt-1">4d</div>
                                </button>
                                <button
                                    onClick={() => handleRating(5)}
                                    className="p-4 rounded-xl bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors font-medium text-sm"
                                >
                                    Easy
                                    <div className="text-xs opacity-70 mt-1">7d</div>
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="p-8 bg-gray-50 dark:bg-gray-900/50 flex justify-center">
                            <button
                                onClick={() => setShowAnswer(true)}
                                className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 rounded-xl font-medium transition-colors shadow-sm"
                            >
                                Show Answer
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
