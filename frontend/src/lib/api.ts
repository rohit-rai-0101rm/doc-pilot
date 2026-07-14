import { request } from '@/lib/http';

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
};

export interface Thread {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: string;
  content: string;
  sequence: number;
  created_at: string;
}

export interface ThreadWithMessages extends Thread {
  messages: Message[];
}

export function listThreads() {
  return api.get<Thread[]>('/threads');
}

export function createThread(title?: string) {
  return api.post<Thread>('/threads', { title });
}

export function getThread(id: string) {
  return api.get<ThreadWithMessages>(`/threads/${id}`);
}
