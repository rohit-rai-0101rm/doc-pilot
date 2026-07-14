import { useEffect, useState } from 'react';

import { ThreadSidebar } from '@/components/chat/ThreadSidebar';
import { Button } from '@/components/ui/button';
import { createThread, getThread, listThreads, type Thread, type ThreadWithMessages } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { supabase } from '@/lib/supabase';

export function HomePage() {
  const { session } = useAuth();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [selectedThread, setSelectedThread] = useState<ThreadWithMessages | null>(null);
  const [loadingThreads, setLoadingThreads] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listThreads()
      .then(setThreads)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load chats'))
      .finally(() => setLoadingThreads(false));
  }, []);

  async function handleSelectThread(id: string) {
    setError(null);
    try {
      const thread = await getThread(id);
      setSelectedThread(thread);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load chat');
    }
  }

  async function handleNewThread() {
    setCreating(true);
    setError(null);
    try {
      const thread = await createThread();
      setThreads((prev) => [thread, ...prev]);
      setSelectedThread({ ...thread, messages: [] });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create chat');
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      <ThreadSidebar
        threads={threads}
        selectedThreadId={selectedThread?.id ?? null}
        onSelectThread={handleSelectThread}
        onNewThread={handleNewThread}
        creating={creating}
      />
      <div className="flex flex-1 flex-col gap-4 p-6">
        <div className="flex items-center justify-between">
          <p className="text-muted-foreground text-sm">Logged in as {session?.user.email}.</p>
          <Button variant="outline" onClick={() => supabase.auth.signOut()}>
            Sign out
          </Button>
        </div>

        {error && <p className="text-destructive text-sm">{error}</p>}

        {loadingThreads ? (
          <p className="text-muted-foreground text-sm">Loading chats…</p>
        ) : selectedThread ? (
          <div className="flex flex-col gap-2">
            <h1 className="text-lg font-semibold">{selectedThread.title ?? 'Untitled chat'}</h1>
            {selectedThread.messages.length === 0 ? (
              <p className="text-muted-foreground text-sm">No messages yet.</p>
            ) : (
              selectedThread.messages.map((message) => (
                <p key={message.id} className="text-sm">
                  <span className="font-medium">{message.role}:</span> {message.content}
                </p>
              ))
            )}
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">Select a chat or start a new one.</p>
        )}
      </div>
    </div>
  );
}
