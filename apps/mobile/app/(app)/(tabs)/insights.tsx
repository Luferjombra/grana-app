import { useCallback, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from 'expo-router';

import { currentMonth, formatShortDate, monthName, parseIsoDate } from '../../../lib/dates';
import { HEALTH_COLORS, HEALTH_LABELS } from '../../../lib/dashboard';
import {
  getHealthBreakdown,
  getMonthOverMonth,
  getSubscriptions,
  getThreeMonthAverage,
  getTopTransactions,
  type Delta,
  type HealthBreakdown,
  type MonthOverMonth,
  type Subscriptions,
  type ThreeMonthAverage,
  type TopTransactions,
} from '../../../lib/insights';
import { deltaText, overshoot, shortMonths } from '../../../lib/insights-format';
import { formatApiAmount } from '../../../lib/money';

export default function Insights() {
  const [mom, setMom] = useState<MonthOverMonth | null>(null);
  const [subs, setSubs] = useState<Subscriptions | null>(null);
  const [top, setTop] = useState<TopTransactions | null>(null);
  const [average, setAverage] = useState<ThreeMonthAverage | null>(null);
  const [health, setHealth] = useState<HealthBreakdown | null>(null);
  const [failed, setFailed] = useState(0);

  const month = currentMonth();

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      setFailed(0);

      // Cinco chamadas independentes, sem Promise.all: são cinco leituras
      // separadas, e uma falha isolada não pode apagar as outras quatro
      // seções — mesma lição da Home.
      const load = <T,>(request: Promise<T>, set: (value: T) => void) =>
        request
          .then((data) => {
            if (!cancelled) set(data);
          })
          .catch(() => {
            if (!cancelled) setFailed((count) => count + 1);
          });

      load(getMonthOverMonth(month), setMom);
      load(getSubscriptions(), setSubs);
      load(getTopTransactions(month), setTop);
      load(getThreeMonthAverage(), setAverage);
      load(getHealthBreakdown(month), setHealth);

      return () => {
        cancelled = true;
      };
    }, [month]),
  );

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.brand}>Insights</Text>
          <Text style={styles.headerSub}>
            {monthName(month)}
            {mom?.comparable_days ? ` · dia ${mom.comparable_days}` : ''}
          </Text>
        </View>
        {mom?.partial ? (
          <View style={styles.tag}>
            <Text style={styles.tagText}>parcial</Text>
          </View>
        ) : null}
      </View>

      {failed === 5 ? (
        <Text style={styles.error}>Não foi possível carregar os insights.</Text>
      ) : null}

      {/* ---------------------------------------------------- mês a mês */}
      {mom ? (
        <>
          {/* O backend corta os dois meses no mesmo dia justamente pra não
              anunciar economia falsa. Se a tela não disser isso, o cuidado do
              backend morre aqui. */}
          {mom.partial && mom.comparable_days ? (
            <View style={styles.warn}>
              <Text style={styles.warnText}>
                {monthName(mom.month)} ainda está em curso, então a comparação usa os{' '}
                <Text style={styles.warnStrong}>{mom.comparable_days} primeiros dias</Text> de cada
                mês. Nada aqui é o fechamento.
              </Text>
            </View>
          ) : null}

          <Text style={styles.section}>Mês a mês</Text>
          <View style={styles.card}>
            <Text style={styles.label}>
              {mom.partial ? `Gasto até o dia ${mom.comparable_days}` : 'Gasto no mês'}
            </Text>
            <Text style={styles.big}>{formatApiAmount(mom.total.current)}</Text>
            <Text style={[styles.deltaLine, tone(mom.total.direction)]}>
              {deltaText(mom.total)} · vs {monthName(mom.previous_month)}
            </Text>
          </View>

          {mom.by_category.length > 0 ? (
            <View style={styles.card}>
              {/* Já vem ordenado por variação em reais: não reordenar. */}
              {mom.by_category.slice(0, 6).map((entry) => (
                <View key={`${entry.category_id ?? 'none'}`} style={styles.row}>
                  <View style={styles.rowMain}>
                    <Text style={styles.rowName}>{entry.name}</Text>
                    <Text style={styles.rowMeta}>
                      {formatApiAmount(entry.previous)} → {formatApiAmount(entry.current)}
                    </Text>
                  </View>
                  <Text style={[styles.rowValue, tone(entry.direction)]}>{deltaText(entry)}</Text>
                </View>
              ))}
            </View>
          ) : null}

          <Text style={styles.note}>
            Ordenado pelo que mais mudou em reais, não em porcentagem: 200% de aumento num gasto de
            R$ 3 não é notícia.
          </Text>
        </>
      ) : null}

      {/* ------------------------------------------------ média de 3 meses */}
      {average?.average_total ? (
        <>
          <Text style={styles.section}>Média dos últimos meses</Text>
          <View style={styles.card}>
            <Text style={styles.label}>Média mensal</Text>
            <Text style={styles.big}>{formatApiAmount(average.average_total)}</Text>
            <Text style={styles.rowMeta}>
              {shortMonths(average.months_used, monthName)}
              {' · '}
              {average.months_used.length}{' '}
              {average.months_used.length === 1 ? 'mês fechado' : 'meses fechados'}
            </Text>

            <View style={styles.divider} />
            {average.by_bucket.map((entry) => (
              <View key={entry.bucket} style={styles.row}>
                <Text style={styles.rowName}>{entry.label}</Text>
                <Text style={styles.rowValue}>{formatApiAmount(entry.average)}</Text>
              </View>
            ))}
          </View>
          <Text style={styles.note}>
            Mês sem lançamento nenhum fica fora da média — quase sempre significa &quot;não
            registrei&quot;, não &quot;não gastei&quot;.
          </Text>
        </>
      ) : null}

      {/* -------------------------------------------------- custo recorrente */}
      {subs && subs.items.length > 0 ? (
        <>
          <Text style={styles.section}>Custo fixo recorrente</Text>
          <View style={styles.card}>
            <Text style={styles.label}>Por mês, hoje</Text>
            <Text style={styles.big}>{formatApiAmount(subs.monthly_total)}</Text>

            <View style={styles.divider} />
            {subs.items
              .filter((item) => item.active)
              .map((item) => (
                <View key={item.merchant_key} style={styles.row}>
                  <View style={styles.rowMain}>
                    <Text style={styles.rowName} numberOfLines={1}>
                      {item.label}
                    </Text>
                    <Text style={styles.rowMeta}>
                      {item.category?.name ? `${item.category.name} · ` : ''}
                      visto em {item.months_seen} meses
                    </Text>
                  </View>
                  <Text style={styles.rowValue}>{formatApiAmount(item.amount)}</Text>
                </View>
              ))}

            {/* Cancelada continuaria "ativa" na tela e inflaria o custo fixo. */}
            {subs.items.some((item) => !item.active) ? (
              <>
                <View style={styles.divider} />
                <Text style={styles.label}>Pararam de aparecer</Text>
                {subs.items
                  .filter((item) => !item.active)
                  .map((item) => (
                    <View key={item.merchant_key} style={styles.row}>
                      <View style={styles.rowMain}>
                        <Text style={[styles.rowName, styles.muted]} numberOfLines={1}>
                          {item.label}
                        </Text>
                        <Text style={styles.rowMeta}>
                          último em {formatShortDate(parseIsoDate(item.last_seen) ?? new Date())}
                        </Text>
                      </View>
                      <Text style={[styles.rowValue, styles.muted]}>
                        {formatApiAmount(item.amount)}
                      </Text>
                    </View>
                  ))}
              </>
            ) : null}
          </View>
          <Text style={styles.note}>
            Detectado do seu extrato: mesmo comerciante, valor estável, {subs.months_analyzed} meses
            analisados. O que parou de cobrar sai do total.
          </Text>
        </>
      ) : null}

      {/* ------------------------------------------------- maiores gastos */}
      {top && top.items.length > 0 ? (
        <>
          <Text style={styles.section}>Maiores gastos de {monthName(top.month)}</Text>
          <View style={styles.card}>
            {top.items.map((item, index) => (
              <View key={item.id} style={styles.row}>
                <Text style={styles.rank}>{index + 1}</Text>
                <View style={styles.rowMain}>
                  {/* merchant vem null quando o extrato veio sem descrição.
                      Linha em branco no "maiores gastos" seria o pior lugar
                      possível pra isso aparecer. */}
                  <Text
                    style={[styles.rowName, !item.merchant && styles.noDescription]}
                    numberOfLines={1}
                  >
                    {item.merchant || 'Lançamento sem descrição'}
                  </Text>
                  <Text style={styles.rowMeta}>
                    {item.category?.name ?? 'sem categoria'} ·{' '}
                    {formatShortDate(parseIsoDate(item.occurred_at) ?? new Date())}
                  </Text>
                </View>
                <Text style={styles.rowValue}>{formatApiAmount(item.amount)}</Text>
              </View>
            ))}
          </View>
          {Number(top.excluded_savings) > 0 ? (
            <Text style={styles.note}>
              Aporte em poupança fica fora: {formatApiAmount(top.excluded_savings)} investidos neste
              mês não são gasto, e apareceriam no topo da lista.
            </Text>
          ) : null}
        </>
      ) : null}

      {/* ------------------------------------------------------ health score */}
      {health ? (
        <>
          <Text style={styles.section}>Sua nota do mês</Text>
          <View style={styles.card}>
            {health.score === null ? (
              // Sem renda não existe teto, e sem teto não há aderência a medir.
              // Explica, em vez de mostrar erro ou um zero que pareceria nota.
              <Text style={styles.subtitle}>
                Sem renda informada neste mês não há teto pra comparar, então não existe nota.
                Informe sua renda no início pra ver este número.
              </Text>
            ) : (
              <>
                <View style={styles.scoreRow}>
                  <Text style={[styles.score, { color: HEALTH_COLORS[health.label ?? 'risco'] }]}>
                    {health.score}
                  </Text>
                  <View style={styles.scoreSide}>
                    <View
                      style={[
                        styles.tag,
                        { backgroundColor: HEALTH_COLORS[health.label ?? 'risco'] },
                      ]}
                    >
                      <Text style={styles.tagText}>{HEALTH_LABELS[health.label ?? 'risco']}</Text>
                    </View>
                    <Text style={styles.rowMeta}>
                      Média por bucket, com o peso dos seus 50-30-20
                    </Text>
                  </View>
                </View>

                <View style={styles.divider} />
                {health.breakdown.map((entry) => (
                  <View key={entry.bucket} style={styles.row}>
                    <View style={styles.rowMain}>
                      <View style={styles.nameLine}>
                        <Text style={styles.rowName}>{entry.label}</Text>
                        <Text style={styles.kind}>{entry.kind === 'goal' ? 'meta' : 'teto'}</Text>
                      </View>
                      <Text style={styles.rowMeta}>
                        {formatApiAmount(entry.spent)} de {formatApiAmount(entry.target)}
                        {overshoot(entry) ? ` · ${overshoot(entry)}` : ''}
                      </Text>
                    </View>
                    <View style={styles.scoreCell}>
                      <Text style={styles.rowValue}>{entry.score}</Text>
                      <Text style={styles.rowMeta}>
                        peso {Math.round(Number(entry.weight_pct))}%
                      </Text>
                    </View>
                  </View>
                ))}
              </>
            )}

            {Number(health.uncategorized_expense) > 0 ? (
              <View style={[styles.row, styles.rowTop]}>
                <View style={styles.rowMain}>
                  <Text style={[styles.rowName, styles.muted]}>Sem categoria</Text>
                  <Text style={styles.rowMeta}>
                    não entra em bucket nenhum, então não pontua nem pune
                  </Text>
                </View>
                <Text style={[styles.rowValue, styles.muted]}>
                  {formatApiAmount(health.uncategorized_expense)}
                </Text>
              </View>
            ) : null}
          </View>
        </>
      ) : null}
    </ScrollView>
  );
}

