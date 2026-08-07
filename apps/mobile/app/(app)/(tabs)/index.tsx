import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';

import { currentMonth, monthName } from '../../../lib/dates';
import {
  BUCKET_LABELS,
  getDashboardSummary,
  HEALTH_COLORS,
  HEALTH_LABELS,
  type DashboardSummary,
} from '../../../lib/dashboard';
import { formatApiAmount } from '../../../lib/money';
import { getNotifications } from '../../../lib/notifications';
import { getProfile, type Profile } from '../../../lib/profile';

export default function Home() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [unread, setUnread] = useState(0);
  const [summaryFailed, setSummaryFailed] = useState(false);

  const month = currentMonth();

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      // Em paralelo, mas independentes: com Promise.all, uma falha em
      // qualquer uma apagava a tela inteira — o badge do sino fora do ar
      // derrubava saldo, buckets e health score junto.
      getProfile()
        .then((data) => {
          if (!cancelled) setProfile(data);
        })
        .catch(() => {});

      getDashboardSummary(month)
        .then((data) => {
          if (cancelled) return;
          setSummary(data);
          setSummaryFailed(false);
        })
        .catch(() => {
          if (!cancelled) setSummaryFailed(true);
        });

      // Badge é acessório: se falhar, some em silêncio em vez de virar erro.
      getNotifications()
        .then((data) => {
          if (!cancelled) setUnread(data.unread_count);
        })
        .catch(() => {
          if (!cancelled) setUnread(0);
        });

      return () => {
        cancelled = true;
      };
    }, [month]),
  );

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.brand}>Grana</Text>
          <Text style={styles.headerSub}>{monthName(month)}</Text>
        </View>
        <Pressable style={styles.bell} onPress={() => router.push('/(app)/notificacoes')}>
          <Text style={styles.bellIcon}>🔔</Text>
          {unread > 0 ? (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{unread > 9 ? '9+' : unread}</Text>
            </View>
          ) : null}
        </Pressable>
      </View>

      {summaryFailed ? (
        <Text style={styles.error}>Não foi possível carregar o resumo do mês.</Text>
      ) : null}

      {profile && !profile.onboarding_complete ? (
        <Pressable style={styles.card} onPress={() => router.push('/(onboarding)/perfil')}>
          <Text style={styles.cardTitle}>Informe sua renda</Text>
          <Text style={styles.cardText}>
            Sem ela não dá pra calcular suas metas de 50-30-20 nem a reserva de emergência.
          </Text>
          <Text style={styles.cardAction}>Configurar agora</Text>
        </Pressable>
      ) : null}

      {summary ? (
        <>
          <View style={styles.flowRow}>
            <View style={styles.flowItem}>
              <Text style={styles.flowLabel}>Entrou</Text>
              <Text style={styles.flowValue}>{formatApiAmount(summary.cash_flow.income)}</Text>
            </View>
            <View style={styles.flowItem}>
              <Text style={styles.flowLabel}>Saiu</Text>
              <Text style={styles.flowValue}>{formatApiAmount(summary.cash_flow.expense)}</Text>
            </View>
            <View style={styles.flowItem}>
              <Text style={styles.flowLabel}>Investido</Text>
              <Text style={styles.flowValue}>{formatApiAmount(summary.cash_flow.saved)}</Text>
            </View>
          </View>

          {summary.health_score ? (
            <View style={styles.health}>
              <Text
                style={[styles.healthScore, { color: HEALTH_COLORS[summary.health_score.label] }]}
              >
                {summary.health_score.score}
              </Text>
              <View>
                <Text style={styles.healthTitle}>Saúde financeira</Text>
                <Text style={styles.healthLabel}>{HEALTH_LABELS[summary.health_score.label]}</Text>
              </View>
            </View>
          ) : null}

          <Text style={styles.sectionTitle}>Regra 50-30-20</Text>
          {summary.buckets.map((bucket) => (
            <View key={bucket.bucket} style={styles.bucket}>
              <View style={styles.bucketRow}>
                <Text style={styles.bucketName}>{BUCKET_LABELS[bucket.bucket]}</Text>
                <Text style={styles.bucketValue}>
                  {formatApiAmount(bucket.spent)}
                  {bucket.target ? ` / ${formatApiAmount(bucket.target)}` : ''}
                </Text>
              </View>
              <ProgressBar spent={bucket.spent} target={bucket.target} />
            </View>
          ))}

          {summary.by_category.length ? (
            <>
              <Text style={styles.sectionTitle}>Onde você gastou</Text>
              {summary.by_category.map((slice) => (
                <View key={slice.category_id ?? 'sem-categoria'} style={styles.bucket}>
                  <View style={styles.bucketRow}>
                    <Text style={styles.bucketName}>{slice.name ?? 'Sem categoria'}</Text>
                    <Text style={styles.bucketValue}>
                      {slice.percentage}% · {formatApiAmount(slice.amount)}
                    </Text>
                  </View>
                  <View style={styles.track}>
                    <View style={[styles.fill, { width: `${clampPercent(slice.percentage)}%` }]} />
                  </View>
                </View>
              ))}
            </>
          ) : null}
        </>
      ) : null}

      <Pressable style={styles.addButton} onPress={() => router.push('/(app)/adicionar')}>
        <Text style={styles.addButtonText}>Adicionar lançamento</Text>
      </Pressable>
    </ScrollView>
  );
}

