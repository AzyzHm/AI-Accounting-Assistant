import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { Router } from '@angular/router';

import { HomeComponent } from '@features/home/home.component';

describe('HomeComponent', () => {
  it('renders the hero and the highlight cards', async () => {
    await render(HomeComponent, {
      providers: [{ provide: Router, useValue: { navigate: jest.fn(), navigateByUrl: jest.fn() } }]
    });

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/ask comptarag anything/i);
    expect(screen.getByText('IFRS, grounded')).toBeTruthy();
    expect(screen.getByText('Tunisian fiscal law')).toBeTruthy();
    expect(screen.getByText('French or English')).toBeTruthy();
  });

  it('sends "Get started" to /login with the register query param', async () => {
    const navigate = jest.fn();

    await render(HomeComponent, {
      providers: [{ provide: Router, useValue: { navigate, navigateByUrl: jest.fn() } }]
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /get started/i }));

    expect(navigate).toHaveBeenCalledWith(['/login'], { queryParams: { mode: 'register' } });
  });

  it('sends "Sign in" straight to /login', async () => {
    const navigateByUrl = jest.fn();

    await render(HomeComponent, {
      providers: [{ provide: Router, useValue: { navigate: jest.fn(), navigateByUrl } }]
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /^sign in$/i }));

    expect(navigateByUrl).toHaveBeenCalledWith('/login');
  });
});
