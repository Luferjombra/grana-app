import type { Session } from '@supabase/supabase-js';
import * as Linking from 'expo-linking';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

import { parseAuthCallback } from './auth';
import { supabase } from './supabase';

type AuthContextValue = {
  session: Session | null;
  initializing: boolean;
  passwordRecoveryPending: boolean;
  clearPasswordRecovery: () => void;
};

const AuthContext = createContext<AuthContextValue>({
  session: null,
  initializing: true,
  passwordRecoveryPending: false,
  clearPasswordRecovery: () => {},
});

/**
 * O link de "esqueci minha senha" abre o app via deep link com ?code=...&
 * type=recovery (PKCE) — igual ao OAuth, mas chega pelo cliente de e-mail,
 * não pelo WebBrowser.openAuthSessionAsync. Por isso precisa de um listener
 * de Linking global aqui, não no fluxo do Google. Ver specs/04-cadastro-login.md.
 *
 * A troca do código exige o verifier salvo neste dispositivo quando o reset
 * foi solicitado — um link de terceiros (ex: reset pedido pro e-mail de
 * outra pessoa e reenviado) não tem esse verifier e falha na troca, em vez
 * de logar o usuário na conta errada.
 */
async function handleIncomingUrl(url: string, onRecovery: () => void) {
  if (!url.includes('code=')) return;

  let code: string | null;
  let type: string | null;
  try {
    ({ code, type } = parseAuthCallback(url));
  } catch {
    return;
  }
  if (!code || type !== 'recovery') return;

  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) return;

  onRecovery();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [passwordRecoveryPending, setPasswordRecoveryPending] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setInitializing(false);
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });

    const markRecovery = () => setPasswordRecoveryPending(true);

    Linking.getInitialURL().then((url) => {
      if (url) handleIncomingUrl(url, markRecovery);
    });

    const linkingSubscription = Linking.addEventListener('url', ({ url }) => {
      handleIncomingUrl(url, markRecovery);
    });

    return () => {
      subscription.subscription.unsubscribe();
      linkingSubscription.remove();
    };
  }, []);

  return (
    <AuthContext.Provider
      value={{
        session,
        initializing,
        passwordRecoveryPending,
        clearPasswordRecovery: () => setPasswordRecoveryPending(false),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
