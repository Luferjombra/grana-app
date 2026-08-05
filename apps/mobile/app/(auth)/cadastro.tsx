import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { Link } from 'expo-router';

import { signInWithGoogle, signUpWithEmail } from '../../lib/auth';

type FieldErrors = {
  fullName?: string;
  email?: string;
  password?: string;
  form?: string;
};

export default function Cadastro() {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  function validate(): boolean {
    const next: FieldErrors = {};
    if (!fullName.trim()) next.fullName = 'Informe seu nome.';
    if (!email.trim()) next.email = 'Informe seu e-mail.';
    if (password.length < 6) next.password = 'A senha precisa ter pelo menos 6 caracteres.';
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleCreateAccount() {
    if (!validate()) return;

    setSubmitting(true);
    setErrors({});
    try {
      await signUpWithEmail(fullName.trim(), email.trim(), password);
    } catch (error) {
      setErrors({ form: mapSignUpError(error) });
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

  const canSubmit = termsAccepted && !submitting;

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Crie sua conta grátis</Text>
      <Text style={styles.subtitle}>Leva menos de um minuto. Sem cartão, sem compromisso.</Text>

      <Pressable
        style={[styles.socialButton, !canSubmit && styles.buttonDisabled]}
        onPress={handleGoogle}
        disabled={!canSubmit}
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
        placeholder="Seu nome"
        value={fullName}
        onChangeText={setFullName}
        autoCapitalize="words"
      />
      {errors.fullName ? <Text style={styles.fieldError}>{errors.fullName}</Text> : null}

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
        placeholder="Crie uma senha"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />
      {errors.password ? <Text style={styles.fieldError}>{errors.password}</Text> : null}

      <Pressable style={styles.consentRow} onPress={() => setTermsAccepted((v) => !v)}>
        <Switch value={termsAccepted} onValueChange={setTermsAccepted} />
        <Text style={styles.consentText}>
          {/* TODO: texto pendente de revisão jurídica antes de produção (specs/04) */}
          Aceito os termos de uso e a política de privacidade, e autorizo o processamento dos meus
          dados financeiros pra gerar os insights do app.
        </Text>
      </Pressable>

      {errors.form ? <Text style={styles.formError}>{errors.form}</Text> : null}

      <Pressable
        style={[styles.primaryButton, !canSubmit && styles.buttonDisabled]}
        onPress={handleCreateAccount}
        disabled={!canSubmit}
      >
        <Text style={styles.primaryButtonText}>Criar minha conta</Text>
      </Pressable>

      <Link href="/(auth)/login" style={styles.loginLink}>
        Já tenho conta · Entrar
      </Link>
    </ScrollView>
  );
}

function mapSignUpError(error: unknown): string {
  const message = error instanceof Error ? error.message : '';
  if (message.includes('already registered')) return 'Este e-mail já está cadastrado.';
  return 'Não foi possível criar sua conta. Tente de novo.';
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
  consentRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    marginVertical: 16,
  },
  consentText: {
    flex: 1,
    fontSize: 11,
    color: '#8a8f98',
    lineHeight: 16,
  },
  primaryButton: {
    backgroundColor: '#e8a33d',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
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
  loginLink: {
    textAlign: 'center',
    fontSize: 12,
    color: '#8a8f98',
    paddingVertical: 6,
  },
});
