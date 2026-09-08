import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router';
import { BehaviorSubject, of, throwError } from 'rxjs';

import { ChatComponent } from '@features/chat/chat.component';
import { ChatApiService } from '@core/services/chat-api.service';
import { ChatStreamEvent, ChatSummary } from '@core/models/chat.model';

function activatedRouteStub(initialChatId: string | null = null) {
  const paramMap = new BehaviorSubject(
    convertToParamMap(initialChatId ? { chatId: initialChatId } : {})
  );
  return { route: { paramMap: paramMap.asObservable() }, paramMap };
}

function makeChatApi(overrides: Partial<Record<keyof ChatApiService, jest.Mock>> = {}) {
  return {
    listChats: jest.fn().mockReturnValue(of([])),
    createChat: jest.fn(),
    getChat: jest.fn(),
    renameChat: jest.fn(),
    deleteChat: jest.fn(),
    sendMessage: jest.fn(),
    ...overrides
  };
}

function answeredWith(response: string, chatId: string) {
  const events: ChatStreamEvent[] = [
    { event: 'progress', node: 'router', label: 'Understanding your question' },
    { event: 'progress', node: 'generate', label: 'Writing answer' },
    { event: 'done', response, category: 'ifrs', chat_id: chatId }
  ];
  return of(...events);
}

