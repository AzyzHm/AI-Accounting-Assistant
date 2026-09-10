import { TestBed } from '@angular/core/testing';
import { Router, UrlTree } from '@angular/router';

import { authGuard, guestGuard, pendingApprovalGuard } from '@core/guards/auth.guard';
import { AuthService } from '@core/services/auth.service';

function setup(isAuthenticated: boolean, isApproved = true) {
  const authService = {
    ready: Promise.resolve(),
    isAuthenticated: () => isAuthenticated,
    isApproved: () => isApproved
  };
  const urlTree = {} as UrlTree;
  const router = { parseUrl: jest.fn().mockReturnValue(urlTree) };

  TestBed.configureTestingModule({
    providers: [
      { provide: AuthService, useValue: authService },
      { provide: Router, useValue: router }
    ]
  });

  return { router, urlTree };
}

describe('authGuard', () => {
  it('allows an approved, authenticated user through', async () => {
    setup(true, true);

    const result = await TestBed.runInInjectionContext(() =>
      authGuard(null as never, null as never)
    );

    expect(result).toBe(true);
  });

  it('sends an unauthenticated user to /login', async () => {
    const { router, urlTree } = setup(false);

    const result = await TestBed.runInInjectionContext(() =>
      authGuard(null as never, null as never)
    );

    expect(router.parseUrl).toHaveBeenCalledWith('/login');
    expect(result).toBe(urlTree);
  });

  it('sends an authenticated but unapproved user to /pending-approval', async () => {
    const { router, urlTree } = setup(true, false);

    const result = await TestBed.runInInjectionContext(() =>
      authGuard(null as never, null as never)
    );

    expect(router.parseUrl).toHaveBeenCalledWith('/pending-approval');
    expect(result).toBe(urlTree);
  });
});

describe('guestGuard', () => {
  it('allows a signed-out visitor through to /login', async () => {
    setup(false);

    const result = await TestBed.runInInjectionContext(() =>
      guestGuard(null as never, null as never)
    );

    expect(result).toBe(true);
  });

  it('redirects an already-signed-in, approved user to /chat', async () => {
    const { router, urlTree } = setup(true, true);

    const result = await TestBed.runInInjectionContext(() =>
      guestGuard(null as never, null as never)
    );

    expect(router.parseUrl).toHaveBeenCalledWith('/chat');
    expect(result).toBe(urlTree);
  });

  it('redirects an already-signed-in, unapproved user to /pending-approval', async () => {
    const { router, urlTree } = setup(true, false);

    const result = await TestBed.runInInjectionContext(() =>
      guestGuard(null as never, null as never)
    );

    expect(router.parseUrl).toHaveBeenCalledWith('/pending-approval');
    expect(result).toBe(urlTree);
  });
});

describe('pendingApprovalGuard', () => {
  it('sends an unauthenticated visitor to /login', async () => {
    const { router, urlTree } = setup(false);

    const result = await TestBed.runInInjectionContext(() =>
      pendingApprovalGuard(null as never, null as never)
    );

    expect(router.parseUrl).toHaveBeenCalledWith('/login');
    expect(result).toBe(urlTree);
  });

  it('lets an authenticated, unapproved user see the page', async () => {
    setup(true, false);

    const result = await TestBed.runInInjectionContext(() =>
      pendingApprovalGuard(null as never, null as never)
    );

    expect(result).toBe(true);
  });

  it('redirects an already-approved user away to /chat', async () => {
    const { router, urlTree } = setup(true, true);

    const result = await TestBed.runInInjectionContext(() =>
      pendingApprovalGuard(null as never, null as never)
    );

    expect(router.parseUrl).toHaveBeenCalledWith('/chat');
    expect(result).toBe(urlTree);
  });
});
