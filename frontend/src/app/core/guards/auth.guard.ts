import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from '@core/services/auth.service';

import { redirectIfUnauthenticated } from './guard-helpers';

export const authGuard: CanActivateFn = async () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  const redirect = await redirectIfUnauthenticated(authService, router);
  if (redirect) {
    return redirect;
  }

  if (!authService.isApproved()) {
    return router.parseUrl('/pending-approval');
  }

  return true;
};

export const guestGuard: CanActivateFn = async () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  await authService.ready;

  if (authService.isAuthenticated()) {
    return router.parseUrl(authService.isApproved() ? '/chat' : '/pending-approval');
  }

  return true;
};

export const pendingApprovalGuard: CanActivateFn = async () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  const redirect = await redirectIfUnauthenticated(authService, router);
  if (redirect) {
    return redirect;
  }

  if (authService.isApproved()) {
    return router.parseUrl('/chat');
  }

  return true;
};
