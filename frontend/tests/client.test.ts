import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../src/api/client';

afterEach(() => vi.unstubAllGlobals());

describe('Viewer transport contract', () => {
  it('keeps overlapping session requests on one cookie and permits later renewal', async () => {
    let resolve!: (response: Response) => void;
    const pending = new Promise<Response>((done) => {
      resolve = done;
    });
    const fetch = vi
      .fn()
      .mockReturnValueOnce(pending)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrf_token: 'renewed-session', run: {} })),
      );
    vi.stubGlobal('fetch', fetch);
    const first = api.bootstrap();
    const overlapping = api.bootstrap();
    expect(fetch).toHaveBeenCalledTimes(1);
    resolve(new Response(JSON.stringify({ csrf_token: 'initial-session', run: {} })));
    const results = await Promise.all([first, overlapping]);
    expect(results.map((result) => result.csrf_token)).toEqual([
      'initial-session',
      'initial-session',
    ]);
    expect((await api.bootstrap()).csrf_token).toBe('renewed-session');
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('requests the full bounded history on initial load and reconnect', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: {}, frames: [] })));
    vi.stubGlobal('fetch', fetch);
    await api.snapshot('mission/one');
    expect(fetch).toHaveBeenCalledWith('/v1/runs/mission%2Fone/snapshot?history=41', {
      credentials: 'same-origin',
    });
  });

  it('preserves actionable normative API errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: 'control_not_applied',
            message: 'Persistence retry is active; the command was not applied.',
            details: {},
            request_id: 'test-request',
          }),
          { status: 503 },
        ),
      ),
    );
    await expect(
      api.control('mission', 'test-token', 'pause', undefined, 'test-key'),
    ).rejects.toThrow('Persistence retry is active; the command was not applied.');
  });
});
