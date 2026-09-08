import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router';
import { of } from 'rxjs';
import { ReadableStream as NodeReadableStream } from 'node:stream/web';

import { ChatComponent } from '@features/chat/chat.component';

function sseStream(events: object[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new NodeReadableStream({
    pull(controller) {
      if (index < events.length) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(events[index])}\n\n`));
        index++;
      } else {
        controller.close();
      }
    }
  }) as unknown as ReadableStream<Uint8Array>;
}

describe('Chat feature (integration)', () => {
  it('starts a new chat, sends the first question, and streams the answer', async () => {
    const navigate = jest.fn().mockResolvedValue(true);
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: sseStream([
        { event: 'progress', node: 'router', label: 'Understanding your question' },
        { event: 'progress', node: 'generate', label: 'Writing answer' },
        {
          event: 'done',
          response: 'Les exportations de biens sont exonérées de TVA.',
          category: 'Fiscalité Tunisienne',
          chat_id: 'chat-1'
        }
      ])
    });
    (globalThis as unknown as { fetch: typeof fetch }).fetch = fetchMock as unknown as typeof fetch;

    await render(ChatComponent, {
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({})) } },
        { provide: Router, useValue: { navigate } }
      ]
    });

    const httpMock = TestBed.inject(HttpTestingController);

    httpMock.expectOne('http://localhost:8000/chats/').flush([]);

    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText('Ask a question'),
      'Comment la TVA est-elle traitée sur les exportations ?'
    );
    await user.click(screen.getByRole('button', { name: /^ask$/i }));

    expect(screen.getByText('Comment la TVA est-elle traitée sur les exportations ?')).toBeTruthy();

    const createRequest = httpMock.expectOne('http://localhost:8000/chats/');
    expect(createRequest.request.method).toBe('POST');
    createRequest.flush({ id: 'chat-1', owner_uid: 'u1', title: 'New chat' });

    expect(
      await screen.findByText('Les exportations de biens sont exonérées de TVA.')
    ).toBeTruthy();
    expect(navigate).toHaveBeenCalledWith(['/chat', 'chat-1'], { replaceUrl: true });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/chats/chat-1/messages',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          query: 'Comment la TVA est-elle traitée sur les exportations ?'
        })
      })
    );

    // Sending a message refreshes the sidebar's chat list.
    httpMock.expectOne('http://localhost:8000/chats/').flush([
      {
        id: 'chat-1',
        owner_uid: 'u1',
        title: 'Comment la TVA est-elle traitée sur les exportations ?'
      }
    ]);

    httpMock.verify();
  });
});
