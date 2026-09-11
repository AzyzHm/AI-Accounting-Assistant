import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';

import { MessageComposerComponent } from '@features/chat/components/message-composer/message-composer.component';

describe('MessageComposerComponent', () => {
  it('emits the trimmed query and clears the draft on submit', async () => {
    const onSubmitted = jest.fn();

    await render(`<app-message-composer (submitted)="onSubmitted($event)" />`, {
      imports: [MessageComposerComponent],
      componentProperties: { onSubmitted }
    });

    const user = userEvent.setup();
    const textarea = screen.getByLabelText('Ask a question');

    await user.type(textarea, '  What is IFRS 15?  ');
    await user.click(screen.getByRole('button', { name: /ask/i }));

    expect(onSubmitted).toHaveBeenCalledWith('  What is IFRS 15?  ');
    expect(textarea).toHaveValue('');
  });

  it('does not submit an empty or whitespace-only draft', async () => {
    const onSubmitted = jest.fn();

    await render(`<app-message-composer (submitted)="onSubmitted($event)" />`, {
      imports: [MessageComposerComponent],
      componentProperties: { onSubmitted }
    });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Ask a question'), '   ');
    expect(screen.getByRole('button', { name: /ask/i })).toBeDisabled();

    expect(onSubmitted).not.toHaveBeenCalled();
  });

  it('does not submit while disabled', async () => {
    const onSubmitted = jest.fn();

    await render(`<app-message-composer [disabled]="true" (submitted)="onSubmitted($event)" />`, {
      imports: [MessageComposerComponent],
      componentProperties: { onSubmitted }
    });

    expect(screen.getByRole('button', { name: /asking/i })).toBeDisabled();
    expect(screen.getByLabelText('Ask a question')).toBeDisabled();
  });

  it('submits on Enter and inserts a newline on Shift+Enter', async () => {
    const onSubmitted = jest.fn();

    await render(`<app-message-composer (submitted)="onSubmitted($event)" />`, {
      imports: [MessageComposerComponent],
      componentProperties: { onSubmitted }
    });

    const user = userEvent.setup();
    const textarea = screen.getByLabelText('Ask a question');

    await user.type(textarea, 'line one{Shift>}{Enter}{/Shift}line two');
    expect(onSubmitted).not.toHaveBeenCalled();
    expect(textarea).toHaveValue('line one\nline two');

    await user.type(textarea, '{Enter}');
    expect(onSubmitted).toHaveBeenCalledWith('line one\nline two');
  });

  it('inserts a newline on Ctrl+Enter instead of submitting', async () => {
    const onSubmitted = jest.fn();

    await render(`<app-message-composer (submitted)="onSubmitted($event)" />`, {
      imports: [MessageComposerComponent],
      componentProperties: { onSubmitted }
    });

    const textarea = screen.getByLabelText('Ask a question');
    const event = new KeyboardEvent('keydown', {
      key: 'Enter',
      ctrlKey: true,
      bubbles: true,
      cancelable: true
    });
    textarea.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(false);
    expect(onSubmitted).not.toHaveBeenCalled();
  });
});
