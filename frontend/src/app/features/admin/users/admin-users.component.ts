import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  OnInit,
  signal
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AdminApiService } from '@core/services/admin-api.service';
import { AuthService } from '@core/services/auth.service';
import { Role, UserProfile } from '@core/models/user.model';
import { RoleBadgeComponent } from '@shared/components/role-badge/role-badge.component';

const ASSIGNABLE_ROLES: Role[] = ['USER', 'ADMIN'];

@Component({
  selector: 'app-admin-users',
  standalone: true,
  imports: [FormsModule, RoleBadgeComponent],
  templateUrl: './admin-users.component.html',
  styleUrl: './admin-users.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AdminUsersComponent implements OnInit {
  private readonly adminApi = inject(AdminApiService);
  private readonly authService = inject(AuthService);

  protected readonly users = signal<UserProfile[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly pendingUid = signal<string | null>(null);

  protected readonly viewerUid = computed(() => this.authService.profile()?.uid ?? null);
  protected readonly viewerIsSuperAdmin = computed(() => this.authService.role() === 'SUPER_ADMIN');
  protected readonly assignableRoles = ASSIGNABLE_ROLES;

  protected readonly totalUsers = computed(
    () => this.users().filter((user) => user.role === 'USER').length
  );
  protected readonly totalAdmins = computed(
    () => this.users().filter((user) => user.role === 'ADMIN').length
  );
  protected readonly totalPending = computed(
    () => this.users().filter((user) => !user.approved).length
  );

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);

    this.adminApi.listUsers().subscribe({
      next: (users) => {
        this.users.set(users);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Could not load the user list. Please try again.');
        this.loading.set(false);
      }
    });
  }

  protected canEditRole(user: UserProfile): boolean {
    return this.viewerIsSuperAdmin() && user.uid !== this.viewerUid();
  }

  protected canDelete(user: UserProfile): boolean {
    if (user.uid === this.viewerUid()) {
      return false;
    }
    return this.viewerIsSuperAdmin() || user.role === 'USER';
  }

  protected canApprove(user: UserProfile): boolean {
    if (user.approved || user.uid === this.viewerUid()) {
      return false;
    }
    return this.viewerIsSuperAdmin() || user.role === 'USER';
  }

  protected changeRole(user: UserProfile, role: Role): void {
    if (role === user.role || this.pendingUid()) {
      return;
    }

    this.pendingUid.set(user.uid);
    this.error.set(null);

    this.adminApi.updateRole(user.uid, role).subscribe({
      next: (updated) => {
        this.users.update((current) =>
          current.map((entry) => (entry.uid === updated.uid ? updated : entry))
        );
        this.pendingUid.set(null);
      },
      error: () => {
        this.error.set(`Could not update the role for ${user.email ?? user.uid}.`);
        this.pendingUid.set(null);
      }
    });
  }

  protected approveUser(user: UserProfile): void {
    if (this.pendingUid()) {
      return;
    }

    this.pendingUid.set(user.uid);
    this.error.set(null);

    this.adminApi.approveUser(user.uid).subscribe({
      next: (updated) => {
        this.users.update((current) =>
          current.map((entry) => (entry.uid === updated.uid ? updated : entry))
        );
        this.pendingUid.set(null);
      },
      error: () => {
        this.error.set(`Could not approve ${user.email ?? user.uid}.`);
        this.pendingUid.set(null);
      }
    });
  }

  protected deleteUser(user: UserProfile): void {
    if (this.pendingUid()) {
      return;
    }
    if (!window.confirm(`Delete ${user.email ?? user.uid}? This cannot be undone.`)) {
      return;
    }

    this.pendingUid.set(user.uid);
    this.error.set(null);

    this.adminApi.deleteUser(user.uid).subscribe({
      next: () => {
        this.users.update((current) => current.filter((entry) => entry.uid !== user.uid));
        this.pendingUid.set(null);
      },
      error: () => {
        this.error.set(`Could not delete ${user.email ?? user.uid}.`);
        this.pendingUid.set(null);
      }
    });
  }
}
