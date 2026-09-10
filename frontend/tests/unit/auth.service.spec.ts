import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import {
  EmailAuthProvider,
  getAuth,
  reauthenticateWithCredential,
  updateEmail,
  updatePassword,
  updateProfile
} from 'firebase/auth';

import { AuthService } from '@core/services/auth.service';
import { ApiService } from '@core/services/api.service';

function currentFirebaseAuth() {
  return (getAuth as jest.Mock).mock.results[0].value;
}

describe('AuthService', () => {
  let apiPatch: jest.Mock;

  beforeEach(() => {
    (updateProfile as jest.Mock).mockReset().mockResolvedValue(undefined);
    (updateEmail as jest.Mock).mockReset().mockResolvedValue(undefined);
    (updatePassword as jest.Mock).mockReset().mockResolvedValue(undefined);
    (reauthenticateWithCredential as jest.Mock).mockReset().mockResolvedValue(undefined);
    (EmailAuthProvider.credential as jest.Mock).mockReset().mockReturnValue('mock-credential');

    currentFirebaseAuth().currentUser = { email: 'me@example.com', getIdToken: jest.fn() };

    apiPatch = jest.fn().mockReturnValue(of({ uid: 'u1', email: 'me@example.com', role: 'USER' }));

    TestBed.configureTestingModule({
      providers: [
        AuthService,
        {
          provide: ApiService,
          useValue: { get: jest.fn().mockReturnValue(of({})), patch: apiPatch }
        }
      ]
    });
  });

  function service(): AuthService {
    return TestBed.inject(AuthService);
  }

  it('updates the display name via Firebase and syncs it to the backend', async () => {
    const authService = service();

    await authService.updateDisplayName('New Name');

    expect(updateProfile).toHaveBeenCalledWith(currentFirebaseAuth().currentUser, {
      displayName: 'New Name'
    });
    expect(apiPatch).toHaveBeenCalledWith('/auth/me', { display_name: 'New Name' });
  });

  it('re-authenticates before changing the email, then syncs it to the backend', async () => {
    const authService = service();

    await authService.updateEmail('new@example.com', 'current-pass');

    expect(EmailAuthProvider.credential).toHaveBeenCalledWith('me@example.com', 'current-pass');
    expect(reauthenticateWithCredential).toHaveBeenCalledWith(
      currentFirebaseAuth().currentUser,
      'mock-credential'
    );
    expect(updateEmail).toHaveBeenCalledWith(currentFirebaseAuth().currentUser, 'new@example.com');
    expect(apiPatch).toHaveBeenCalledWith('/auth/me', { email: 'new@example.com' });
  });

  it('re-authenticates before changing the password, and never touches the backend', async () => {
    const authService = service();

    await authService.updatePassword('new-secret', 'current-pass');

    expect(reauthenticateWithCredential).toHaveBeenCalled();
    expect(updatePassword).toHaveBeenCalledWith(currentFirebaseAuth().currentUser, 'new-secret');
    expect(apiPatch).not.toHaveBeenCalled();
  });

  it('rejects a password change when no user is signed in', async () => {
    currentFirebaseAuth().currentUser = null;
    const authService = service();

    await expect(authService.updatePassword('new-secret', 'current-pass')).rejects.toThrow();
  });
});

describe('AuthService approval status', () => {
  it('exposes isApproved as false until a profile with approved:true is synced', async () => {
    const apiGet = jest.fn().mockReturnValue(of({ uid: 'u1', role: 'USER', approved: false }));

    TestBed.configureTestingModule({
      providers: [AuthService, { provide: ApiService, useValue: { get: apiGet, patch: jest.fn() } }]
    });

    const authService = TestBed.inject(AuthService);

    expect(authService.isApproved()).toBe(false);

    await authService.refreshProfile();

    expect(apiGet).toHaveBeenCalledWith('/auth/me');
    expect(authService.isApproved()).toBe(false);
  });

  it('reflects an approved profile after refreshProfile picks up the change', async () => {
    const apiGet = jest
      .fn()
      .mockReturnValueOnce(of({ uid: 'u1', role: 'USER', approved: false }))
      .mockReturnValueOnce(of({ uid: 'u1', role: 'USER', approved: true }));

    TestBed.configureTestingModule({
      providers: [AuthService, { provide: ApiService, useValue: { get: apiGet, patch: jest.fn() } }]
    });

    const authService = TestBed.inject(AuthService);
    await authService.refreshProfile();
    expect(authService.isApproved()).toBe(false);

    await authService.refreshProfile();

    expect(authService.isApproved()).toBe(true);
  });
});
