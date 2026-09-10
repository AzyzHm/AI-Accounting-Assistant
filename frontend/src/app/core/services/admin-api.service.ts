import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '@core/services/api.service';
import { Role, UserProfile } from '@core/models/user.model';
import { LoginEvent, UsageTotal } from '@core/models/admin-stats.model';

@Injectable({ providedIn: 'root' })
export class AdminApiService {
  private readonly api = inject(ApiService);

  listUsers(): Observable<UserProfile[]> {
    return this.api.get<UserProfile[]>('/admin/users');
  }

  updateRole(uid: string, role: Role): Observable<UserProfile> {
    return this.api.patch<UserProfile>(`/admin/users/${uid}/role`, { role });
  }

  approveUser(uid: string): Observable<UserProfile> {
    return this.api.patch<UserProfile>(`/admin/users/${uid}/approve`, {});
  }

  deleteUser(uid: string): Observable<void> {
    return this.api.delete<void>(`/admin/users/${uid}`);
  }

  listLoginEvents(): Observable<LoginEvent[]> {
    return this.api.get<LoginEvent[]>('/admin/stats/logins');
  }

  listUsageTotals(): Observable<UsageTotal[]> {
    return this.api.get<UsageTotal[]>('/admin/stats/usage');
  }
}
