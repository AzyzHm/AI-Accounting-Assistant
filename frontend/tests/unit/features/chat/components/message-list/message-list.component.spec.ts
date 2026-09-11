import { render, screen } from '@testing-library/angular';

import { MessageListComponent } from '@features/chat/components/message-list/message-list.component';
import { ChatMessage } from '@core/models/chat.model';

describe('MessageListComponent', () => {
  it('shows the empty-state invitation when there are no messages', async () => {
    await render(MessageListComponent, {
      componentInputs: { messages: [], pending: false }
    });

    expect(screen.getByText('Ask ComptaRAG')).toBeTruthy();
  });

  it('renders user and assistant entries without a category badge', async () => {
    const messages: ChatMessage[] = [
      { id: '1', role: 'user', content: 'What is IFRS 15?' },
      {
        id: '2',
        role: 'assistant',
        content: 'IFRS 15 governs revenue recognition.'
      }
    ];

    await render(MessageListComponent, {
      componentInputs: { messages, pending: false }
    });

    expect(screen.getByText('What is IFRS 15?')).toBeTruthy();
    expect(screen.getByText('IFRS 15 governs revenue recognition.')).toBeTruthy();
    expect(screen.queryByText('IFRS')).toBeNull();
    expect(screen.queryByText('Ask ComptaRAG')).toBeNull();
  });

  it('shows a generic thinking indicator while waiting with no progress label yet', async () => {
    await render(MessageListComponent, {
      componentInputs: { messages: [], pending: true, progressLabel: null }
    });

    expect(screen.getByText(/thinking/i)).toBeTruthy();
  });

  it('shows the live progress label while the agent is working', async () => {
    await render(MessageListComponent, {
      componentInputs: { messages: [], pending: true, progressLabel: 'Searching sources' }
    });

    expect(screen.getByText(/searching sources/i)).toBeTruthy();
  });

  it('updates the progress label as the agent moves through steps', async () => {
    const { rerender } = await render(MessageListComponent, {
      componentInputs: { messages: [], pending: true, progressLabel: 'Refining your query' }
    });

    expect(screen.getByText(/refining your query/i)).toBeTruthy();

    await rerender({
      componentInputs: { messages: [], pending: true, progressLabel: 'Writing answer' }
    });

    expect(screen.getByText(/writing answer/i)).toBeTruthy();
    expect(screen.queryByText(/refining your query/i)).toBeNull();
  });
});
