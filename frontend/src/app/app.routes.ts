import { Routes } from '@angular/router';

import { pendingApprovalGuard } from '@core/guards/auth.guard';

export const routes: Routes = [
  {
    path: '',
    loadChildren: () => import('@features/home/home.routes').then((m) => m.HOME_ROUTES)
  },
  {
    path: 'chat',
    loadChildren: () => import('@features/chat/chat.routes').then((m) => m.CHAT_ROUTES)
  },
  {
    path: 'login',
    loadChildren: () => import('@features/auth/auth.routes').then((m) => m.AUTH_ROUTES)
  },
  {
    path: 'pending-approval',
    canActivate: [pendingApprovalGuard],
    loadComponent: () =>
      import('@features/auth/pending-approval/pending-approval.component').then(
        (m) => m.PendingApprovalComponent
      )
  },
  {
    path: 'admin',
    loadChildren: () => import('@features/admin/admin.routes').then((m) => m.ADMIN_ROUTES)
  },
  {
    path: '**',
    redirectTo: ''
  }
];
