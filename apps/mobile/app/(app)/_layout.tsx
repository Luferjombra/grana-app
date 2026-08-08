import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Stack } from 'expo-router';

import { supabase } from '../../lib/supabase';
import { useAuth } from '../../lib/auth-context';

type ProfileCheck = 'checking' | 'ok' | 'missing';

/**
 * Se o trigger on_auth_user_created falhar, auth.users é criado mas profiles
 * fica órfão. Antes de renderizar qualquer tela autenticada, confirma que o
 * profile existe — sem essa checagem, o app quebraria em cascata em toda
 * chamada que dependa de household_id. Ver specs/04-cadastro-login.md.
 */
export default function AppLayout() {
  const { session } = useAuth();
  const [status, setStatus] = useState<ProfileCheck>('checking');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;

    supabase
      .from('profiles')
      .select('id')
      .eq('id', session.user.id)
      .maybeSingle()
      .then(({ data }) => {
        if (!cancelled) setStatus(data ? 'ok' : 'missing');
      });

    return () => {
      cancelled = true;
    };
  }, [session, attempt]);

  if (status === 'checking') return null;

  if (status === 'missing') {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Algo deu errado</Text>
        <Text style={styles.subtitle}>
          Não conseguimos carregar sua conta. Tente de novo ou entre em contato com o suporte.
        </Text>
        <Pressable
          style={styles.button}
          onPress={() => {
            setStatus('checking');
            setAttempt((value) => value + 1);
          }}
        >
          <Text style={styles.buttonText}>Tentar de novo</Text>
        </Pressable>
        <Pressable style={styles.secondaryButton} onPress={() => supabase.auth.signOut()}>
          <Text style={styles.secondaryButtonText}>Sair</Text>
        </Pressable>
      </View>
    );
  }

  // As abas ficam dentro deste Stack; adicionar e notificações são empurradas
  // por cima delas, não são abas.
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="adicionar" options={{ presentation: 'modal' }} />
      <Stack.Screen name="recibo" options={{ presentation: 'modal' }} />
      <Stack.Screen name="importar" />
      <Stack.Screen name="notificacoes" />
    </Stack>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 24,
  },
  title: {
    fontSize: 20,
    fontWeight: '500',
  },
  subtitle: {
    fontSize: 13,
    color: '#8a8f98',
    textAlign: 'center',
    marginBottom: 12,
  },
  button: {
    backgroundColor: '#e8a33d',
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 24,
    alignItems: 'center',
  },
  buttonText: {
    color: '#2a1c04',
    fontSize: 14,
    fontWeight: '500',
  },
  secondaryButton: {
    paddingVertical: 10,
  },
  secondaryButtonText: {
    fontSize: 13,
    color: '#8a8f98',
  },
});
