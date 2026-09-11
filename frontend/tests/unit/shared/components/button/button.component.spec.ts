import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';

import { ButtonComponent } from '@shared/components/button/button.component';

describe('ButtonComponent', () => {
  it('renders projected content', async () => {
    await render(`<app-button>Click me</app-button>`, {
      imports: [ButtonComponent]
    });

    expect(screen.getByText('Click me')).toBeTruthy();
  });

  it('emits clicked when pressed', async () => {
    const onClicked = jest.fn();

    await render(`<app-button (clicked)="onClicked($event)">Save</app-button>`, {
      imports: [ButtonComponent],
      componentProperties: { onClicked }
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(onClicked).toHaveBeenCalledTimes(1);
  });

  it('does not emit clicked when disabled', async () => {
    const onClicked = jest.fn();

    await render(
      `<app-button [disabled]="true" (clicked)="onClicked($event)">Disabled</app-button>`,
      {
        imports: [ButtonComponent],
        componentProperties: { onClicked }
      }
    );

    const button = screen.getByRole('button', { name: 'Disabled' });
    expect(button).toBeDisabled();

    const user = userEvent.setup();
    await user.click(button);

    expect(onClicked).not.toHaveBeenCalled();
  });
});
