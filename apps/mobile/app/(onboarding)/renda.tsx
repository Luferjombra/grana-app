import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';

import { centsToApiAmount, extractDigits, formatCents, isPositiveAmount } from '../../lib/money';
import { completeOnboarding, type IncomeProfile } from '../../lib/profile';

export default function OnboardingRenda() {
  const { perfil } = useLocalSearchParams<{ perfil: IncomeProfile }>();
  // Guarda centavos como dígitos, nunca float — ver lib/money.ts.
  const [cents, setCents] = useState('');
  const [error, setError] = useState<string | undefined>();
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = isPositiveAmount(cents) && !submitting;

  async function handleSubmit() {
    if (!perfil) {
      setError('Volte e escolha o tipo de renda.');
      return;
    }

    setSubmitting(true);
    setError(undefined);
    try {
      await completeOnboarding(perfil, centsToApiAmount(cents));
      router.replace('/(app)');
    } catch {
      setError('Não foi possível salvar. Tente de novo.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Quanto você recebe por mês?</Text>
      <Text style={styles.subtitle}>Não precisa ser exato, e você pode mudar quando quiser.</Text>

      <View style={styles.field}>
        <Text style={styles.prefix}>R$</Text>
        <TextInput
          style={styles.input}
          placeholder="0,00"
          placeholderTextColor="#5c626b"
          value={formatCents(cents)}
          onChangeText={(text) => setCents(extractDigits(text))}
          keyboardType="number-pad"
          autoFocus
        />
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable
        style={[styles.primaryButton, !canSubmit && styles.buttonDisabled]}
        disabled={!canSubmit}
        onPress={handleSubmit}
      >
        <Text style={styles.primaryButtonText}>Concluir</Text>
      </Pressable>

      <Pressable style={styles.skip} onPress={() => router.replace('/(app)')}>
        <Text style={styles.skipText}>Pular por enquanto</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    padding: 24,
  },
  title: {
    fontSize: 20,
    fontWeight: '500',
  },
  subtitle: {
    fontSize: 13,
    color: '#8a8f98',
    marginTop: 4,
    marginBottom: 24,
  },
  field: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderWidth: 1,
    borderColor: '#262b33',
    borderRadius: 10,
    paddingHorizontal: 12,
  },
  prefix: {
    fontSize: 18,
    color: '#8a8f98',
  },
  input: {
    flex: 1,
    paddingVertical: 14,
    fontSize: 24,
    fontWeight: '500',
  },
  error: {
    color: '#d85a30',
    fontSize: 12,
    marginTop: 8,
  },
  primaryButton: {
    backgroundColor: '#e8a33d',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 24,
  },
  primaryButtonText: {
    color: '#2a1c04',
    fontSize: 14,
    fontWeight: '500',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  skip: {
    paddingVertical: 12,
    alignItems: 'center',
  },
  skipText: {
    fontSize: 12,
    color: '#8a8f98',
  },
});
