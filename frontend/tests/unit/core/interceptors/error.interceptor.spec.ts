import { TestBed } from '@angular/core/testing';
import { HttpErrorResponse, HttpHandlerFn, HttpRequest, HttpEvent } from '@angular/common/http';
import { Router } from '@angular/router';
import { firstValueFrom, of, throwError } from 'rxjs';

import { errorInterceptor } from '@core/interceptors/error.interceptor';
import { AuthService } from '@core/services/auth.service';

function runInterceptor(req: HttpRequest<unknown>, next: HttpHandlerFn) {
  return TestBed.runInInjectionContext(() => errorInterceptor(req, next));
}

describe('errorInterceptor', () => {
  it('logs out and redirects to /login on a 401', async () => {
    const logout = jest.fn().mockResolvedValue(undefined);
    const navigate = jest.fn().mockResolvedValue(true);

    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: { logout } },
        { provide: Router, useValue: { navigate } }
      ]
    });

    const req = new HttpRequest('GET', '/chat/');
    const error = new HttpErrorResponse({ status: 401 });
    const next: HttpHandlerFn = (() => throwError(() => error)) as unknown as HttpHandlerFn;

    await expect(firstValueFrom(runInterceptor(req, next))).rejects.toBe(error);

    await Promise.resolve();
    await Promise.resolve();

    expect(logout).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith(['/login']);
  });

  it('does not log out on a non-401 error', async () => {
    const logout = jest.fn();
    const navigate = jest.fn();

    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: { logout } },
        { provide: Router, useValue: { navigate } }
      ]
    });

    const req = new HttpRequest('GET', '/chat/');
    const error = new HttpErrorResponse({ status: 500 });
    const next: HttpHandlerFn = (() => throwError(() => error)) as unknown as HttpHandlerFn;

    await expect(firstValueFrom(runInterceptor(req, next))).rejects.toBe(error);

    expect(logout).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });

  it('passes a successful response through unchanged', async () => {
    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: { logout: jest.fn() } },
        { provide: Router, useValue: { navigate: jest.fn() } }
      ]
    });

    const req = new HttpRequest('GET', '/chat/');
    const response = {} as HttpEvent<unknown>;
    const next: HttpHandlerFn = (() => of(response)) as unknown as HttpHandlerFn;

    await expect(firstValueFrom(runInterceptor(req, next))).resolves.toBe(response);
  });
});
