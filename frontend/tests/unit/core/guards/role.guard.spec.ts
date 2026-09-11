import { TestBed } from '@angular/core/testing';
import { Router, UrlTree } from '@angular/router';

import { roleGuard } from '@core/guards/role.guard';
import { AuthService } from '@core/services/auth.service';
import { Role } from '@core/models/user.model';

function setup(isAuthenticated: boolean, role: Role | null, isApproved = true) {
  const authService = {
    ready: Promise.resolve(),
    isAuthenticated: () => isAuthenticated,
    isApproved: () => isApproved,
    role: () => role
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

describe('roleGuard', () => {
  it('allows a user whose role is in the allowed list', async () => {
    setup(true, 'ADMIN');
    const guard = roleGuard('ADMIN', 'SUPER_ADMIN');

    const result = await TestBed.runInInjectionContext(() => guard(null as never, null as never));

    expect(result).toBe(true);
  });

  it('sends a signed-out visitor to /login', async () => {
    const { router, urlTree } = setup(false, null);
    const guard = roleGuard('ADMIN', 'SUPER_ADMIN');

    const result = await TestBed.runInInjectionContext(() => guard(null as never, null as never));

    expect(router.parseUrl).toHaveBeenCalledWith('/login');
    expect(result).toBe(urlTree);
  });

  it('sends a signed-in user with the wrong role to /chat', async () => {
    const { router, urlTree } = setup(true, 'USER');
    const guard = roleGuard('ADMIN', 'SUPER_ADMIN');

    const result = await TestBed.runInInjectionContext(() => guard(null as never, null as never));

    expect(router.parseUrl).toHaveBeenCalledWith('/chat');
    expect(result).toBe(urlTree);
  });

  it('sends an unapproved account to /pending-approval even with an allowed role', async () => {
    const { router, urlTree } = setup(true, 'ADMIN', false);
    const guard = roleGuard('ADMIN', 'SUPER_ADMIN');

    const result = await TestBed.runInInjectionContext(() => guard(null as never, null as never));

    expect(router.parseUrl).toHaveBeenCalledWith('/pending-approval');
    expect(result).toBe(urlTree);
  });
});
