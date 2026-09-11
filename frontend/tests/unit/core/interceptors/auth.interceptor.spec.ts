import { TestBed } from '@angular/core/testing';
import { HttpRequest, HttpHandlerFn, HttpEvent } from '@angular/common/http';
import { of } from 'rxjs';
import { firstValueFrom } from 'rxjs';

import { authInterceptor } from '@core/interceptors/auth.interceptor';
import { AuthService } from '@core/services/auth.service';
import { environment } from '@env/environment';

function runInterceptor(req: HttpRequest<unknown>, next: HttpHandlerFn) {
  return TestBed.runInInjectionContext(() => authInterceptor(req, next));
}

describe('authInterceptor', () => {
  it('attaches a Bearer token to requests targeting the backend API', async () => {
    const getIdToken = jest.fn().mockResolvedValue('the-id-token');
    TestBed.configureTestingModule({
      providers: [{ provide: AuthService, useValue: { getIdToken } }]
    });

    const req = new HttpRequest('GET', `${environment.apiBaseUrl}/auth/me`);
    const next: HttpHandlerFn = jest.fn(
      () => of({} as HttpEvent<unknown>) as ReturnType<HttpHandlerFn>
    ) as unknown as HttpHandlerFn;

    await firstValueFrom(runInterceptor(req, next));

    const forwardedReq = (next as jest.Mock).mock.calls[0][0] as HttpRequest<unknown>;
    expect(forwardedReq.headers.get('Authorization')).toBe('Bearer the-id-token');
  });

  it('does not attach a header when signed out', async () => {
    const getIdToken = jest.fn().mockResolvedValue(null);
    TestBed.configureTestingModule({
      providers: [{ provide: AuthService, useValue: { getIdToken } }]
    });

    const req = new HttpRequest('GET', `${environment.apiBaseUrl}/auth/me`);
    const next: HttpHandlerFn = jest.fn(
      () => of({} as HttpEvent<unknown>) as ReturnType<HttpHandlerFn>
    ) as unknown as HttpHandlerFn;

    await firstValueFrom(runInterceptor(req, next));

    const forwardedReq = (next as jest.Mock).mock.calls[0][0] as HttpRequest<unknown>;
    expect(forwardedReq.headers.has('Authorization')).toBe(false);
  });

  it('passes non-backend requests through untouched, without checking auth', async () => {
    const getIdToken = jest.fn();
    TestBed.configureTestingModule({
      providers: [{ provide: AuthService, useValue: { getIdToken } }]
    });

    const req = new HttpRequest('GET', 'https://third-party.example.com/data');
    const next: HttpHandlerFn = jest.fn(
      () => of({} as HttpEvent<unknown>) as ReturnType<HttpHandlerFn>
    ) as unknown as HttpHandlerFn;

    await firstValueFrom(runInterceptor(req, next));

    expect(getIdToken).not.toHaveBeenCalled();
    expect(next).toHaveBeenCalledWith(req);
  });
});
