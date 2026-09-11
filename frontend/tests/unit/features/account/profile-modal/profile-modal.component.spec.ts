import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';

import { ProfileModalComponent } from '@features/account/profile-modal/profile-modal.component';
import { AuthService } from '@core/services/auth.service';
import { UserProfile } from '@core/models/user.model';

const profile: UserProfile = {
  uid: 'u1',
  email: 'me@example.com',
  display_name: 'Old Name',
  role: 'USER',
  approved: true
};

function renderModal(overrides: Partial<Record<keyof AuthService, unknown>> = {}) {
  const updateDisplayName = jest.fn().mockResolvedValue(undefined);
  const updateEmail = jest.fn().mockResolvedValue(undefined);
  const updatePassword = jest.fn().mockResolvedValue(undefined);
  const onClosed = jest.fn();

  return render(`<app-profile-modal (closed)="onClosed()" />`, {
    imports: [ProfileModalComponent],
    componentProperties: { onClosed },
    providers: [
      {
        provide: AuthService,
        useValue: {
          profile: () => profile,
          updateDisplayName,
          updateEmail,
          updatePassword,
          ...overrides
        }
      }
    ]
  }).then((result) => ({ result, updateDisplayName, updateEmail, updatePassword, onClosed }));
}

describe('ProfileModalComponent', () => {
  it('pre-fills the username and email from the current profile', async () => {
    await renderModal();

    expect(screen.getByLabelText('Username')).toHaveValue('Old Name');
    expect(screen.getByLabelText('Email')).toHaveValue('me@example.com');
  });

  it('updates only the display name when only the username changed', async () => {
    const { updateDisplayName, updateEmail, updatePassword } = await renderModal();

    const user = userEvent.setup();
    await user.clear(screen.getByLabelText('Username'));
    await user.type(screen.getByLabelText('Username'), 'New Name');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    expect(await screen.findByRole('status')).toHaveTextContent(/updated/i);
    expect(updateDisplayName).toHaveBeenCalledWith('New Name');
    expect(updateEmail).not.toHaveBeenCalled();
    expect(updatePassword).not.toHaveBeenCalled();
  });

  it('requires the current password to change the email', async () => {
    const { updateEmail } = await renderModal();

    const user = userEvent.setup();
    await user.clear(screen.getByLabelText('Email'));
    await user.type(screen.getByLabelText('Email'), 'new@example.com');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/current password/i);
    expect(updateEmail).not.toHaveBeenCalled();
  });

  it('changes the email once the current password is provided', async () => {
    const { updateEmail } = await renderModal();

    const user = userEvent.setup();
    await user.clear(screen.getByLabelText('Email'));
    await user.type(screen.getByLabelText('Email'), 'new@example.com');
    await user.type(screen.getByLabelText('Current password'), 'hunter22');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    expect(await screen.findByRole('status')).toHaveTextContent(/updated/i);
    expect(updateEmail).toHaveBeenCalledWith('new@example.com', 'hunter22');
  });

  it('rejects a new password that does not match its confirmation', async () => {
    const { updatePassword } = await renderModal();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('New password'), 'secret-one');
    await user.type(screen.getByLabelText('Confirm new password'), 'secret-two');
    await user.type(screen.getByLabelText('Current password'), 'hunter22');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/do not match/i);
    expect(updatePassword).not.toHaveBeenCalled();
  });

  it('changes the password when it matches its confirmation', async () => {
    const { updatePassword } = await renderModal();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('New password'), 'secret-one');
    await user.type(screen.getByLabelText('Confirm new password'), 'secret-one');
    await user.type(screen.getByLabelText('Current password'), 'hunter22');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    expect(await screen.findByRole('status')).toHaveTextContent(/updated/i);
    expect(updatePassword).toHaveBeenCalledWith('secret-one', 'hunter22');
  });

  it('toggles the password fields between hidden and visible text', async () => {
    await renderModal();

    const newPasswordInput = screen.getByLabelText('New password') as HTMLInputElement;
    expect(newPasswordInput.type).toBe('password');

    await userEvent.setup().click(screen.getByRole('button', { name: /show passwords/i }));

    expect(newPasswordInput.type).toBe('text');
  });

  it('closes when the modal close button is clicked', async () => {
    const { onClosed } = await renderModal();

    await userEvent.setup().click(screen.getByRole('button', { name: /^close$/i }));

    expect(onClosed).toHaveBeenCalled();
  });
});
