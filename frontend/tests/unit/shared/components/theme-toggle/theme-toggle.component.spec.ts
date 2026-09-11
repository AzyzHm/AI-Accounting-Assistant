import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';

import { ThemeToggleComponent } from '@shared/components/theme-toggle/theme-toggle.component';
import { ThemeService } from '@core/services/theme.service';

async function renderToggle(preference: 'light' | 'dark' | 'system' = 'system') {
  const setPreference = jest.fn();

  const result = await render(ThemeToggleComponent, {
    providers: [
      {
        provide: ThemeService,
        useValue: { preference: () => preference, setPreference }
      }
    ]
  });

  return { ...result, setPreference };
}

describe('ThemeToggleComponent', () => {
  it('marks the active preference as pressed', async () => {
    await renderToggle('dark');

    expect(screen.getByRole('button', { name: 'Dark theme' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(screen.getByRole('button', { name: 'Light theme' })).toHaveAttribute(
      'aria-pressed',
      'false'
    );
  });

  it('calls setPreference with light when the light option is clicked', async () => {
    const { setPreference } = await renderToggle('system');

    await userEvent.setup().click(screen.getByRole('button', { name: 'Light theme' }));

    expect(setPreference).toHaveBeenCalledWith('light');
  });

  it('calls setPreference with dark when the dark option is clicked', async () => {
    const { setPreference } = await renderToggle('system');

    await userEvent.setup().click(screen.getByRole('button', { name: 'Dark theme' }));

    expect(setPreference).toHaveBeenCalledWith('dark');
  });

  it('calls setPreference with system when the system option is clicked', async () => {
    const { setPreference } = await renderToggle('dark');

    await userEvent.setup().click(screen.getByRole('button', { name: 'Match system theme' }));

    expect(setPreference).toHaveBeenCalledWith('system');
  });
});
