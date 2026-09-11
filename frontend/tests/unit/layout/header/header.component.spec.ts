import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { provideRouter } from '@angular/router';

import { HeaderComponent } from '@app/layout/header/header.component';
import { AuthService } from '@core/services/auth.service';
import { UserProfile } from '@core/models/user.model';

const profile: UserProfile = {
  uid: 'u1',
  email: 'me@example.com',
  display_name: 'My Name',
  role: 'USER',
  approved: true
};

function renderHeader(overrides: Partial<Record<keyof AuthService, unknown>> = {}) {
  return render(HeaderComponent, {
    providers: [
      provideRouter([]),
      {
        provide: AuthService,
        useValue: {
          isAuthenticated: () => true,
          isInitializing: () => false,
          profile: () => profile,
          role: () => profile.role,
          logout: jest.fn().mockResolvedValue(undefined),
          ...overrides
        }
      }
    ]
  });
}

describe('HeaderComponent', () => {
  it('renders the ComptaRAG logo next to the title', async () => {
    const { container } = await renderHeader();

    const logo = container.querySelector('.app-header__logo') as HTMLImageElement;
    expect(logo.getAttribute('src')).toBe('/logo.png');
    expect(screen.getByText('ComptaRAG')).toBeTruthy();
  });

  it('shows the display name in place of the email once it is set', async () => {
    await renderHeader();

    expect(screen.getByText('My Name')).toBeTruthy();
    expect(screen.queryByText('me@example.com')).toBeNull();
  });

  it('falls back to the email when no display name is set', async () => {
    await renderHeader({ profile: () => ({ ...profile, display_name: null }) });

    expect(screen.getByText('me@example.com')).toBeTruthy();
  });

  it('opens the profile modal when the user name is clicked', async () => {
    await renderHeader();

    expect(screen.queryByRole('heading', { name: 'Your profile' })).toBeNull();

    await userEvent.setup().click(screen.getByText('My Name'));

    expect(await screen.findByRole('heading', { name: 'Your profile' })).toBeTruthy();
  });

  it('closes the profile modal when it emits closed', async () => {
    await renderHeader();

    await userEvent.setup().click(screen.getByText('My Name'));
    expect(await screen.findByRole('heading', { name: 'Your profile' })).toBeTruthy();

    await userEvent.setup().click(screen.getByRole('button', { name: /^close$/i }));

    expect(screen.queryByRole('heading', { name: 'Your profile' })).toBeNull();
  });

  it('does not render the profile modal for a signed-out visitor', async () => {
    await renderHeader({ isAuthenticated: () => false });

    expect(screen.queryByRole('heading', { name: 'Your profile' })).toBeNull();
    expect(screen.getByText('Sign in')).toBeTruthy();
  });

  it('renders the theme toggle regardless of auth state', async () => {
    await renderHeader({ isAuthenticated: () => false });

    expect(screen.getByRole('group', { name: 'Theme' })).toBeTruthy();
  });
});
