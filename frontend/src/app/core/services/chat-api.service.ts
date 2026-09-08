import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '@env/environment';
import { ApiService } from '@core/services/api.service';
import { AuthService } from '@core/services/auth.service';
import { ChatDetail, ChatStreamEvent, ChatSummary } from '@core/models/chat.model';

@Injectable({ providedIn: 'root' })
export class ChatApiService {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly baseUrl = environment.apiBaseUrl;

  listChats(): Observable<ChatSummary[]> {
    return this.api.get<ChatSummary[]>('/chats/');
  }

  createChat(): Observable<ChatSummary> {
    return this.api.post<ChatSummary>('/chats/', {});
  }

  getChat(chatId: string): Observable<ChatDetail> {
    return this.api.get<ChatDetail>(`/chats/${chatId}`);
  }

  renameChat(chatId: string, title: string): Observable<{ id: string; title: string }> {
    return this.api.patch<{ id: string; title: string }>(`/chats/${chatId}`, { title });
  }

  deleteChat(chatId: string): Observable<void> {
    return this.api.delete<void>(`/chats/${chatId}`);
  }

  sendMessage(chatId: string, query: string): Observable<ChatStreamEvent> {
    return new Observable<ChatStreamEvent>((subscriber) => {
      const controller = new AbortController();
      let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;

      void (async () => {
        try {
          const token = await this.auth.getIdToken();

          const response = await fetch(`${this.baseUrl}/chats/${chatId}/messages`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(token ? { Authorization: `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ query }),
            signal: controller.signal
          });

          if (!response.ok || !response.body) {
            subscriber.error(new Error(`Request failed with status ${response.status}`));
            return;
          }

          reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          for (;;) {
            const { done, value } = await reader.read();
            if (done) {
              break;
            }

            buffer += decoder.decode(value, { stream: true });
            const chunks = buffer.split('\n\n');
            buffer = chunks.pop() ?? '';

            for (const chunk of chunks) {
              const dataLine = chunk.split('\n').find((line) => line.startsWith('data: '));
              if (!dataLine) {
                continue;
              }
              const event = JSON.parse(dataLine.slice('data: '.length)) as ChatStreamEvent;
              subscriber.next(event);
            }
          }

          subscriber.complete();
        } catch (err) {
          if ((err as { name?: string }).name !== 'AbortError') {
            subscriber.error(err);
          }
        }
      })();

      return () => {
        controller.abort();
        void reader?.cancel().catch(() => undefined);
      };
    });
  }
}
