import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Link } from 'expo-router';

import { requestPasswordReset } from '../../lib/auth';

export default function EsqueciSenha() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | undefined>();
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit() {
    if (!email.trim()) {
      setError('Informe seu e-mail.');
      return;
    }

    setSubmitting(true);
    setError(undefined);
    try {
      await requestPasswordReset(email.trim());
      setSent(true);
    } catch {
      setError('Não foi possível enviar o e-mail. Tente de novo.');
    } finally {
      setSubmitting(false);
    }
  }

  if (sent) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Confira seu e-mail</Text>
        <Text style={styles.subtitle}>
          Enviamos um link pra redefinir sua senha pra {email.trim()}.
        </Text>
        <Link href="/(auth)/login" style={styles.secondaryLink}>
          Voltar pro login
        </Link>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Esqueci minha senha</Text>
      <Text style={styles.subtitle}>
        Informe o e-mail da sua conta e enviamos um link de redefinição.
      </Text>

      <TextInput
        style={styles.input}
        placeholder="nome@email.com"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
      />
      {error ? <Text style={styles.fieldError}>{error}</Text> : null}

      <Pressable
        style={[styles.primaryButton, submitting && styles.buttonDisabled]}
        onPress={handleSubmit}
        disabled={submitting}
      >
        <Text style={styles.primaryButtonText}>Enviar link de redefinição</Text>
      </Pressable>

      <Link href="/(auth)/login" style={styles.secondaryLink}>
        Voltar pro login
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
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
