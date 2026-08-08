import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { router, useFocusEffect } from 'expo-router';

import { currentMonth, monthName } from '../../../lib/dates';
import { getDashboardSummary, type BucketProgress } from '../../../lib/dashboard';
import {
  centsToApiAmount,
  extractDigits,
  formatApiAmount,
  formatCents,
  hasAmount,
  isPositiveAmount,
  numberToCents,
} from '../../../lib/money';
import { getReserve, PROFILE_LABELS, updateReserve, type Reserve } from '../../../lib/reserve';

/**
 * Aba Metas.
 *
 * Nasce com a **reserva de emergência** e a **meta de poupança do mês**, não com
 * gamificação. A aba nunca precisou da regra de XP — precisava de uma meta, e a
 * reserva já era uma: tem alvo, progresso e prazo implícito. XP, nível e
 * conquistas entram como segunda seção quando a regra for decidida, com a aba já
 * existindo e tendo tráfego, em vez de estrear vazia.
 *
 * Antes disso, a reserva era criada no onboarding e **nunca mais aparecia em tela
 * nenhuma** — e o alerta de marco ("3 meses de reserva") não tinha destino.
 */
type Editing = 'none' | 'balance' | 'saving';

export default function Metas() {
  const [reserve, setReserve] = useState<Reserve | null>(null);
  const [savings, setSavings] = useState<BucketProgress | null>(null);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [editing, setEditing] = useState<Editing>('none');
  const [digits, setDigits] = useState('');
  const [error, setError] = useState<string | undefined>();

  const month = currentMonth();

  const load = useCallback(() => {
    let cancelled = false;

    // Independentes, sem Promise.all: a meta de poupança não pode desaparecer
    // porque a reserva falhou, nem o contrário.
    getReserve()
      .then((data) => {
        if (cancelled) return;
        setReserve(data);
        setNeedsOnboarding(false);
      })
      .catch((problem: unknown) => {
        if (cancelled) return;
        // 404 significa que o onboarding não foi concluído: a reserva nasce lá.
        // Levar de volta é a saída; mostrar erro seria um beco.
        const missing = problem instanceof Error && problem.message.includes('404');
        setNeedsOnboarding(missing);
        if (!missing) setError('Não foi possível carregar sua reserva.');
      });

    getDashboardSummary(month)
      .then((data) => {
        if (cancelled) return;
        setSavings(data.buckets.find((b) => b.bucket === 'poupanca') ?? null);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [month]);

  useFocusEffect(load);

  function startEditing(mode: Exclude<Editing, 'none'>) {
    if (!reserve) return;
    setError(undefined);
    setEditing(mode);
    // Abre com o valor atual, pra corrigir ser mais fácil que redigitar.
    setDigits(
      mode === 'balance'
        ? numberToCents(Number(reserve.current_balance))
        : numberToCents(Number(reserve.essential_expenses_baseline)),
    );
  }

  /** Saldo pode ser zero ("gastei minha reserva"); gasto essencial não, porque
   *  zerar o baseline zeraria a meta e diria "reserva completa" com nada. */
  const canSave =
    editing === 'balance' ? hasAmount(digits) : editing === 'saving' && isPositiveAmount(digits);

  async function save() {
    if (!reserve || editing === 'none' || !canSave) return;

    const amount = centsToApiAmount(digits);
    const mode = editing;
    setEditing('none');

    try {
      const updated = await updateReserve(
        mode === 'balance' ? { current_balance: amount } : { essential_expenses_baseline: amount },
      );
      setReserve(updated);
      setError(undefined);
    } catch {
      setError('Não foi possível salvar. Tente de novo.');
      setEditing(mode);
    }
  }

  async function adoptSuggestion() {
    if (!reserve?.suggested_baseline) return;
    try {
      setReserve(
        await updateReserve({
          essential_expenses_baseline: reserve.suggested_baseline.amount,
        }),
      );
    } catch {
      setError('Não foi possível atualizar a meta.');
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <Text style={styles.brand}>Metas</Text>
        <Text style={styles.headerSub}>{monthName(month)}</Text>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {needsOnboarding ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Sua reserva ainda não tem meta</Text>
          <Text style={styles.subtitle}>
            Ela é calculada a partir do seu gasto essencial e do tipo de renda. Leva um minuto.
          </Text>
          <Pressable style={styles.cta} onPress={() => router.push('/(onboarding)/perfil')}>
            <Text style={styles.ctaText}>Configurar agora</Text>
          </Pressable>
        </View>
      ) : null}

      {/* -------------------------------------------- reserva de emergência */}
      {reserve ? (
        <>
          <Text style={styles.section}>Reserva de emergência</Text>
          <View style={styles.card}>
            <Text style={styles.label}>Você tem hoje</Text>
            <Text style={styles.big}>{formatApiAmount(reserve.current_balance)}</Text>

            {reserve.months_covered ? (
              <Text style={styles.covered}>
                {/* "3,5 meses de vida" diz mais que "58%". Ponto vira vírgula:
                    o backend devolve decimal, a tela é em português. */}
                cobre {reserve.months_covered.replace('.', ',')} de {reserve.months_multiplier}{' '}
                meses do seu essencial
              </Text>
            ) : null}

            <View style={styles.track}>
              <View
                style={[
                  styles.fill,
                  { width: `${reserve.progress_pct}%` },
                  reserve.complete && styles.fillDone,
                ]}
              />
            </View>
            <View style={styles.trackLine}>
              <Text style={styles.trackText}>{reserve.progress_pct}% da meta</Text>
              <Text style={styles.trackText}>
                {reserve.complete ? 'meta atingida' : `faltam ${formatApiAmount(reserve.missing)}`}
              </Text>
            </View>

            {editing === 'balance' ? (
              <View style={styles.editBox}>
                <Text style={styles.label}>Quanto você tem guardado hoje</Text>
                <TextInput
                  style={styles.input}
                  value={formatCents(digits)}
                  onChangeText={(text) => setDigits(extractDigits(text))}
                  keyboardType="number-pad"
                  autoFocus
                  placeholder="0,00"
                  placeholderTextColor="#5c626b"
                />
                <View style={styles.editRow}>
                  <Pressable style={styles.ghost} onPress={() => setEditing('none')}>
                    <Text style={styles.ghostText}>Cancelar</Text>
                  </Pressable>
                  <Pressable
                    style={[styles.cta, styles.ctaInline, !canSave && styles.ctaOff]}
                    disabled={!canSave}
                    onPress={save}
                  >
                    <Text style={styles.ctaText}>Salvar</Text>
                  </Pressable>
                </View>
              </View>
            ) : (
              <Pressable style={styles.ghost} onPress={() => startEditing('balance')}>
                <Text style={styles.ghostText}>Informar novo saldo</Text>
              </Pressable>
            )}
          </View>

          {/* A conta do alvo, aberta: o número não pode parecer arbitrário. */}
          <View style={styles.card}>
            <View style={styles.row}>
              <View style={styles.rowMain}>
                <Text style={styles.rowName}>Gasto essencial por mês</Text>
                <Text style={styles.rowMeta}>o que você não consegue cortar</Text>
              </View>
              <Pressable onPress={() => startEditing('saving')}>
                <Text style={styles.rowEdit}>
                  {formatApiAmount(reserve.essential_expenses_baseline)}
                </Text>
              </Pressable>
            </View>
            <View style={styles.row}>
              <View style={styles.rowMain}>
                <Text style={styles.rowName}>Meses de colchão</Text>
                <Text style={styles.rowMeta}>perfil {PROFILE_LABELS[reserve.profile]}</Text>
              </View>
              <Text style={styles.rowValue}>{reserve.months_multiplier}</Text>
            </View>
            <View style={[styles.row, styles.rowLast]}>
              <Text style={styles.rowName}>Meta</Text>
              <Text style={styles.rowValue}>{formatApiAmount(reserve.target)}</Text>
            </View>
          </View>

          {editing === 'saving' ? (
            <View style={styles.card}>
              <Text style={styles.label}>Seu gasto essencial por mês</Text>
              <TextInput
                style={styles.input}
                value={formatCents(digits)}
                onChangeText={(text) => setDigits(extractDigits(text))}
                keyboardType="number-pad"
                autoFocus
                placeholder="0,00"
                placeholderTextColor="#5c626b"
              />
              <View style={styles.editRow}>
                <Pressable style={styles.ghost} onPress={() => setEditing('none')}>
                  <Text style={styles.ghostText}>Cancelar</Text>
                </Pressable>
                <Pressable
                  style={[styles.cta, styles.ctaInline, !canSave && styles.ctaOff]}
                  disabled={!canSave}
                  onPress={save}
                >
                  <Text style={styles.ctaText}>Salvar</Text>
                </Pressable>
              </View>
            </View>
          ) : null}

          {/* Sugestão, não aplicação automática: o usuário pode ter um motivo
              que o histórico não conhece. O backend só sugere com 10%+ de
              diferença, então quando aparece, vale a interrupção. */}
          {reserve.suggested_baseline ? (
            <View style={styles.warn}>
              <Text style={styles.warnText}>
                Seu gasto essencial nos últimos {reserve.suggested_baseline.months_used} meses foi{' '}
                <Text style={styles.warnStrong}>
                  {formatApiAmount(reserve.suggested_baseline.amount)}
                </Text>
                {reserve.suggested_baseline.direction === 'up'
                  ? ', acima do que está na sua meta.'
                  : ', abaixo do que está na sua meta.'}
              </Text>
              <Pressable style={styles.warnAction} onPress={adoptSuggestion}>
                <Text style={styles.warnActionText}>Atualizar a meta</Text>
              </Pressable>
            </View>
          ) : null}
        </>
      ) : needsOnboarding || error ? null : (
        <ActivityIndicator color="#e8a33d" style={styles.loading} />
      )}

      {/* --------------------------------------- meta de poupança do mês */}
      {savings?.target ? (
        <>
          <Text style={styles.section}>Meta de poupança de {monthName(month)}</Text>
          <View style={styles.card}>
            <Text style={styles.label}>Guardado neste mês</Text>
            <Text style={styles.big}>{formatApiAmount(savings.spent)}</Text>
            <View style={styles.track}>
              <View style={[styles.fill, styles.fillDone, { width: `${savingsPct(savings)}%` }]} />
            </View>
            <View style={styles.trackLine}>
              <Text style={styles.trackText}>meta {formatApiAmount(savings.target)}</Text>
              <Text style={styles.trackText}>{savingsPct(savings)}%</Text>
            </View>
            <Text style={styles.note}>
              Vem da sua regra 50-30-20. Poupança é <Text style={styles.warnStrong}>meta</Text>, não
              teto: aqui ficar abaixo é ficar devendo, ao contrário dos outros dois buckets.
            </Text>
          </View>
        </>
      ) : null}

      {/* Diz o que ainda não existe, em vez de deixar a aba parecer completa. */}
      <Text style={styles.note}>
        Nível, XP e conquistas entram aqui quando a regra de pontuação for definida. O cofrinho de
        arredondamento é manual nesta fase — automação real depende de conexão bancária, que está
        fora de escopo.
      </Text>
    </ScrollView>
  );
}

/** Trava em 100 como o backend faz na reserva: passar da meta é ótimo, mas barra
 *  de 140% confunde. */
function savingsPct(bucket: BucketProgress): number {
  const target = Number(bucket.target);
  if (!Number.isFinite(target) || target <= 0) return 0;
  return Math.min(Math.round((Number(bucket.spent) / target) * 100), 100);
}

const styles = StyleSheet.create({
  container: { backgroundColor: '#14171c', paddingHorizontal: 18, paddingBottom: 40, flexGrow: 1 },
  header: { paddingTop: 52, paddingBottom: 6 },
  brand: { color: '#eef0f3', fontSize: 16, fontWeight: '500' },
  headerSub: { color: '#8a8f98', fontSize: 11, marginTop: 2 },
  loading: { marginTop: 30 },

  section: {
    color: '#5c626b',
    fontSize: 10,
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginTop: 20,
    marginBottom: 8,
  },
  card: { backgroundColor: '#1c2028', borderRadius: 12, padding: 13, marginBottom: 8 },
  cardTitle: { color: '#eef0f3', fontSize: 14, fontWeight: '500', marginBottom: 4 },
  label: { color: '#8a8f98', fontSize: 10.5 },
  big: { color: '#eef0f3', fontSize: 25, fontWeight: '500' },
  covered: { color: '#e8a33d', fontSize: 11.5, marginTop: 2, marginBottom: 10 },
  subtitle: { color: '#8a8f98', fontSize: 12.5, lineHeight: 19, marginBottom: 4 },
  note: { color: '#5c626b', fontSize: 10.5, lineHeight: 16, marginTop: 10 },
  error: { color: '#d85a30', fontSize: 12.5, marginTop: 14 },

  track: { height: 6, backgroundColor: '#2b323c', borderRadius: 4, marginTop: 4 },
  fill: { height: 6, backgroundColor: '#e8a33d', borderRadius: 4 },
  fillDone: { backgroundColor: '#5dcaa5' },
  trackLine: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 6 },
  trackText: { color: '#8a8f98', fontSize: 10.5 },

  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: '#22272f',
  },
  rowLast: { borderBottomWidth: 0 },
  rowMain: { flex: 1, minWidth: 0 },
  rowName: { color: '#eef0f3', fontSize: 12.5 },
  rowMeta: { color: '#5c626b', fontSize: 10, marginTop: 1 },
  rowValue: { color: '#eef0f3', fontSize: 12.5 },
  rowEdit: { color: '#e8a33d', fontSize: 12.5 },

  editBox: { marginTop: 12, borderTopWidth: 1, borderTopColor: '#262b33', paddingTop: 12 },
  editRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  input: {
    backgroundColor: '#232832',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 11,
    color: '#eef0f3',
    fontSize: 17,
    marginTop: 6,
    marginBottom: 10,
  },

  cta: {
    backgroundColor: '#e8a33d',
    borderRadius: 11,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 10,
  },
  ctaInline: { flex: 1, marginTop: 0 },
  ctaOff: { opacity: 0.4 },
  ctaText: { color: '#2a1c04', fontSize: 13.5, fontWeight: '500' },
  ghost: {
    borderColor: '#262b33',
    borderWidth: 1,
    borderRadius: 11,
    paddingVertical: 11,
    paddingHorizontal: 14,
    alignItems: 'center',
    marginTop: 12,
  },
  ghostText: { color: '#8a8f98', fontSize: 12.5 },

  warn: {
    backgroundColor: '#221d14',
    borderColor: '#3d3320',
    borderWidth: 1,
    borderRadius: 11,
    padding: 12,
  },
  warnText: { color: '#e0c79a', fontSize: 11.5, lineHeight: 18 },
  warnStrong: { color: '#e8a33d', fontWeight: '500' },
  warnAction: { marginTop: 9 },
  warnActionText: { color: '#e8a33d', fontSize: 12.5, fontWeight: '500' },
});
