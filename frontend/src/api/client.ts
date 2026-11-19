export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const BASE = '/api/v1';

async function request(path: string, accept: string, signal?: AbortSignal): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { signal, headers: { Accept: accept } });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError(0, 'Cannot reach the PaveWatch server. Is the backend running?');
  }
  if (!res.ok) {
    let detail = res.statusText || `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res;
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await request(path, 'application/json', signal);
  return res.json() as Promise<T>;
}

/** Name from a Content-Disposition header (RFC 5987 `filename*` first, then `filename`). */
function filenameFrom(header: string | null): string | null {
  if (!header) return null;
  const star = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header);
  if (star) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {
      /* fall through */
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : null;
}

/**
 * Fetches a file from the API and hands it to the browser as a download.
 * Fetching first (instead of a plain link) lets the caller show progress and a readable error.
 * Returns the file name used.
 */
export async function downloadFile(path: string, fallbackName: string, accept = 'application/pdf'): Promise<string> {
  const res = await request(path, accept);
  const name = filenameFrom(res.headers.get('Content-Disposition')) ?? fallbackName;
  const url = URL.createObjectURL(await res.blob());
  try {
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    // Give the browser a moment to start the download before releasing the blob.
    setTimeout(() => URL.revokeObjectURL(url), 30_000);
  }
  return name;
}

export const enc = encodeURIComponent;
