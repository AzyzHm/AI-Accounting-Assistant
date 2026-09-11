import { Router, UrlTree } from '@angular/router';

import { AuthService } from '@core/services/auth.service';

export async function redirectIfUnauthenticated(
  authService: AuthService,
  router: Router
): Promise<UrlTree | null> {
  await authService.ready;

  if (!authService.isAuthenticated()) {
    return router.parseUrl('/login');
  }

  return null;
}
