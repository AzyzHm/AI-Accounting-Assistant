import { TestBed } from '@angular/core/testing';
import { Router, UrlTree } from '@angular/router';

import { redirectIfUnauthenticated } from '@core/guards/guard-helpers';
import { AuthService } from '@core/services/auth.service';

function setup(isAuthenticated: boolean) {
  const authService = {
    ready: Promise.resolve(),
    isAuthenticated: () => isAuthenticated
  } as unknown as AuthService;
  const urlTree = {} as UrlTree;
  const router = { parseUrl: jest.fn().mockReturnValue(urlTree) } as unknown as Router;

  TestBed.configureTestingModule({});

  return { authService, router, urlTree };
}

describe('redirectIfUnauthenticated', () => {
  it('returns null once the authenticated caller is ready', async () => {
    const { authService, router } = setup(true);

    const result = await redirectIfUnauthenticated(authService, router);

    expect(result).toBeNull();
  });

  it('returns a redirect to /login for an unauthenticated caller', async () => {
    const { authService, router, urlTree } = setup(false);

    const result = await redirectIfUnauthenticated(authService, router);

    expect(router.parseUrl).toHaveBeenCalledWith('/login');
    expect(result).toBe(urlTree);
  });
});
