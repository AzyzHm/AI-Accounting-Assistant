import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AdminApiService } from '@core/services/admin-api.service';
import { UsageTotal } from '@core/models/admin-stats.model';
import { RoleBadgeComponent } from '@shared/components/role-badge/role-badge.component';
import { ButtonComponent } from '@shared/components/button/button.component';
import { AdminUsageLimitsModalComponent } from './limits-modal/limits-modal.component';

@Component({
  selector: 'app-admin-usage',
  standalone: true,
  imports: [FormsModule, RoleBadgeComponent, ButtonComponent, AdminUsageLimitsModalComponent],
  templateUrl: './admin-usage.component.html',
  styleUrl: './admin-usage.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AdminUsageComponent implements OnInit {
  private readonly adminApi = inject(AdminApiService);

  protected readonly totals = signal<UsageTotal[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly searchTerm = signal('');
  protected readonly limitsTarget = signal<UsageTotal | null>(null);

  protected readonly totalTokensUsed = computed(() =>
    this.totals().reduce((sum, entry) => sum + (entry.total_tokens ?? 0), 0)
  );
  protected readonly totalSearchCreditsUsed = computed(() =>
    this.totals().reduce((sum, entry) => sum + (entry.search_credits_used ?? 0), 0)
  );
  protected readonly trackedUsers = computed(() => this.totals().length);

  protected readonly filteredTotals = computed(() => {
    const term = this.searchTerm().trim().toLowerCase();
    const sorted = [...this.totals()].sort((a, b) => b.total_tokens - a.total_tokens);

    if (!term) {
      return sorted;
    }

    return sorted.filter((entry) =>
      [entry.email, entry.display_name].some((value) => value?.toLowerCase().includes(term))
    );
  });

  ngOnInit(): void {
    this.load();
  }

  protected openLimits(entry: UsageTotal): void {
    if (entry.role !== 'USER') {
      return;
    }
    this.limitsTarget.set(entry);
  }

  protected closeLimits(): void {
    this.limitsTarget.set(null);
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);

    this.adminApi.listUsageTotals().subscribe({
      next: (totals) => {
        this.totals.set(totals);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Could not load usage data. Please try again.');
        this.loading.set(false);
      }
    });
  }
}
