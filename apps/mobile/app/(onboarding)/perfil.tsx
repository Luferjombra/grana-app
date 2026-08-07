import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';

import type { IncomeProfile } from '../../lib/profile';

const OPTIONS: { value: IncomeProfile; label: string; hint: string }[] = [
  { value: 'clt', label: 'CLT', hint: 'Renda fixa todo mês. Reserva de 6 meses.' },
  { value: 'autonomo', label: 'Autônomo', hint: 'Renda que varia. Reserva de 12 meses.' },
];

export default function OnboardingPerfil() {
  const [selected, setSelected] = useState<IncomeProfile | null>(null);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Como é a sua renda?</Text>
      <Text style={styles.subtitle}>
        Isso define o tamanho da sua reserva de emergência. Dá pra mudar depois.
      </Text>

      <View style={styles.options}>
        {OPTIONS.map((option) => (
          <Pressable
            key={option.value}
            style={[styles.option, selected === option.value && styles.optionSelected]}
            onPress={() => setSelected(option.value)}
          >
            <Text style={styles.optionLabel}>{option.label}</Text>
            <Text style={styles.optionHint}>{option.hint}</Text>
          </Pressable>
        ))}
      </View>

      <Pressable
        style={[styles.primaryButton, !selected && styles.buttonDisabled]}
        disabled={!selected}
        onPress={() =>
          router.push({ pathname: '/(onboarding)/renda', params: { perfil: selected } })
        }
      >
        <Text style={styles.primaryButtonText}>Continuar</Text>
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
  options: {
    gap: 10,
    marginBottom: 24,
  },
  option: {
    borderWidth: 1,
    borderColor: '#262b33',
    borderRadius: 10,
    padding: 16,
  },
  optionSelected: {
    borderColor: '#e8a33d',
  },
  optionLabel: {
    fontSize: 15,
    fontWeight: '500',
  },
  optionHint: {
    fontSize: 12,
    color: '#8a8f98',
    marginTop: 4,
  },
  primaryButton: {
    backgroundColor: '#e8a33d',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
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
