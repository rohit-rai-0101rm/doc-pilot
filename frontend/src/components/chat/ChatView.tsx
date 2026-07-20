import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import { useState, type FormEvent } from 'react';

import { Button } from '@/components/ui/button';
import type { Message, ThreadWithMessages } from '@/lib/api';
import { env } from '@/lib/env';
import { authHeaders } from '@/lib/http';

interface ChatViewProps {
  thread: ThreadWithMessages;
}

function toUIMessages(messages: Message[]) {
  return messages.map((message) => ({
    id: message.id,
    role: message.role as 'user' | 'assistant',
    parts: [{ type: 'text' as const, text: message.content }],
  }));
}

export function ChatView({ thread }: ChatViewProps) {
  const [input, setInput] = useState('');
  const { messages, sendMessage, status } = useChat({
    id: thread.id,
    messages: toUIMessages(thread.messages),
    transport: new DefaultChatTransport({
      api: `${env.apiBaseUrl}/chat/stream`,
      headers: authHeaders,
      body: { threadId: thread.id },
    }),
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!input.trim()) return;
    sendMessage({ text: input });
    setInput('');
  }

  const busy = status === 'submitted' || status === 'streaming';

  return (
    <div className="flex flex-1 flex-col gap-4">
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto">
        {messages.map((message) => (
          <div key={message.id} className="text-sm">
            <span className="font-medium">{message.role === 'user' ? 'You' : 'Assistant'}:</span>{' '}
            {message.parts
              .filter((part) => part.type === 'text')
              .map((part) => part.text)
              .join('')}
          </div>
        ))}
      </div>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask a question..."
          disabled={busy}
          className="border-input flex-1 rounded-md border px-3 py-2 text-sm"
        />
        <Button type="submit" disabled={busy}>
          Send
        </Button>
      </form>
    </div>
  );
}
