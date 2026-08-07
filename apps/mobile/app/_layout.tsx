import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { AuthProvider, useAuth } from '../lib/auth-context';

function RootNavigator() {
  const { session, initializing, passwordRecoveryPending } = useAuth();

  if (initializing) return null;

  return (
    <Stack screenOptions={{ headerShown: false }}>
      {/* Sessão de recuperação (deep link de "esqueci minha senha") tem
          prioridade sobre as demais — mesmo com sessão válida, o usuário
          precisa definir a nova senha antes de entrar no app. */}
      <Stack.Protected guard={passwordRecoveryPending}>
        <Stack.Screen name="(auth)/redefinir-senha" />
      </Stack.Protected>
      <Stack.Protected guard={!passwordRecoveryPending && !!session}>
        <Stack.Screen name="(app)" />
        {/* Onboarding de dados é pulável (specs/10), então fica no mesmo
            grupo autenticado em vez de barrar a entrada no app. */}
        <Stack.Screen name="(onboarding)/perfil" />
        <Stack.Screen name="(onboarding)/renda" />
      </Stack.Protected>
      <Stack.Protected guard={!passwordRecoveryPending && !session}>
        <Stack.Screen name="(auth)/cadastro" />
        <Stack.Screen name="(auth)/login" />
        <Stack.Screen name="(auth)/esqueci-senha" />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootNavigator />
      <StatusBar style="auto" />
    </AuthProvider>
  );
}