describe('ChatComponent', () => {
  it('shows the empty-state invitation with no active chat', async () => {
    const { route } = activatedRouteStub();
    const chatApi = makeChatApi();

    await render(ChatComponent, {
      providers: [
        { provide: ChatApiService, useValue: chatApi },
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate: jest.fn() } }
      ]
    });

    expect(await screen.findByText('Ask ComptaRAG')).toBeTruthy();
  });

  it('loads and displays the chat history sidebar', async () => {
    const { route } = activatedRouteStub();
    const chats: ChatSummary[] = [
      { id: 'c1', owner_uid: 'u1', title: 'IFRS 16 questions' },
      { id: 'c2', owner_uid: 'u1', title: 'VAT rate' }
    ];
    const chatApi = makeChatApi({ listChats: jest.fn().mockReturnValue(of(chats)) });

    await render(ChatComponent, {
      providers: [
        { provide: ChatApiService, useValue: chatApi },
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate: jest.fn() } }
      ]
    });

    expect(await screen.findByText('IFRS 16 questions')).toBeTruthy();
    expect(screen.getByText('VAT rate')).toBeTruthy();
  });

  it('loads an existing chat s messages from the route param', async () => {
    const { route } = activatedRouteStub('c1');
    const chatApi = makeChatApi({
      getChat: jest.fn().mockReturnValue(
        of({
          id: 'c1',
          owner_uid: 'u1',
          title: 'IFRS 16',
          messages: [
            { id: 'm1', role: 'user', content: 'What is IFRS 16?' },
            { id: 'm2', role: 'assistant', content: 'It is the leases standard.' }
          ]
        })
      )
    });

    await render(ChatComponent, {
      providers: [
        { provide: ChatApiService, useValue: chatApi },
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate: jest.fn() } }
      ]
    });

    expect(await screen.findByText('What is IFRS 16?')).toBeTruthy();
    expect(screen.getByText('It is the leases standard.')).toBeTruthy();
    expect(chatApi.getChat).toHaveBeenCalledWith('c1');
  });

  it('creates a new chat and sends the first message when none is active', async () => {
    const { route } = activatedRouteStub();
    const navigate = jest.fn().mockResolvedValue(true);
    const chatApi = makeChatApi({
      createChat: jest
        .fn()
        .mockReturnValue(of({ id: 'new-1', owner_uid: 'u1', title: 'New chat' })),
      sendMessage: jest.fn().mockReturnValue(answeredWith('Here you go.', 'new-1'))
    });

    await render(ChatComponent, {
      providers: [
        { provide: ChatApiService, useValue: chatApi },
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate } }
      ]
    });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Ask a question'), 'What is a provision?');
    await user.click(screen.getByRole('button', { name: /^ask$/i }));

    expect(screen.getByText('What is a provision?')).toBeTruthy();
    expect(await screen.findByText('Here you go.')).toBeTruthy();
    expect(chatApi.createChat).toHaveBeenCalled();
    expect(chatApi.sendMessage).toHaveBeenCalledWith('new-1', 'What is a provision?');
    expect(navigate).toHaveBeenCalledWith(['/chat', 'new-1'], { replaceUrl: true });
  });

  it('sends follow-up messages directly to the active chat', async () => {
    const { route } = activatedRouteStub('c1');
    const chatApi = makeChatApi({
      getChat: jest
        .fn()
        .mockReturnValue(of({ id: 'c1', owner_uid: 'u1', title: 'Ongoing', messages: [] })),
      sendMessage: jest.fn().mockReturnValue(answeredWith('Sure.', 'c1'))
    });

    await render(ChatComponent, {
      providers: [
        { provide: ChatApiService, useValue: chatApi },
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate: jest.fn() } }
      ]
    });

    await waitFor(() => expect(chatApi.getChat).toHaveBeenCalled());

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Ask a question'), 'Follow-up question');
    await user.click(screen.getByRole('button', { name: /^ask$/i }));

    expect(await screen.findByText('Sure.')).toBeTruthy();
    expect(chatApi.createChat).not.toHaveBeenCalled();
    expect(chatApi.sendMessage).toHaveBeenCalledWith('c1', 'Follow-up question');
  });

  it('shows the live progress label while the agent is working', async () => {
    const { route } = activatedRouteStub('c1');
    const events: ChatStreamEvent[] = [
      { event: 'progress', node: 'refine', label: 'Refining your query' },
      { event: 'progress', node: 'retrieve', label: 'Searching sources' },
      { event: 'done', response: 'Sure.', category: 'ifrs', chat_id: 'c1' }
    ];
    const chatApi = makeChatApi({
      getChat: jest
        .fn()
        .mockReturnValue(of({ id: 'c1', owner_uid: 'u1', title: 'Ongoing', messages: [] })),
      sendMessage: jest.fn().mockReturnValue(of(...events))
    });

    await render(ChatComponent, {
      providers: [
        { provide: ChatApiService, useValue: chatApi },
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate: jest.fn() } }
      ]
    });

    await waitFor(() => expect(chatApi.getChat).toHaveBeenCalled());

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Ask a question'), 'q');
    await user.click(screen.getByRole('button', { name: /^ask$/i }));

    expect(await screen.findByText('Sure.')).toBeTruthy();
  });

  it('shows an error message when the stream reports an error event', async () => {
    const { route } = activatedRouteStub('c1');
    const chatApi = makeChatApi({
      getChat: jest
        .fn()
        .mockReturnValue(of({ id: 'c1', owner_uid: 'u1', title: 'x', messages: [] })),
      sendMessage: jest
        .fn()
        .mockReturnValue(of<ChatStreamEvent>({ event: 'error', detail: 'LLM unavailable' }))
    });

    await render(ChatComponent, {
      providers: [
        { provide: ChatApiService, useValue: chatApi },
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate: jest.fn() } }
      ]
    });

    await waitFor(() => expect(chatApi.getChat).toHaveBeenCalled());

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Ask a question'), 'q');
    await user.click(screen.getByRole('button', { name: /^ask$/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i);
  });

  it('shows an error message when the request itself fails', async () => {
    const { route } = activatedRouteStub('c1');
    const chatApi = makeChatApi({
      getChat: jest
        .fn()
        .mockReturnValue(of({ id: 'c1', owner_uid: 'u1', title: 'x', messages: [] })),
      sendMessage: jest.fn().mockReturnValue(throwError(() => new Error('network down')))
    });

    await render(ChatComponent, {
      providers: [
        { provide: ChatApiService, useValue: chatApi },
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate: jest.fn() } }
      ]
    });

    await waitFor(() => expect(chatApi.getChat).toHaveBeenCalled());

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Ask a question'), 'q');
    await user.click(screen.getByRole('button', { name: /^ask$/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i);
  });

  it('navigates to /chat when starting a new chat', async () => {
    const { route } = activatedRouteStub('c1');
    const navigate = jest.fn().mockResolvedValue(true);
    const chatApi = makeChatApi({
      getChat: jest
        .fn()
        .mockReturnValue(of({ id: 'c1', owner_uid: 'u1', title: 'x', messages: [] }))
    });

    await render(ChatComponent, {
      providers: [
        { provide: ChatApiService, useValue: chatApi },
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate } }
      ]
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /new chat/i }));

    expect(navigate).toHaveBeenCalledWith(['/chat']);
  });

  it('opens the mobile sidebar drawer when the hamburger toggle is clicked', async () => {
    const { route } = activatedRouteStub();
    const chatApi = makeChatApi();

    await render(ChatComponent, {
      providers: [
        { provide: ChatApiService, useValue: chatApi },
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate: jest.fn() } }
      ]
    });

    expect(screen.queryByRole('button', { name: /close chat list/i })).toBeNull();

    await userEvent.setup().click(screen.getByRole('button', { name: /open chat list/i }));

    expect(screen.getByRole('button', { name: /close chat list/i })).toBeTruthy();
  });

  it('closes the mobile sidebar drawer after selecting a chat', async () => {
    const { route } = activatedRouteStub();
    const chats: ChatSummary[] = [{ id: 'c1', owner_uid: 'u1', title: 'IFRS 16 questions' }];
    const navigate = jest.fn().mockResolvedValue(true);
    const chatApi = makeChatApi({ listChats: jest.fn().mockReturnValue(of(chats)) });

    await render(ChatComponent, {
      providers: [
        { provide: ChatApiService, useValue: chatApi },
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate } }
      ]
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /open chat list/i }));
    expect(screen.getByRole('button', { name: /close chat list/i })).toBeTruthy();

    await user.click(await screen.findByText('IFRS 16 questions'));

    expect(navigate).toHaveBeenCalledWith(['/chat', 'c1']);
    expect(screen.queryByRole('button', { name: /close chat list/i })).toBeNull();
  });

  it('closes the mobile sidebar drawer when the backdrop is dismissed', async () => {
    const { route } = activatedRouteStub();
    const chatApi = makeChatApi();

    await render(ChatComponent, {
      providers: [
        { provide: ChatApiService, useValue: chatApi },
        { provide: ActivatedRoute, useValue: route },
        { provide: Router, useValue: { navigate: jest.fn() } }
      ]
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /open chat list/i }));
    await user.click(screen.getByRole('button', { name: /close chat list/i }));

    expect(screen.queryByRole('button', { name: /close chat list/i })).toBeNull();
  });
});
