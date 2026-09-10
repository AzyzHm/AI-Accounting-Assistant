import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from '@core/services/auth.service';
import { ButtonComponent } from '@shared/components/button/button.component';

@Component({
  selector: 'app-pending-approval',
  standalone: true,
  imports: [ButtonComponent],
  templateUrl: './pending-approval.component.html',
  styleUrl: './pending-approval.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class PendingApprovalComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly checking = signal(false);
  protected readonly stillPending = signal(false);

  protected readonly email = this.authService.profile()?.email ?? null;

  protected async checkStatus(): Promise<void> {
    if (this.checking()) {
      return;
    }

    this.checking.set(true);
    this.stillPending.set(false);

    try {
      await this.authService.refreshProfile();
      if (this.authService.isApproved()) {
        await this.router.navigateByUrl('/chat');
      } else {
        this.stillPending.set(true);
      }
    } finally {
      this.checking.set(false);
    }
  }

  protected async signOut(): Promise<void> {
    await this.authService.logout();
    await this.router.navigateByUrl('/login');
  }
}
