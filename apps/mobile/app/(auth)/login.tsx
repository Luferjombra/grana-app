import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Link } from 'expo-router';

import { signInWithEmail, signInWithGoogle } from '../../lib/auth';

type FieldErrors = {
  email?: string;
  password?: string;
  form?: string;
};

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  function validate(): boolean {
    const next: FieldErrors = {};
    if (!email.trim()) next.email = 'Informe seu e-mail.';
    if (!password) next.password = 'Informe sua senha.';
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleLogin() {
    if (!validate()) return;

    setSubmitting(true);
    setErrors({});
    try {
      await signInWithEmail(email.trim(), password);
    } catch (error) {
      setErrors({ form: mapSignInError(error) });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogle() {
    setSubmitting(true);
    setErrors({});
    try {
      await signInWithGoogle();
    } catch {
      setErrors({ form: 'Não foi possível continuar com o Google. Tente de novo.' });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Entrar</Text>
      <Text style={styles.subtitle}>Bem-vindo de volta.</Text>

      <Pressable
        style={[styles.socialButton, submitting && styles.buttonDisabled]}
        onPress={handleGoogle}
        disabled={submitting}
      >
        <Text style={styles.socialButtonText}>Continuar com Google</Text>
      </Pressable>

      <View style={styles.divider}>
        <View style={styles.dividerLine} />
        <Text style={styles.dividerText}>ou com e-mail</Text>
        <View style={styles.dividerLine} />
      </View>

      <TextInput
        style={styles.input}
        placeholder="nome@email.com"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
      />
      {errors.email ? <Text style={styles.fieldError}>{errors.email}</Text> : null}

      <TextInput
        style={styles.input}
        placeholder="Sua senha"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />
      {errors.password ? <Text style={styles.fieldError}>{errors.password}</Text> : null}

      {errors.form ? <Text style={styles.formError}>{errors.form}</Text> : null}

      <Pressable
        style={[styles.primaryButton, submitting && styles.buttonDisabled]}
        onPress={handleLogin}
        disabled={submitting}
      >
        <Text style={styles.primaryButtonText}>Entrar</Text>
      </Pressable>

      <Link href="/(auth)/esqueci-senha" style={styles.secondaryLink}>
        Esqueci minha senha
      </Link>
      <Link href="/(auth)/cadastro" style={styles.secondaryLink}>
        Não tenho conta · Criar conta
      </Link>
    </ScrollView>
  );
}

function mapSignInError(error: unknown): string {
  const message = error instanceof Error ? error.message : '';
  if (message.includes('Invalid login credentials')) return 'E-mail ou senha incorretos.';
  return 'Não foi possível entrar. Tente de novo.';
}

const styles = StyleSheet.create({
  container: {
    padding: 24,
    gap: 4,
  },
  title: {
    fontSize: 20,
    fontWeight: '500',
  },
  subtitle: {
    fontSize: 13,
    color: '#8a8f98',
    marginBottom: 20,
  },
  socialButton: {
    backgroundColor: '#1c2028',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    marginBottom: 16,
  },
  socialButtonText: {
    color: '#eef0f3',
    fontSize: 14,
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 16,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#262b33',
  },
  dividerText: {
    fontSize: 11,
    color: '#8a8f98',
  },
  input: {
    borderWidth: 1,
    borderColor: '#262b33',
    borderRadius: 10,
    paddingVertical: 11,
    paddingHorizontal: 12,
    fontSize: 14,
    marginBottom: 4,
  },
  fieldError: {
    color: '#d85a30',
    fontSize: 12,
    marginBottom: 8,
  },
  formError: {
    color: '#d85a30',
    fontSize: 13,
    marginBottom: 12,
    textAlign: 'center',
  },
  primaryButton: {
    backgroundColor: '#e8a33d',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 8,
    marginBottom: 10,
  },
  primaryButtonText: {
    color: '#2a1c04',
    fontSize: 14,
    fontWeight: '500',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  secondaryLink: {
    textAlign: 'center',
    fontSize: 12,
    color: '#8a8f98',
    paddingVertical: 6,
  },
});
