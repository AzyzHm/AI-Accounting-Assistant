import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { RouterTestingHarness } from '@angular/router/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { ChatComponent } from '@features/chat/chat.component';
import { CHAT_ROUTES } from '@features/chat/chat.routes';
import { ChatApiService } from '@core/services/chat-api.service';
import { AuthService } from '@core/services/auth.service';

@Component({ selector: 'app-empty', template: '', standalone: true })
class EmptyComponent {}

describe('CHAT_ROUTES', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([
          { path: '', component: EmptyComponent },
          { path: 'chat', children: CHAT_ROUTES }
        ]),
        {
          provide: ChatApiService,
          useValue: {
            listChats: jest.fn().mockReturnValue(of([])),
            createChat: jest.fn(),
            getChat: jest.fn(),
            renameChat: jest.fn(),
            deleteChat: jest.fn(),
            sendMessage: jest.fn()
          }
        },
        {
          provide: AuthService,
          useValue: {
            ready: Promise.resolve(),
            isAuthenticated: () => true,
            isApproved: () => true
          }
        }
      ]
    });
  });

  it('reuses the same ChatComponent instance when navigating from /chat to /chat/:chatId', async () => {
    const harness = await RouterTestingHarness.create('/chat');
    const first = harness.routeDebugElement?.componentInstance;

    await harness.navigateByUrl('/chat/abc123');
    const second = harness.routeDebugElement?.componentInstance;

    expect(first).toBeInstanceOf(ChatComponent);
    expect(second).toBe(first);
  });

  it('reuses the same ChatComponent instance when navigating from /chat/:chatId back to /chat', async () => {
    const harness = await RouterTestingHarness.create('/chat/abc123');
    const first = harness.routeDebugElement?.componentInstance;

    await harness.navigateByUrl('/chat');
    const second = harness.routeDebugElement?.componentInstance;

    expect(first).toBeInstanceOf(ChatComponent);
    expect(second).toBe(first);
  });
});
