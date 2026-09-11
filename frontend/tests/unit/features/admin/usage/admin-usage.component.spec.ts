import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';

import { AdminUsageComponent } from '@features/admin/usage/admin-usage.component';
import { AdminApiService } from '@core/services/admin-api.service';
import { UsageTotal } from '@core/models/admin-stats.model';

const totals: UsageTotal[] = [
  {
    uid: 'u1',
    email: 'ali@example.com',
    display_name: 'Ali',
    role: 'USER',
    prompt_tokens: 10,
    completion_tokens: 5,
    total_tokens: 15,
    message_count: 1
  },
  {
    uid: 'u2',
    email: 'bea@example.com',
    display_name: 'Bea',
    role: 'USER',
    prompt_tokens: 100,
    completion_tokens: 50,
    total_tokens: 150,
    message_count: 10
  }
];

function renderPage(overrides: Partial<{ listUsageTotals: jest.Mock }> = {}) {
  const listUsageTotals = overrides.listUsageTotals ?? jest.fn().mockReturnValue(of(totals));

  return render(AdminUsageComponent, {
    providers: [{ provide: AdminApiService, useValue: { listUsageTotals } }]
  }).then((result) => ({ result, listUsageTotals }));
}

describe('AdminUsageComponent', () => {
  it('shows the total tokens used KPI summed across accounts', async () => {
    await renderPage();

    await screen.findByText('ali@example.com');
    const kpi = screen.getByText('Total tokens used').closest('.admin-kpi') as HTMLElement;
    expect(kpi.textContent).toContain('165');
  });

  it('lists accounts sorted by total tokens descending', async () => {
    await renderPage();

    const rows = await screen.findAllByRole('row');
    // rows[0] is the header row
    expect(rows[1]).toHaveTextContent('bea@example.com');
    expect(rows[2]).toHaveTextContent('ali@example.com');
  });

  it('filters the list by the search input', async () => {
    await renderPage();

    await screen.findByText('ali@example.com');
    const search = screen.getByRole('searchbox');

    await userEvent.setup().type(search, 'ali');

    expect(screen.getByText('ali@example.com')).toBeTruthy();
    expect(screen.queryByText('bea@example.com')).toBeNull();
  });

  it('shows an error message when loading fails', async () => {
    await renderPage({
      listUsageTotals: jest.fn().mockReturnValue(throwError(() => new Error('nope')))
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
  });
});
