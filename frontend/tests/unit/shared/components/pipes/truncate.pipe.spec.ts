import { TruncatePipe } from '@shared/pipes/truncate.pipe';

describe('TruncatePipe', () => {
  const pipe = new TruncatePipe();

  it('returns the original string when shorter than the limit', () => {
    expect(pipe.transform('hello', 10)).toBe('hello');
  });

  it('truncates and appends the suffix when longer than the limit', () => {
    expect(pipe.transform('hello world', 5)).toBe('hello...');
  });

  it('returns an empty string for falsy input', () => {
    expect(pipe.transform('', 5)).toBe('');
  });
});
