import { Button } from '@/components/ui/button';
import type { Thread } from '@/lib/api';
import { cn } from '@/lib/utils';

interface ThreadSidebarProps {
  threads: Thread[];
  selectedThreadId: string | null;
  onSelectThread: (id: string) => void;
  onNewThread: () => void;
  creating: boolean;
}

export function ThreadSidebar({
  threads,
  selectedThreadId,
  onSelectThread,
  onNewThread,
  creating,
}: ThreadSidebarProps) {
  return (
    <div className="flex w-64 shrink-0 flex-col gap-2 border-r p-4">
      <Button onClick={onNewThread} disabled={creating}>
        {creating ? 'Creating…' : 'New chat'}
      </Button>
      <ul className="flex flex-col gap-1">
        {threads.map((thread) => (
          <li key={thread.id}>
            <button
              type="button"
              onClick={() => onSelectThread(thread.id)}
              className={cn(
                'hover:bg-muted w-full rounded-md px-2 py-1.5 text-left text-sm',
                thread.id === selectedThreadId && 'bg-muted font-medium',
              )}
            >
              {thread.title ?? 'Untitled chat'}
            </button>
          </li>
        ))}
        {threads.length === 0 && (
          <li className="text-muted-foreground px-2 py-1.5 text-sm">No chats yet.</li>
        )}
      </ul>
    </div>
  );
}
