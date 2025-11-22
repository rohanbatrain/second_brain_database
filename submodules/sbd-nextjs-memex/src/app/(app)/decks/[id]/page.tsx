'use client';

import { useQuery } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getDeck, getCards } from '@/lib/api';
import { ArrowLeft, Plus, Play } from 'lucide-react';

export default function DeckView() {
    const { id } = useParams() as { id: string };

    const { data: deck, isLoading: deckLoading } = useQuery({
        queryKey: ['deck', id],
        queryFn: () => getDeck(id),
    });

    const { data: cards, isLoading: cardsLoading } = useQuery({
        queryKey: ['cards', id],
        queryFn: () => getCards(id),
    });

    if (deckLoading || cardsLoading) return <div className="p-8 text-center">Loading...</div>;
    if (!deck) return <div className="p-8 text-center text-red-500">Deck not found</div>;

    return (
        <div className="container mx-auto p-8">
            <Link
                href="/"
                className="inline-flex items-center text-gray-500 hover:text-gray-700 mb-6 transition-colors"
            >
                <ArrowLeft size={20} className="mr-2" />
                Back to Dashboard
            </Link>

            <div className="flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-3xl font-bold mb-2">{deck.title}</h1>
                    <p className="text-gray-500">{cards?.length || 0} cards</p>
                </div>
                <div className="flex gap-4">
                    <Link
                        href={`/decks/${id}/add-card`}
                        className="bg-gray-100 hover:bg-gray-200 text-gray-800 px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
                    >
                        <Plus size={20} />
                        Add Card
                    </Link>
                    <Link
                        href={`/decks/${id}/study`}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
                    >
                        <Play size={20} />
                        Study Now
                    </Link>
                </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
                <table className="w-full text-left">
                    <thead className="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
                        <tr>
                            <th className="p-4 font-medium text-gray-500 dark:text-gray-400">Front</th>
                            <th className="p-4 font-medium text-gray-500 dark:text-gray-400">Back</th>
                            <th className="p-4 font-medium text-gray-500 dark:text-gray-400">Next Review</th>
                            <th className="p-4 font-medium text-gray-500 dark:text-gray-400">Interval</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                        {cards?.map((card) => (
                            <tr key={card._id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                                <td className="p-4">{card.front_content}</td>
                                <td className="p-4">{card.back_content}</td>
                                <td className="p-4 text-sm text-gray-500">
                                    {new Date(card.next_review_date).toLocaleDateString()}
                                </td>
                                <td className="p-4 text-sm text-gray-500">{card.interval} days</td>
                            </tr>
                        ))}
                        {cards?.length === 0 && (
                            <tr>
                                <td colSpan={4} className="p-8 text-center text-gray-500">
                                    No cards in this deck yet.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
