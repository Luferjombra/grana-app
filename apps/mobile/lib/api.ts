import { supabase } from './supabase';

const apiUrl = process.env.EXPO_PUBLIC_API_URL as string;

/**
 * fetch autenticado sem impor Content-Type — usado pelo upload multipart, em
 * que o próprio fetch precisa gerar o boundary. Definir o header à mão ali
 * quebraria o parse do arquivo no servidor.
 */
export async function authorizedFetch(path: string, init?: RequestInit): Promise<Response> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers: {
      ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${await response.text()}`);
  }

  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authorizedFetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
};
