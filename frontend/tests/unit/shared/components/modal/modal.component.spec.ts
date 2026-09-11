import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';

import { ModalComponent } from '@shared/components/modal/modal.component';

describe('ModalComponent', () => {
  it('renders the given title and projected content', async () => {
    await render(`<app-modal title="Your profile"><p>Body content</p></app-modal>`, {
      imports: [ModalComponent]
    });

    expect(screen.getByRole('heading', { name: 'Your profile' })).toBeTruthy();
    expect(screen.getByText('Body content')).toBeTruthy();
  });

  it('emits closed when the close button is clicked', async () => {
    const onClosed = jest.fn();

    await render(`<app-modal title="Your profile" (closed)="onClosed()" />`, {
      imports: [ModalComponent],
      componentProperties: { onClosed }
    });

    await userEvent.setup().click(screen.getByRole('button', { name: /close/i }));

    expect(onClosed).toHaveBeenCalled();
  });

  it('emits closed when the backdrop is clicked', async () => {
    const onClosed = jest.fn();

    const { container } = await render(`<app-modal title="Your profile" (closed)="onClosed()" />`, {
      imports: [ModalComponent],
      componentProperties: { onClosed }
    });

    const backdrop = container.querySelector('.modal-backdrop') as HTMLElement;
    await userEvent.setup().click(backdrop);

    expect(onClosed).toHaveBeenCalled();
  });

  it('does not close when the panel itself is clicked', async () => {
    const onClosed = jest.fn();

    await render(`<app-modal title="Your profile"><p>Body content</p></app-modal>`, {
      imports: [ModalComponent],
      componentProperties: { onClosed }
    });

    await userEvent.setup().click(screen.getByText('Body content'));

    expect(onClosed).not.toHaveBeenCalled();
  });

  it('emits closed on Escape', async () => {
    const onClosed = jest.fn();

    await render(`<app-modal title="Your profile" (closed)="onClosed()" />`, {
      imports: [ModalComponent],
      componentProperties: { onClosed }
    });

    await userEvent.setup().keyboard('{Escape}');

    expect(onClosed).toHaveBeenCalled();
  });
});
