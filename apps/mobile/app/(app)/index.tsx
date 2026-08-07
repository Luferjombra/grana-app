import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';

import { formatApiAmount } from '../../lib/money';
import { getProfile, type Profile } from '../../lib/profile';

export default function Home() {
  const [profile, setProfile] = useState<Profile | null>(null);

  // Busca a cada foco (inclusive o primeiro): ao voltar do onboarding o card
  // de "informe sua renda" precisa sumir. Buscar direto aqui, em vez de por
  // um contador que alimenta um useEffect, evita duas chamadas por entrada.
  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      getProfile()
        .then((data) => {
          if (!cancelled) setProfile(data);
        })
        .catch(() => {
          if (!cancelled) setProfile(null);
        });
      return () => {
        cancelled = true;
      };
    }, []),
  );

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Grana</Text>

      {profile && !profile.onboarding_complete ? (
        <Pressable style={styles.card} onPress={() => router.push('/(onboarding)/perfil')}>
          <Text style={styles.cardTitle}>Informe sua renda</Text>
          <Text style={styles.cardText}>
            Sem ela não dá pra calcular suas metas de 50-30-20 nem a reserva de emergência.
          </Text>
          <Text style={styles.cardAction}>Configurar agora</Text>
        </Pressable>
      ) : null}

      {profile?.current_income ? (
        <View style={styles.summary}>
          <Text style={styles.summaryLabel}>Renda do mês</Text>
          <Text style={styles.summaryValue}>{formatApiAmount(profile.current_income)}</Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 24,
    gap: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: '500',
  },
  card: {
    borderWidth: 1,
    borderColor: '#e8a33d',
    borderRadius: 12,
    padding: 16,
    gap: 6,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '500',
  },
  cardText: {
    fontSize: 13,
    color: '#8a8f98',
    lineHeight: 18,
  },
  cardAction: {
    fontSize: 13,
    color: '#e8a33d',
    fontWeight: '500',
    marginTop: 4,
  },
  summary: {
    gap: 4,
  },
  summaryLabel: {
    fontSize: 13,
    color: '#8a8f98',
  },
  summaryValue: {
    fontSize: 24,
    fontWeight: '500',
  },
});
