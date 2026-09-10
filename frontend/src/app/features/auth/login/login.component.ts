import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { take } from 'rxjs';

import { AuthService } from '@core/services/auth.service';
import { ButtonComponent } from '@shared/components/button/button.component';

type AuthMode = 'sign-in' | 'register';

function friendlyAuthError(error: unknown): string {
  const code = (error as { code?: string })?.code ?? '';

  switch (code) {
    case 'auth/invalid-credential':
    case 'auth/wrong-password':
    case 'auth/user-not-found':
      return 'Incorrect email or password.';
    case 'auth/email-already-in-use':
      return 'An account already exists for this email, try signing in instead.';
    case 'auth/weak-password':
      return 'Please choose a password with at least 6 characters.';
    case 'auth/invalid-email':
      return 'Please enter a valid email address.';
    case 'auth/popup-closed-by-user':
      return 'Google sign-in was cancelled.';
    default:
      return 'Something went wrong, please try again.';
  }
}

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, ButtonComponent],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class LoginComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly mode = signal<AuthMode>('sign-in');
  protected readonly email = signal('');
  protected readonly password = signal('');
  protected readonly passwordVisible = signal(false);
  protected readonly pending = signal(false);
  protected readonly error = signal<string | null>(null);

  constructor() {
    this.route.queryParamMap.pipe(take(1)).subscribe((params) => {
      if (params.get('mode') === 'register') {
        this.mode.set('register');
      }
    });
  }

  protected toggleMode(): void {
    this.mode.set(this.mode() === 'sign-in' ? 'register' : 'sign-in');
    this.error.set(null);
  }

  protected togglePasswordVisibility(): void {
    this.passwordVisible.update((visible) => !visible);
  }

  protected async submit(): Promise<void> {
    const email = this.email().trim();
    const password = this.password();
    if (!email || !password || this.pending()) {
      return;
    }

    this.pending.set(true);
    this.error.set(null);

    try {
      if (this.mode() === 'sign-in') {
        await this.authService.signInWithEmail(email, password);
      } else {
        await this.authService.registerWithEmail(email, password);
      }
      await this.navigateAfterAuth();
    } catch (err) {
      this.error.set(friendlyAuthError(err));
    } finally {
      this.pending.set(false);
    }
  }

  protected async continueWithGoogle(): Promise<void> {
    if (this.pending()) {
      return;
    }

    this.pending.set(true);
    this.error.set(null);

    try {
      await this.authService.signInWithGoogle();
      await this.navigateAfterAuth();
    } catch (err) {
      this.error.set(friendlyAuthError(err));
    } finally {
      this.pending.set(false);
    }
  }

  private async navigateAfterAuth(): Promise<void> {
    await this.router.navigateByUrl(this.authService.isApproved() ? '/chat' : '/pending-approval');
  }
}
