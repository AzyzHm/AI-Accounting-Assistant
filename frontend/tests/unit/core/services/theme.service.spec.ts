import { TestBed } from '@angular/core/testing';

import { ThemeService } from '@core/services/theme.service';

function mockMatchMedia(matches: boolean) {
  const listeners: ((event: MediaQueryListEvent) => void)[] = [];

  (window.matchMedia as jest.Mock).mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn((_event: string, listener: (event: MediaQueryListEvent) => void) => {
      listeners.push(listener);
    }),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn()
  }));

  return {
    fireChange: (nextMatches: boolean) => {
      listeners.forEach((listener) => listener({ matches: nextMatches } as MediaQueryListEvent));
    }
  };
}

describe('ThemeService', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    TestBed.configureTestingModule({});
  });

  it('defaults to system when nothing is stored', () => {
    mockMatchMedia(false);

    const service = TestBed.inject(ThemeService);

    expect(service.preference()).toBe('system');
  });

  it('reads a previously stored preference', () => {
    localStorage.setItem('comptarag-theme', 'dark');
    mockMatchMedia(false);

    const service = TestBed.inject(ThemeService);

    expect(service.preference()).toBe('dark');
  });

  it('falls back to system for a corrupted stored value', () => {
    localStorage.setItem('comptarag-theme', 'sepia');
    mockMatchMedia(false);

    const service = TestBed.inject(ThemeService);

    expect(service.preference()).toBe('system');
  });

  it('resolves system to dark when the OS prefers dark', () => {
    mockMatchMedia(true);

    const service = TestBed.inject(ThemeService);

    expect(service.resolvedTheme()).toBe('dark');
  });

  it('resolves system to light when the OS prefers light', () => {
    mockMatchMedia(false);

    const service = TestBed.inject(ThemeService);

    expect(service.resolvedTheme()).toBe('light');
  });

  it('applies the resolved theme to the document on construction', () => {
    mockMatchMedia(true);

    TestBed.inject(ThemeService);

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('updates the preference, storage, and document when setPreference is called', () => {
    mockMatchMedia(false);
    const service = TestBed.inject(ThemeService);

    service.setPreference('dark');

    expect(service.preference()).toBe('dark');
    expect(service.resolvedTheme()).toBe('dark');
    expect(localStorage.getItem('comptarag-theme')).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('reacts to the OS preference changing while set to system', () => {
    const media = mockMatchMedia(false);
    const service = TestBed.inject(ThemeService);
    expect(service.resolvedTheme()).toBe('light');

    media.fireChange(true);

    expect(service.resolvedTheme()).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('ignores an OS preference change once a manual preference is set', () => {
    const media = mockMatchMedia(false);
    const service = TestBed.inject(ThemeService);

    service.setPreference('light');
    media.fireChange(true);

    expect(service.resolvedTheme()).toBe('light');
  });
});
