import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnInit,
  Output,
  inject,
  signal
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AdminApiService } from '@core/services/admin-api.service';
import { UsagePeriodCounts } from '@core/models/admin-stats.model';
import { ButtonComponent } from '@shared/components/button/button.component';
import { ModalComponent } from '@shared/components/modal/modal.component';

@Component({
  selector: 'app-admin-usage-limits-modal',
  standalone: true,
  imports: [FormsModule, ButtonComponent, ModalComponent],
  templateUrl: './limits-modal.component.html',
  styleUrl: './limits-modal.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AdminUsageLimitsModalComponent implements OnInit {
  private readonly adminApi = inject(AdminApiService);

  @Input({ required: true }) uid!: string;
  @Input() email: string | null = null;

  @Output() readonly closed = new EventEmitter<void>();

  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal<string | null>(null);

  protected readonly usage = signal<UsagePeriodCounts | null>(null);
  protected readonly dailyResetAt = signal('');
  protected readonly monthlyResetAt = signal('');

  protected readonly dailyTokenLimit = signal(0);
  protected readonly dailySearchLimit = signal(0);
  protected readonly monthlyTokenLimit = signal(0);
  protected readonly monthlySearchLimit = signal(0);

  ngOnInit(): void {
    this.load();
  }

  protected close(): void {
    this.closed.emit();
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);

    this.adminApi.getUserLimits(this.uid).subscribe({
      next: (detail) => {
        this.dailyTokenLimit.set(detail.limits.daily_token_limit);
        this.dailySearchLimit.set(detail.limits.daily_search_limit);
        this.monthlyTokenLimit.set(detail.limits.monthly_token_limit);
        this.monthlySearchLimit.set(detail.limits.monthly_search_limit);
        this.usage.set(detail.usage);
        this.dailyResetAt.set(detail.daily_reset_at);
        this.monthlyResetAt.set(detail.monthly_reset_at);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Could not load limits for this account. Please try again.');
        this.loading.set(false);
      }
    });
  }

  protected submit(): void {
    if (this.saving()) {
      return;
    }

    const limits = {
      daily_token_limit: this.dailyTokenLimit(),
      daily_search_limit: this.dailySearchLimit(),
      monthly_token_limit: this.monthlyTokenLimit(),
      monthly_search_limit: this.monthlySearchLimit()
    };

    if (Object.values(limits).some((value) => !Number.isFinite(value) || value < 0)) {
      this.error.set('Limits must be zero or a positive whole number.');
      this.success.set(null);
      return;
    }

    this.saving.set(true);
    this.error.set(null);
    this.success.set(null);

    this.adminApi.updateUserLimits(this.uid, limits).subscribe({
      next: (detail) => {
        this.usage.set(detail.usage);
        this.success.set('Limits updated.');
        this.saving.set(false);
      },
      error: () => {
        this.error.set('Could not save these limits. Please try again.');
        this.saving.set(false);
      }
    });
  }
}