function ProgressBar({ spent, target }: { spent: string; target: string | null }) {
  if (!target) {
    return <Text style={styles.noTarget}>Sem meta até você informar a renda</Text>;
  }

  const ratio = Number(target) > 0 ? (Number(spent) / Number(target)) * 100 : 0;
  const over = ratio > 100;

  return (
    <View style={styles.track}>
      <View style={[styles.fill, { width: `${Math.min(ratio, 100)}%` }, over && styles.fillOver]} />
    </View>
  );
}

function clampPercent(value: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 0;
  return Math.max(0, Math.min(100, parsed));
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    gap: 14,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  brand: {
    fontSize: 18,
    fontWeight: '500',
  },
  headerSub: {
    fontSize: 11,
    color: '#8a8f98',
  },
  bell: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: '#1f242c',
    alignItems: 'center',
    justifyContent: 'center',
  },
  bellIcon: {
    fontSize: 15,
  },
  badge: {
    position: 'absolute',
    top: -2,
    right: -2,
    minWidth: 16,
    height: 16,
    borderRadius: 8,
    paddingHorizontal: 3,
    backgroundColor: '#e85c4a',
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    color: '#fff',
    fontSize: 9,
    fontWeight: '500',
  },
  error: {
    color: '#d85a30',
    fontSize: 13,
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
  flowRow: {
    flexDirection: 'row',
    gap: 10,
  },
  flowItem: {
    flex: 1,
    backgroundColor: '#1c2028',
    borderRadius: 10,
    padding: 12,
    gap: 2,
  },
  flowLabel: {
    fontSize: 11,
    color: '#8a8f98',
  },
  flowValue: {
    fontSize: 14,
    fontWeight: '500',
  },
  health: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  healthScore: {
    fontSize: 30,
    fontWeight: '500',
  },
  healthTitle: {
    fontSize: 13,
    fontWeight: '500',
  },
  healthLabel: {
    fontSize: 12,
    color: '#8a8f98',
  },
  sectionTitle: {
    fontSize: 11,
    color: '#8a8f98',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginTop: 8,
  },
  bucket: {
    gap: 5,
  },
  bucketRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  bucketName: {
    fontSize: 13,
  },
  bucketValue: {
    fontSize: 12,
    color: '#8a8f98',
  },
  track: {
    height: 6,
    borderRadius: 3,
    backgroundColor: '#1c2028',
    overflow: 'hidden',
  },
  fill: {
    height: 6,
    borderRadius: 3,
    backgroundColor: '#e8a33d',
  },
  fillOver: {
    backgroundColor: '#e85c4a',
  },
  noTarget: {
    fontSize: 11,
    color: '#5c626b',
  },
  addButton: {
    backgroundColor: '#e8a33d',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 12,
  },
  addButtonText: {
    color: '#2a1c04',
    fontSize: 14,
    fontWeight: '500',
  },
});
