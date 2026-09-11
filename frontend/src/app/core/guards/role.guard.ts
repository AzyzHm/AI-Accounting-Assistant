import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from '@core/services/auth.service';
import { Role } from '@core/models/user.model';

import { redirectIfUnauthenticated } from './guard-helpers';

export function roleGuard(...roles: Role[]): CanActivateFn {
  return async () => {
    const authService = inject(AuthService);
    const router = inject(Router);

    const redirect = await redirectIfUnauthenticated(authService, router);
    if (redirect) {
      return redirect;
    }

    if (!authService.isApproved()) {
      return router.parseUrl('/pending-approval');
    }

    const role = authService.role();
    if (role && roles.includes(role)) {
      return true;
    }

    return router.parseUrl('/chat');
  };
}
