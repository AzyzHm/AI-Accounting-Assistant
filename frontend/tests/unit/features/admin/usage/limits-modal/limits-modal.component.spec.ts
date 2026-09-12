import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';

import { AdminUsageLimitsModalComponent } from '@features/admin/usage/limits-modal/limits-modal.component';
import { AdminApiService } from '@core/services/admin-api.service';
import { UserLimitsDetail } from '@core/models/admin-stats.model';

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

function renderModal(
  overrides: Partial<{ getUserLimits: jest.Mock; updateUserLimits: jest.Mock }> = {}
) {
  const getUserLimits = overrides.getUserLimits ?? jest.fn().mockReturnValue(of(limitsDetail));
  const updateUserLimits =
    overrides.updateUserLimits ?? jest.fn().mockReturnValue(of(limitsDetail));
  const onClosed = jest.fn();

  return render(
    `<app-admin-usage-limits-modal uid="u1" email="ali@example.com" (closed)="onClosed()" />`,
    {
      imports: [AdminUsageLimitsModalComponent],
      componentProperties: { onClosed },
      providers: [{ provide: AdminApiService, useValue: { getUserLimits, updateUserLimits } }]
    }
  ).then((result) => ({ result, getUserLimits, updateUserLimits, onClosed }));
}

describe('AdminUsageLimitsModalComponent', () => {
  it('shows the modal title with the account email', async () => {
    await renderModal();

    expect(await screen.findByText('Usage limits for ali@example.com')).toBeTruthy();
  });

  it('pre-fills all four fields from the loaded limits', async () => {
    await renderModal();

    expect(await screen.findByLabelText('Daily token limit')).toHaveValue(100_000);
    expect(screen.getByLabelText('Daily web search limit')).toHaveValue(30);
    expect(screen.getByLabelText('Monthly token limit')).toHaveValue(2_000_000);
    expect(screen.getByLabelText('Monthly web search limit')).toHaveValue(600);
  });

  it('shows the current usage and exact reset dates', async () => {
    await renderModal();

    await screen.findByLabelText('Daily token limit');
    expect(screen.getByText(/20 tokens used so far today/)).toBeTruthy();
    expect(screen.getByText(/1 web searches used so far today/)).toBeTruthy();
    expect(screen.getByText(/Resets on 2026-09-12/)).toBeTruthy();
    expect(screen.getByText(/Resets on 2026-10-01/)).toBeTruthy();
  });

  it('shows an error message when loading the limits fails', async () => {
    await renderModal({
      getUserLimits: jest.fn().mockReturnValue(throwError(() => new Error('nope')))
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
  });

  it('rejects a negative limit without calling the API', async () => {
    const { updateUserLimits } = await renderModal();

    const dailyTokenInput = await screen.findByLabelText('Daily token limit');
    await userEvent.setup().clear(dailyTokenInput);
    await userEvent.setup().type(dailyTokenInput, '-5');
    await userEvent.setup().click(screen.getByText('Save limits'));

    expect(updateUserLimits).not.toHaveBeenCalled();
    expect(await screen.findByRole('alert')).toHaveTextContent(/zero or a positive/i);
  });

  it('shows an error message when saving fails', async () => {
    await renderModal({
      updateUserLimits: jest.fn().mockReturnValue(throwError(() => new Error('nope')))
    });

    await screen.findByLabelText('Daily token limit');
    await userEvent.setup().click(screen.getByText('Save limits'));

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not save/i);
  });

  it('emits closed when the close button is clicked', async () => {
    const { onClosed } = await renderModal();

    await screen.findByLabelText('Daily token limit');
    await userEvent.setup().click(screen.getByLabelText('Close'));

    expect(onClosed).toHaveBeenCalled();
  });
});