function tone(direction: Delta['direction']) {
  if (direction === 'up') return styles.up;
  if (direction === 'down') return styles.down;
  return styles.flat;
}

const styles = StyleSheet.create({
  container: { backgroundColor: '#14171c', paddingHorizontal: 18, paddingBottom: 40, flexGrow: 1 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingTop: 52,
    paddingBottom: 6,
  },
  brand: { color: '#eef0f3', fontSize: 16, fontWeight: '500' },
  headerSub: { color: '#8a8f98', fontSize: 11, marginTop: 2 },

  section: {
    color: '#5c626b',
    fontSize: 10,
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginTop: 20,
    marginBottom: 8,
  },
  card: { backgroundColor: '#1c2028', borderRadius: 12, padding: 13, marginBottom: 8 },
  label: { color: '#8a8f98', fontSize: 10.5 },
  big: { color: '#eef0f3', fontSize: 25, fontWeight: '500' },
  subtitle: { color: '#8a8f98', fontSize: 12.5, lineHeight: 19 },
  note: { color: '#5c626b', fontSize: 10.5, lineHeight: 16 },
  error: { color: '#d85a30', fontSize: 12.5, marginTop: 16 },
  divider: { height: 1, backgroundColor: '#262b33', marginVertical: 10 },

  deltaLine: { fontSize: 11.5, marginTop: 3 },
  up: { color: '#d85a30' },
  down: { color: '#5dcaa5' },
  flat: { color: '#8a8f98' },

  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#22272f',
  },
  rowTop: { borderBottomWidth: 0, borderTopWidth: 1, borderTopColor: '#262b33' },
  rowMain: { flex: 1, minWidth: 0 },
  rowName: { color: '#eef0f3', fontSize: 12.5 },
  rowMeta: { color: '#5c626b', fontSize: 10, marginTop: 1 },
  rowValue: { color: '#eef0f3', fontSize: 12.5 },
  muted: { color: '#8a8f98' },
  noDescription: { color: '#5c626b', fontStyle: 'italic' },
  rank: { color: '#5c626b', fontSize: 11, width: 14 },
  nameLine: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  kind: {
    color: '#5c626b',
    fontSize: 9,
    borderWidth: 1,
    borderColor: '#262b33',
    borderRadius: 8,
    paddingHorizontal: 5,
    paddingVertical: 1,
  },
  scoreCell: { alignItems: 'flex-end' },

  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  score: { fontSize: 30, fontWeight: '500' },
  scoreSide: { flex: 1, gap: 6 },

  tag: {
    backgroundColor: '#e8a33d',
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 2,
    alignSelf: 'flex-start',
  },
  tagText: { color: '#2a1c04', fontSize: 10 },

  warn: {
    backgroundColor: '#221d14',
    borderColor: '#3d3320',
    borderWidth: 1,
    borderRadius: 10,
    padding: 11,
    marginTop: 12,
  },
  warnText: { color: '#e0c79a', fontSize: 11, lineHeight: 17 },
  warnStrong: { color: '#e8a33d', fontWeight: '500' },
});
