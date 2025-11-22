/**
 * Main Chat Page
 * Integrates MessageList and ChatInput
 */

'use client';

import { Header } from '@/components/layout/Header';
import { ChatInput } from '@/components/chat/ChatInput';
import { MessageList } from '@/components/chat/MessageList';

export default function ChatPage() {
  return (
    <div className="flex flex-col h-full bg-background/50">
      <Header title="Chat with Raunak" subtitle="AI-powered conversations" />

      <MessageList />

      <ChatInput />
    </div>
  );
}
