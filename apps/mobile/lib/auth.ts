import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';

import { supabase } from './supabase';

// Incrementar sempre que o texto de consentimento (specs/04) mudar.
export const CURRENT_TERMS_VERSION = 'v1-draft';

export async function signUpWithEmail(fullName: string, email: string, password: string) {
  const { error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: {
        full_name: fullName,
        terms_version: CURRENT_TERMS_VERSION,
      },
    },
  });

  if (error) throw error;
}

export async function signInWithEmail(email: string, password: string) {
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
}

export async function requestPasswordReset(email: string) {
  // Precisa bater exatamente com o que está cadastrado em Supabase Auth ->
  // URL Configuration -> Redirect URLs (hoje só "grana://", sem path/wildcard).
  const redirectTo = Linking.createURL('');
  const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo });
  if (error) throw error;
}

export async function updatePassword(password: string) {
  const { error } = await supabase.auth.updateUser({ password });
  if (error) throw error;
}

/**
 * OAuth (Google) não permite anexar metadata própria na criação do
 * auth.users — por isso o consentimento é gravado à parte, logo após a
 * sessão ser estabelecida. Ver infra/supabase/migrations/0001_profiles_consent.sql.
 */
export async function signInWithGoogle() {
  // Precisa bater exatamente com o que está cadastrado em Supabase Auth ->
  // URL Configuration -> Redirect URLs (hoje só "grana://", sem path/wildcard).
  const redirectTo = Linking.createURL('');

  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo, skipBrowserRedirect: true },
  });
  if (error) throw error;

  const result = await WebBrowser.openAuthSessionAsync(data.url, redirectTo);
  if (result.type !== 'success') return;

  // Em PKCE o retorno traz ?code=... na query string (não tokens no fragment).
  const { code, errorDescription } = parseAuthCallback(result.url);
  if (errorDescription) throw new Error(errorDescription);
  if (!code) throw new Error('Resposta de login do Google incompleta.');

  const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
  if (exchangeError) throw exchangeError;

  await recordConsentIfMissing();
}

export function parseAuthCallback(url: string) {
  const { searchParams } = new URL(url);
  return {
    code: searchParams.get('code'),
    type: searchParams.get('type'),
    errorDescription: searchParams.get('error_description'),
  };
}

async function recordConsentIfMissing() {
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return;

  // O trigger de cadastro roda na mesma transação do insert em auth.users,
  // mas dá uma pequena margem pra visibilidade do profile via API replicar.
  for (let attempt = 0; attempt < 3; attempt++) {
    const { data: profile, error } = await supabase
      .from('profiles')
      .select('terms_accepted_at')
      .eq('id', user.id)
      .maybeSingle();

    if (error) return;

    if (profile) {
      if (!profile.terms_accepted_at) {
        await supabase
          .from('profiles')
          .update({
            terms_accepted_at: new Date().toISOString(),
            terms_version: CURRENT_TERMS_VERSION,
          })
          .eq('id', user.id);
      }
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, 300));
  }
}
