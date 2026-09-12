import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';

import { AdminUsageComponent } from '@features/admin/usage/admin-usage.component';
import { AdminApiService } from '@core/services/admin-api.service';
import { UsageTotal, UserLimitsDetail } from '@core/models/admin-stats.model';

const totals: UsageTotal[] = [
  {
    uid: 'u1',
    email: 'ali@example.com',
    display_name: 'Ali',
    role: 'USER',
    prompt_tokens: 10,
    completion_tokens: 5,
    total_tokens: 15,
    message_count: 1,
    search_credits_used: 2
  },
  {
    uid: 'u2',
    email: 'bea@example.com',
    display_name: 'Bea',
    role: 'USER',
    prompt_tokens: 100,
    completion_tokens: 50,
    total_tokens: 150,
    message_count: 10,
    search_credits_used: 7
  }
];

const limitsDetail: UserLimitsDetail = {
  limits: {
    daily_token_limit: 100_000,
    daily_search_limit: 30,
    monthly_token_limit: 2_000_000,
    monthly_search_limit: 600
  },
  usage: { daily_tokens: 20, daily_searches: 1, monthly_tokens: 20, monthly_searches: 1 },
  daily_reset_at: '2026-09-12',
  monthly_reset_at: '2026-10-01'
};

function renderPage(
  overrides: Partial<{
    listUsageTotals: jest.Mock;
    getUserLimits: jest.Mock;
    updateUserLimits: jest.Mock;
  }> = {}
) {
  const listUsageTotals = overrides.listUsageTotals ?? jest.fn().mockReturnValue(of(totals));
  const getUserLimits = overrides.getUserLimits ?? jest.fn().mockReturnValue(of(limitsDetail));
  const updateUserLimits =
    overrides.updateUserLimits ?? jest.fn().mockReturnValue(of(limitsDetail));

  return render(AdminUsageComponent, {
    providers: [
      { provide: AdminApiService, useValue: { listUsageTotals, getUserLimits, updateUserLimits } }
    ]
  }).then((result) => ({ result, listUsageTotals, getUserLimits, updateUserLimits }));
}

describe('AdminUsageComponent', () => {
  it('shows the total tokens used KPI summed across accounts', async () => {
    await renderPage();

    await screen.findByText('ali@example.com');
    const kpi = screen.getByText('Total tokens used').closest('.admin-kpi') as HTMLElement;
    expect(kpi.textContent).toContain('165');
  });

  it('shows the total search credits used KPI summed across accounts', async () => {
    await renderPage();

    await screen.findByText('ali@example.com');
    const kpi = screen.getByText('Total search credits used').closest('.admin-kpi') as HTMLElement;
    expect(kpi.textContent).toContain('9');
  });

  it('lists accounts sorted by total tokens descending', async () => {
    await renderPage();

    const rows = await screen.findAllByRole('row');
    // rows[0] is the header row
    expect(rows[1]).toHaveTextContent('bea@example.com');
    expect(rows[2]).toHaveTextContent('ali@example.com');
  });

  it("shows each account's search credits used", async () => {
    await renderPage();

    const rows = await screen.findAllByRole('row');
    expect(rows[1]).toHaveTextContent('7');
    expect(rows[2]).toHaveTextContent('2');
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

  it('opens the limits modal with the loaded limits and usage for the clicked account', async () => {
    const { getUserLimits } = await renderPage();

    await screen.findByText('ali@example.com');
    await userEvent.setup().click(screen.getAllByText('Edit limits')[1]);

    expect(getUserLimits).toHaveBeenCalledWith('u1');
    expect(await screen.findByLabelText('Daily token limit')).toHaveValue(100_000);
  });

  it('saves edited limits and shows a confirmation', async () => {
    const { updateUserLimits } = await renderPage();

    await screen.findByText('ali@example.com');
    await userEvent.setup().click(screen.getAllByText('Edit limits')[1]);

    const dailyTokenInput = await screen.findByLabelText('Daily token limit');
    await userEvent.setup().clear(dailyTokenInput);
    await userEvent.setup().type(dailyTokenInput, '5000');
    await userEvent.setup().click(screen.getByText('Save limits'));

    expect(updateUserLimits).toHaveBeenCalledWith(
      'u1',
      expect.objectContaining({ daily_token_limit: 5000 })
    );
    expect(await screen.findByText('Limits updated.')).toBeTruthy();
  });

  it('closes the limits modal', async () => {
    await renderPage();

    await screen.findByText('ali@example.com');
    await userEvent.setup().click(screen.getAllByText('Edit limits')[1]);
    await screen.findByLabelText('Daily token limit');

    await userEvent.setup().click(screen.getByLabelText('Close'));

    expect(screen.queryByLabelText('Daily token limit')).toBeNull();
  });

  it('shows "Unlimited" instead of an edit action for ADMIN and SUPER_ADMIN accounts', async () => {
    const mixedRoleTotals: UsageTotal[] = [
      ...totals,
      {
        uid: 'a1',
        email: 'admin@example.com',
        display_name: 'Admin',
        role: 'ADMIN',
        prompt_tokens: 1,
        completion_tokens: 1,
        total_tokens: 2,
        message_count: 1,
        search_credits_used: 0
      }
    ];

    await renderPage({ listUsageTotals: jest.fn().mockReturnValue(of(mixedRoleTotals)) });

    await screen.findByText('admin@example.com');
    const adminRow = screen.getByText('admin@example.com').closest('tr') as HTMLElement;

    expect(adminRow).toHaveTextContent('Unlimited');
    expect(
      Array.from(adminRow.querySelectorAll('button')).some(
        (button) => button.textContent?.trim() === 'Edit limits'
      )
    ).toBe(false);
  });
});
