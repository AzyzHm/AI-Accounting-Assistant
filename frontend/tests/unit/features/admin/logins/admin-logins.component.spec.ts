import { render, screen } from '@testing-library/angular';
import { of, throwError } from 'rxjs';

import { AdminLoginsComponent } from '@features/admin/logins/admin-logins.component';
import { AdminApiService } from '@core/services/admin-api.service';
import { LoginEvent } from '@core/models/admin-stats.model';

const events: LoginEvent[] = [
  {
    id: 'e1',
    uid: 'u1',
    email: 'them@example.com',
    display_name: 'Them',
    role: 'USER',
    ip: '203.0.113.5',
    user_agent: 'pytest-agent',
    created_at: '2026-01-01T10:00:00Z'
  }
];

function renderPage(overrides: Partial<{ listLoginEvents: jest.Mock }> = {}) {
  const listLoginEvents = overrides.listLoginEvents ?? jest.fn().mockReturnValue(of(events));

  return render(AdminLoginsComponent, {
    providers: [{ provide: AdminApiService, useValue: { listLoginEvents } }]
  }).then((result) => ({ result, listLoginEvents }));
}

describe('AdminLoginsComponent', () => {
  it('lists the login events the backend returned', async () => {
    await renderPage();

    expect(await screen.findByText('them@example.com')).toBeTruthy();
    expect(screen.getByText('203.0.113.5')).toBeTruthy();
  });

  it('shows a status message while there is no data yet', async () => {
    await renderPage({ listLoginEvents: jest.fn().mockReturnValue(of([])) });

    expect(await screen.findByText('No login activity to show yet.')).toBeTruthy();
  });

  it('shows an error message when loading fails', async () => {
    await renderPage({
      listLoginEvents: jest.fn().mockReturnValue(throwError(() => new Error('nope')))
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
  });
});
