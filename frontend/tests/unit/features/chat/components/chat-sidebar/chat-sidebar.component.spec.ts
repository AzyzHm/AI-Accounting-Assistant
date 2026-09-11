import { render, screen, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';

import { ChatSidebarComponent } from '@features/chat/components/chat-sidebar/chat-sidebar.component';
import { ChatSummary } from '@core/models/chat.model';

const chats: ChatSummary[] = [
  { id: 'c1', owner_uid: 'u1', title: 'IFRS 16 questions' },
  { id: 'c2', owner_uid: 'u1', title: 'VAT rate' }
];

describe('ChatSidebarComponent', () => {
  it('shows an empty message when there are no chats', async () => {
    await render(ChatSidebarComponent, {
      componentInputs: { chats: [], activeChatId: null, loading: false, collapsed: false }
    });

    expect(screen.getByText(/no chats yet/i)).toBeTruthy();
  });

  it('lists every chat title', async () => {
    await render(ChatSidebarComponent, {
      componentInputs: { chats, activeChatId: null, loading: false, collapsed: false }
    });

    expect(screen.getByText('IFRS 16 questions')).toBeTruthy();
    expect(screen.getByText('VAT rate')).toBeTruthy();
  });

  it('emits newChat when the new chat button is clicked', async () => {
    const onNewChat = jest.fn();

    await render(`<app-chat-sidebar [chats]="chats" (newChat)="onNewChat()" />`, {
      imports: [ChatSidebarComponent],
      componentProperties: { chats, onNewChat }
    });

    await userEvent.setup().click(screen.getByRole('button', { name: /new chat/i }));

    expect(onNewChat).toHaveBeenCalled();
  });

  it('emits selectChat with the chat s id when a row is clicked', async () => {
    const onSelectChat = jest.fn();

    await render(`<app-chat-sidebar [chats]="chats" (selectChat)="onSelectChat($event)" />`, {
      imports: [ChatSidebarComponent],
      componentProperties: { chats, onSelectChat }
    });

    await userEvent.setup().click(screen.getByText('IFRS 16 questions'));

    expect(onSelectChat).toHaveBeenCalledWith('c1');
  });

  it('emits renameChat with the edited title on Enter', async () => {
    const onRenameChat = jest.fn();

    await render(`<app-chat-sidebar [chats]="chats" (renameChat)="onRenameChat($event)" />`, {
      imports: [ChatSidebarComponent],
      componentProperties: { chats, onRenameChat }
    });

    const user = userEvent.setup();
    await user.click(screen.getAllByRole('button', { name: /rename chat/i, hidden: true })[0]);
    const input = screen.getByDisplayValue('IFRS 16 questions');
    await user.clear(input);
    await user.type(input, 'Leases{Enter}');

    expect(onRenameChat).toHaveBeenCalledWith({ id: 'c1', title: 'Leases' });
  });

  it('emits deleteChat when the user confirms the native prompt', async () => {
    const onDeleteChat = jest.fn();
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);

    await render(`<app-chat-sidebar [chats]="chats" (deleteChat)="onDeleteChat($event)" />`, {
      imports: [ChatSidebarComponent],
      componentProperties: { chats, onDeleteChat }
    });

    await userEvent
      .setup()
      .click(screen.getAllByRole('button', { name: /delete chat/i, hidden: true })[0]);

    expect(onDeleteChat).toHaveBeenCalledWith('c1');
    confirmSpy.mockRestore();
  });

  it('does not emit deleteChat when the user cancels the native prompt', async () => {
    const onDeleteChat = jest.fn();
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(false);

    await render(`<app-chat-sidebar [chats]="chats" (deleteChat)="onDeleteChat($event)" />`, {
      imports: [ChatSidebarComponent],
      componentProperties: { chats, onDeleteChat }
    });

    await userEvent
      .setup()
      .click(screen.getAllByRole('button', { name: /delete chat/i, hidden: true })[0]);

    expect(onDeleteChat).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('hides the chat list and title labels while collapsed', async () => {
    await render(ChatSidebarComponent, {
      componentInputs: { chats, activeChatId: null, loading: false, collapsed: true }
    });

    expect(screen.queryByText('IFRS 16 questions')).toBeNull();
    expect(screen.queryByText('New chat')).toBeNull();
  });

  it('emits toggleCollapsed when the collapse button is clicked', async () => {
    const onToggleCollapsed = jest.fn();

    await render(`<app-chat-sidebar [chats]="chats" (toggleCollapsed)="onToggleCollapsed()" />`, {
      imports: [ChatSidebarComponent],
      componentProperties: { chats, onToggleCollapsed }
    });

    await userEvent.setup().click(screen.getByRole('button', { name: /collapse sidebar/i }));

    expect(onToggleCollapsed).toHaveBeenCalled();
  });

  it('closes the mobile drawer, instead of emitting toggleCollapsed, when the same button is clicked while the drawer is open', async () => {
    const onToggleCollapsed = jest.fn();
    const onCloseMobile = jest.fn();

    await render(
      `<app-chat-sidebar [chats]="chats" [mobileOpen]="true" (toggleCollapsed)="onToggleCollapsed()" (closeMobile)="onCloseMobile()" />`,
      {
        imports: [ChatSidebarComponent],
        componentProperties: { chats, onToggleCollapsed, onCloseMobile }
      }
    );

    await userEvent.setup().click(screen.getByRole('button', { name: /close sidebar/i }));

    expect(onCloseMobile).toHaveBeenCalled();
    expect(onToggleCollapsed).not.toHaveBeenCalled();
  });

  it('emits selectChat when a row is activated with the keyboard', async () => {
    const onSelectChat = jest.fn();

    await render(`<app-chat-sidebar [chats]="chats" (selectChat)="onSelectChat($event)" />`, {
      imports: [ChatSidebarComponent],
      componentProperties: { chats, onSelectChat }
    });

    screen
      .getByText('IFRS 16 questions')
      .closest('[role="button"]')
      ?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));

    expect(onSelectChat).toHaveBeenCalledWith('c1');
  });

  it('does not render a backdrop when the mobile drawer is closed', async () => {
    await render(ChatSidebarComponent, {
      componentInputs: {
        chats,
        activeChatId: null,
        loading: false,
        collapsed: false,
        mobileOpen: false
      }
    });

    expect(screen.queryByRole('button', { name: /close chat list/i })).toBeNull();
  });

  it('emits closeMobile when the backdrop is clicked while the drawer is open', async () => {
    const onCloseMobile = jest.fn();

    await render(
      `<app-chat-sidebar [chats]="chats" [mobileOpen]="true" (closeMobile)="onCloseMobile()" />`,
      {
        imports: [ChatSidebarComponent],
        componentProperties: { chats, onCloseMobile }
      }
    );

    await userEvent.setup().click(screen.getByRole('button', { name: /close chat list/i }));

    expect(onCloseMobile).toHaveBeenCalled();
  });

  it('shows full content in the mobile drawer even if the desktop rail is collapsed', async () => {
    await render(ChatSidebarComponent, {
      componentInputs: {
        chats,
        activeChatId: null,
        loading: false,
        collapsed: true,
        mobileOpen: true
      }
    });

    expect(screen.getByText('IFRS 16 questions')).toBeTruthy();
    expect(screen.getByText('New chat')).toBeTruthy();
  });

  it('lets the rename input accept spaces without triggering row navigation', async () => {
    const onSelectChat = jest.fn();
    const onRenameChat = jest.fn();

    await render(
      `<app-chat-sidebar [chats]="chats" (selectChat)="onSelectChat($event)" (renameChat)="onRenameChat($event)" />`,
      {
        imports: [ChatSidebarComponent],
        componentProperties: { chats, onSelectChat, onRenameChat }
      }
    );

    const user = userEvent.setup();
    const row = screen.getByText('IFRS 16 questions').closest('[role="button"]') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: /rename chat/i }));

    const input = screen.getByRole('textbox') as HTMLInputElement;
    await user.clear(input);
    await user.type(input, 'Two words{Enter}');

    expect(onSelectChat).not.toHaveBeenCalled();
    expect(onRenameChat).toHaveBeenCalledWith({ id: 'c1', title: 'Two words' });
  });
});
