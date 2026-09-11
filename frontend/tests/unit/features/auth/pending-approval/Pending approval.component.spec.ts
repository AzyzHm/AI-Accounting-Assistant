import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { Router } from '@angular/router';

import { PendingApprovalComponent } from '@features/auth/pending-approval/pending-approval.component';
import { AuthService } from '@core/services/auth.service';

function renderPage(overrides: Partial<Record<string, unknown>> = {}) {
  const refreshProfile = jest.fn().mockResolvedValue(undefined);
  const logout = jest.fn().mockResolvedValue(undefined);
  const navigateByUrl = jest.fn().mockResolvedValue(true);
  const isApproved = jest.fn().mockReturnValue(false);

  return render(PendingApprovalComponent, {
    providers: [
      {
        provide: AuthService,
        useValue: {
          profile: () => ({ uid: 'u1', email: 'pending@example.com', role: 'USER' }),
          refreshProfile,
          isApproved,
          logout,
          ...overrides
        }
      },
      { provide: Router, useValue: { navigateByUrl } }
    ]
  }).then(() => ({ refreshProfile, logout, navigateByUrl, isApproved }));
}

describe('PendingApprovalComponent', () => {
  it('explains that the account is waiting on an admin, showing the signed-in email', async () => {
    await renderPage();

    expect(screen.getByText(/waiting on admin approval/i)).toBeTruthy();
    expect(screen.getByText('pending@example.com')).toBeTruthy();
  });

  it('re-checks status on demand and stays put when still pending', async () => {
    const { refreshProfile, navigateByUrl } = await renderPage();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /check again/i }));

    expect(refreshProfile).toHaveBeenCalled();
    expect(navigateByUrl).not.toHaveBeenCalled();
    expect(await screen.findByText(/still pending/i)).toBeTruthy();
  });

  it('navigates to /chat once refreshing shows the account was approved', async () => {
    const { navigateByUrl } = await renderPage({ isApproved: jest.fn().mockReturnValue(true) });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /check again/i }));

    expect(navigateByUrl).toHaveBeenCalledWith('/chat');
  });

  it('signs out and returns to /login', async () => {
    const { logout, navigateByUrl } = await renderPage();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /sign out/i }));

    expect(logout).toHaveBeenCalled();
    expect(navigateByUrl).toHaveBeenCalledWith('/login');
  });
});
