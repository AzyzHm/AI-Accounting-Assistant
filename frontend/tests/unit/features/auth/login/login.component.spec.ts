import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router';
import { of } from 'rxjs';

import { LoginComponent } from '@features/auth/login/login.component';
import { AuthService } from '@core/services/auth.service';

function activatedRouteStub(queryParams: Record<string, string> = {}) {
  return {
    queryParamMap: of(convertToParamMap(queryParams))
  };
}

describe('LoginComponent', () => {
  it('signs in with email and password, then navigates to /chat', async () => {
    const signInWithEmail = jest.fn().mockResolvedValue(undefined);
    const navigateByUrl = jest.fn().mockResolvedValue(true);

    await render(LoginComponent, {
      providers: [
        { provide: AuthService, useValue: { signInWithEmail, isApproved: () => true } },
        { provide: Router, useValue: { navigateByUrl } },
        { provide: ActivatedRoute, useValue: activatedRouteStub() }
      ]
    });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Email'), 'demo@example.com');
    await user.type(screen.getByLabelText('Password'), 'hunter22');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(signInWithEmail).toHaveBeenCalledWith('demo@example.com', 'hunter22');
    expect(navigateByUrl).toHaveBeenCalledWith('/chat');
  });

  it('switches to register mode and calls registerWithEmail on submit', async () => {
    const registerWithEmail = jest.fn().mockResolvedValue(undefined);
    const navigateByUrl = jest.fn().mockResolvedValue(true);

    await render(LoginComponent, {
      providers: [
        { provide: AuthService, useValue: { registerWithEmail, isApproved: () => true } },
        { provide: Router, useValue: { navigateByUrl } },
        { provide: ActivatedRoute, useValue: activatedRouteStub() }
      ]
    });

    const user = userEvent.setup();
    await user.click(screen.getByText(/create one/i));
    await user.type(screen.getByLabelText('Email'), 'new@example.com');
    await user.type(screen.getByLabelText('Password'), 'hunter22');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    expect(registerWithEmail).toHaveBeenCalledWith('new@example.com', 'hunter22');
    expect(navigateByUrl).toHaveBeenCalledWith('/chat');
  });

  it('sends a brand-new, unapproved sign-up to /pending-approval instead of /chat', async () => {
    const registerWithEmail = jest.fn().mockResolvedValue(undefined);
    const navigateByUrl = jest.fn().mockResolvedValue(true);

    await render(LoginComponent, {
      providers: [
        { provide: AuthService, useValue: { registerWithEmail, isApproved: () => false } },
        { provide: Router, useValue: { navigateByUrl } },
        { provide: ActivatedRoute, useValue: activatedRouteStub() }
      ]
    });

    const user = userEvent.setup();
    await user.click(screen.getByText(/create one/i));
    await user.type(screen.getByLabelText('Email'), 'new@example.com');
    await user.type(screen.getByLabelText('Password'), 'hunter22');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    expect(navigateByUrl).toHaveBeenCalledWith('/pending-approval');
  });

  it('opens directly in register mode when the mode=register query param is set', async () => {
    await render(LoginComponent, {
      providers: [
        {
          provide: AuthService,
          useValue: { registerWithEmail: jest.fn(), isApproved: () => true }
        },
        { provide: Router, useValue: { navigateByUrl: jest.fn() } },
        { provide: ActivatedRoute, useValue: activatedRouteStub({ mode: 'register' }) }
      ]
    });

    expect(screen.getByRole('heading', { name: /create your comptarag account/i })).toBeTruthy();
  });

  it('shows a friendly message when sign-in fails', async () => {
    const signInWithEmail = jest.fn().mockRejectedValue({ code: 'auth/wrong-password' });

    await render(LoginComponent, {
      providers: [
        { provide: AuthService, useValue: { signInWithEmail, isApproved: () => true } },
        { provide: Router, useValue: { navigateByUrl: jest.fn() } },
        { provide: ActivatedRoute, useValue: activatedRouteStub() }
      ]
    });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Email'), 'demo@example.com');
    await user.type(screen.getByLabelText('Password'), 'wrong');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/incorrect email or password/i);
  });

  it('signs in with Google', async () => {
    const signInWithGoogle = jest.fn().mockResolvedValue(undefined);
    const navigateByUrl = jest.fn().mockResolvedValue(true);

    await render(LoginComponent, {
      providers: [
        { provide: AuthService, useValue: { signInWithGoogle, isApproved: () => true } },
        { provide: Router, useValue: { navigateByUrl } },
        { provide: ActivatedRoute, useValue: activatedRouteStub() }
      ]
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /continue with google/i }));

    expect(signInWithGoogle).toHaveBeenCalled();
    expect(navigateByUrl).toHaveBeenCalledWith('/chat');
  });

  it('toggles the password field between hidden and visible text', async () => {
    await render(LoginComponent, {
      providers: [
        { provide: AuthService, useValue: {} },
        { provide: Router, useValue: { navigateByUrl: jest.fn() } },
        { provide: ActivatedRoute, useValue: activatedRouteStub() }
      ]
    });

    const passwordInput = screen.getByLabelText('Password') as HTMLInputElement;
    expect(passwordInput.type).toBe('password');

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /show password/i }));
    expect(passwordInput.type).toBe('text');

    await user.click(screen.getByRole('button', { name: /hide password/i }));
    expect(passwordInput.type).toBe('password');
  });
});
