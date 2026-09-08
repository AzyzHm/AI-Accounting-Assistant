import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize, firstValueFrom } from 'rxjs';

import { ChatApiService } from '@core/services/chat-api.service';
import { ChatMessage, ChatSummary } from '@core/models/chat.model';
import { ChatSidebarComponent } from './components/chat-sidebar/chat-sidebar.component';
import { MessageListComponent } from './components/message-list/message-list.component';
import { MessageComposerComponent } from './components/message-composer/message-composer.component';

let localMessageCounter = 0;

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [ChatSidebarComponent, MessageListComponent, MessageComposerComponent],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ChatComponent {
  private readonly chatApi = inject(ChatApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  private lastLoadedChatId: string | null = null;

  protected readonly chats = signal<ChatSummary[]>([]);
  protected readonly chatsLoading = signal(true);
  protected readonly sidebarCollapsed = signal(false);
  protected readonly mobileSidebarOpen = signal(false);

  protected readonly activeChatId = signal<string | null>(null);
  protected readonly messages = signal<ChatMessage[]>([]);
  protected readonly conversationLoading = signal(false);

  protected readonly pending = signal(false);
  protected readonly progressLabel = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);

  constructor() {
    this.loadChats();

    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const chatId = params.get('chatId');
      this.activeChatId.set(chatId);
      this.error.set(null);

      if (!chatId) {
        this.messages.set([]);
        this.lastLoadedChatId = null;
        return;
      }

      if (chatId !== this.lastLoadedChatId) {
        this.loadConversation(chatId);
      }
    });
  }

  protected startNewChat(): void {
    this.mobileSidebarOpen.set(false);
    void this.router.navigate(['/chat']);
  }

  protected openChat(chatId: string): void {
    this.mobileSidebarOpen.set(false);
    void this.router.navigate(['/chat', chatId]);
  }

  protected toggleSidebar(): void {
    this.sidebarCollapsed.update((collapsed) => !collapsed);
  }

  protected toggleMobileSidebar(): void {
    this.mobileSidebarOpen.update((open) => !open);
  }

  protected closeMobileSidebar(): void {
    this.mobileSidebarOpen.set(false);
  }

  protected async renameChat(event: { id: string; title: string }): Promise<void> {
    try {
      await firstValueFrom(this.chatApi.renameChat(event.id, event.title));
      this.chats.update((list) =>
        list.map((chat) => (chat.id === event.id ? { ...chat, title: event.title } : chat))
      );
    } catch {
      this.error.set('Could not rename that chat, please try again.');
    }
  }

  protected async deleteChat(chatId: string): Promise<void> {
    try {
      await firstValueFrom(this.chatApi.deleteChat(chatId));
      this.chats.update((list) => list.filter((chat) => chat.id !== chatId));
      if (this.activeChatId() === chatId) {
        void this.router.navigate(['/chat']);
      }
    } catch {
      this.error.set('Could not delete that chat, please try again.');
    }
  }

  protected async submitQuery(query: string): Promise<void> {
    const trimmed = query.trim();
    if (!trimmed || this.pending()) {
      return;
    }

    this.error.set(null);
    this.pending.set(true);
    this.progressLabel.set(null);
    this.appendLocalMessage({ role: 'user', content: trimmed });

    try {
      let chatId = this.activeChatId();

      if (!chatId) {
        const chat = await firstValueFrom(this.chatApi.createChat());
        chatId = chat.id;
        this.activeChatId.set(chatId);
        this.lastLoadedChatId = chatId;
        this.chats.update((list) => [chat, ...list]);
        await this.router.navigate(['/chat', chatId], { replaceUrl: true });
      }

      await this.streamAnswer(chatId, trimmed);
    } catch {
      this.error.set('Something went wrong reaching ComptaRAG, please try asking again.');
      this.pending.set(false);
      this.progressLabel.set(null);
    }
  }

  private streamAnswer(chatId: string, query: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.chatApi
        .sendMessage(chatId, query)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (streamEvent) => {
            if (streamEvent.event === 'progress') {
              this.progressLabel.set(streamEvent.label);
            } else if (streamEvent.event === 'done') {
              this.appendLocalMessage({ role: 'assistant', content: streamEvent.response });
              this.loadChats();
            } else if (streamEvent.event === 'error') {
              this.error.set('Something went wrong reaching ComptaRAG, please try asking again.');
            }
          },
          error: (err) => reject(err),
          complete: () => {
            this.pending.set(false);
            this.progressLabel.set(null);
            resolve();
          }
        });
    });
  }

  private loadChats(): void {
    this.chatApi
      .listChats()
      .pipe(finalize(() => this.chatsLoading.set(false)))
      .subscribe({
        next: (chats) => this.chats.set(chats),
        error: () => this.error.set('Could not load your chat history.')
      });
  }

  private loadConversation(chatId: string): void {
    this.conversationLoading.set(true);
    this.messages.set([]);

    this.chatApi
      .getChat(chatId)
      .pipe(finalize(() => this.conversationLoading.set(false)))
      .subscribe({
        next: (chat) => {
          this.messages.set(chat.messages);
          this.lastLoadedChatId = chatId;
        },
        error: () => {
          this.error.set('That chat could not be found.');
          void this.router.navigate(['/chat']);
        }
      });
  }

  private appendLocalMessage(
    message: Pick<ChatMessage, 'role' | 'content'> & Partial<ChatMessage>
  ): void {
    this.messages.update((current) => [
      ...current,
      { id: `local-${++localMessageCounter}`, ...message } as ChatMessage
    ]);
  }
}
