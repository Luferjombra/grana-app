import { useCallback, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';
import { Ionicons } from '@expo/vector-icons';

import { formatApiAmount, sumApiAmounts } from '../../lib/money';
import { monthName } from '../../lib/dates';
import {
  confirmImport,
  previewImport,
  type ImportMonth,
  type ImportPreview,
  type PickedFile,
} from '../../lib/imports';
import {
  DEFER,
  assignMany,
  buildUnits,
  deferredCount,
  initialAssignment,
  orphans,
  removeItem,
  resolvedCount,
  restoreItem,
  toConfirmRows,
  totalCount,
  type Assignment,
  type Destination,
  type Removed,
} from '../../lib/import-tray';
import { getCategories, type Category } from '../../lib/transactions';

type Phase = 'choosing' | 'reading' | 'tray' | 'saving' | 'done';

export default function ImportarScreen() {
  const [phase, setPhase] = useState<Phase>('choosing');
  const [file, setFile] = useState<PickedFile | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [assignment, setAssignment] = useState<Assignment>({});
  const [removed, setRemoved] = useState<Removed>({});
  const [marked, setMarked] = useState<Record<string, true>>({});
  const [bin, setBin] = useState<Destination | null>(null);
  const [open, setOpen] = useState<Record<string, true>>({});
  const [result, setResult] = useState<{ imported: number; rules: number; left: number } | null>(
    null,
  );
  const [error, setError] = useState<string | undefined>();

  const units = useMemo(
    () => (preview ? buildUnits(preview.groups, removed) : []),
    [preview, removed],
  );
  const total = totalCount(units);
  const resolved = resolvedCount(units, assignment);
  const deferred = deferredCount(units, assignment);
  const pending = orphans(units, assignment);
  const markedIds = Object.keys(marked);

  const loadMonth = useCallback(async (picked: PickedFile, month?: string) => {
    setPhase('reading');
    setError(undefined);
    try {
      // Categorias e preview em paralelo é tentador, mas uma falha isolada
      // apagaria a outra — mesmo motivo de a Home não usar Promise.all.
      const data = await previewImport(picked, month);
      const cats = await getCategories().catch(() => [] as Category[]);

      setPreview(data);
      setCategories(cats);
      setAssignment(initialAssignment(data.groups));
      setRemoved({});
      setMarked({});
      setBin(null);
      setOpen({});
      setPhase('tray');
    } catch (problem) {
      // Volta pra escolha do arquivo: nada foi gravado no preview, então
      // tentar de novo é seguro (diferente do recibo, em que a foto já subiu).
      setPhase('choosing');
      setError(
        problem instanceof Error && problem.message.includes('422')
          ? 'Não consegui ler esse extrato. Ele pode estar num formato diferente ou ter lançamentos demais — tente exportar um período menor.'
          : 'Não consegui ler esse extrato. Confira o arquivo e tente de novo.',
      );
    }
  }, []);

  async function pick() {
    setError(undefined);
    const picked = await DocumentPicker.getDocumentAsync({
      // OFX raramente tem MIME registrado, então aceita qualquer tipo e deixa o
      // backend decidir pela extensão.
      type: '*/*',
      copyToCacheDirectory: true,
    });
    if (picked.canceled) return;

    const asset = picked.assets[0];
    const chosen = { uri: asset.uri, name: asset.name, mimeType: asset.mimeType };
    setFile(chosen);
    await loadMonth(chosen);
  }

  function toggleMark(id: string) {
    setMarked((current) => {
      const next = { ...current };
      if (next[id]) delete next[id];
      else next[id] = true;
      return next;
    });
  }

  function applyBin() {
    if (bin === null || markedIds.length === 0) return;
    setAssignment((current) => assignMany(current, markedIds, bin));
    setMarked({});
    setBin(null);
  }

  /** Devolve o item ao grupo, limpando o destino e a marcação da unidade solta
   *  que deixa de existir — senão o botão diria "Atribuir 3" com 2 unidades. */
  function restore(groupIndex: number, itemIndex: number, unitId: string) {
    const back = restoreItem(removed, assignment, groupIndex, itemIndex);
    setRemoved(back.removed);
    setAssignment(back.assignment);
    setMarked((current) => {
      if (!current[unitId]) return current;
      const next = { ...current };
      delete next[unitId];
      return next;
    });
  }

  async function save() {
    if (!preview) return;
    setPhase('saving');
    setError(undefined);
    try {
      const rows = toConfirmRows(units, assignment);
      const saved = await confirmImport(rows);
      setResult({ imported: saved.imported, rules: saved.rules_learned, left: deferred });
      setPhase('done');
    } catch {
      // Volta pra bandeja com as escolhas intactas: refazer 27 decisões porque
      // a rede caiu seria o pior desfecho possível aqui.
      setPhase('tray');
      setError('Não consegui salvar. Suas escolhas continuam aqui — tente de novo.');
    }
  }

  const nextMonth = useMemo(() => {
    if (!preview) return null;
    const index = preview.months.findIndex((m) => m.month === preview.month);
    return index >= 0 ? (preview.months[index + 1] ?? null) : null;
  }, [preview]);

  // ---------------------------------------------------------------- escolha
  if (phase === 'choosing' || phase === 'reading') {
    return (
      <View style={styles.screen}>
        <Header title="Importar extrato" />
        <ScrollView contentContainerStyle={styles.pad}>
          <Text style={styles.h1}>Traga seu extrato do banco</Text>
          <Text style={styles.sub}>
            Exporte o extrato em OFX no app do seu banco e escolha o arquivo aqui. Você revisa tudo
            antes — nada é salvo sem a sua confirmação.
          </Text>

          {phase === 'reading' ? (
            <View style={styles.loading}>
              <ActivityIndicator color="#e8a33d" />
              <Text style={styles.sub}>Lendo o extrato…</Text>
            </View>
          ) : (
            <Pressable style={styles.cta} onPress={pick}>
              <Text style={styles.ctaText}>Escolher arquivo</Text>
            </Pressable>
          )}

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Text style={styles.note}>
            Aceita OFX e CSV. Um extrato de vários meses é resolvido um mês por vez: o que você
            escolher no primeiro mês vira regra e adianta os seguintes.
          </Text>
        </ScrollView>
      </View>
    );
  }

  // ------------------------------------------------------------------ fim
  if (phase === 'done' && result) {
    return (
      <View style={styles.screen}>
        <Header title={monthLabel(preview?.month)} />
        <ScrollView contentContainerStyle={styles.pad}>
          <Text style={styles.big}>✓</Text>
          <Text style={styles.h1}>{result.imported} lançamentos importados</Text>
          {result.rules > 0 ? (
            <Text style={styles.sub}>
              Aprendi {result.rules} {result.rules === 1 ? 'regra' : 'regras'} suas. Os próximos
              meses já vêm quase prontos.
            </Text>
          ) : null}

          {result.left > 0 ? (
            <View style={styles.warn}>
              <Text style={styles.warnText}>
                <Text style={styles.warnStrong}>
                  {result.left} {result.left === 1 ? 'lançamento ficou' : 'lançamentos ficaram'} de
                  fora
                </Text>{' '}
                porque você adiou. Este mês entra incompleto e o painel vai subestimar o gasto até
                você voltar neles — reimporte o mesmo arquivo quando quiser resolver.
              </Text>
            </View>
          ) : null}

          {nextMonth && file ? (
            <Pressable style={styles.cta} onPress={() => loadMonth(file, nextMonth.month)}>
              <Text style={styles.ctaText}>
                Continuar com {monthLabel(nextMonth.month)} · {nextMonth.total} lançamentos
              </Text>
            </Pressable>
          ) : null}

          <Pressable style={styles.ghost} onPress={() => router.back()}>
            <Text style={styles.ghostText}>
              {nextMonth ? 'Parar aqui e ver meu painel' : 'Ver meu painel'}
            </Text>
          </Pressable>
        </ScrollView>
      </View>
    );
  }

  // --------------------------------------------------------------- bandeja
  const pct = total > 0 ? Math.round((resolved / total) * 100) : 0;

  return (
    <View style={styles.screen}>
      <Header
        title={monthLabel(preview?.month)}
        right={monthPosition(preview?.months, preview?.month)}
      />

      <ScrollView contentContainerStyle={styles.pad} keyboardShouldPersistTaps="handled">
        <View style={styles.progRow}>
          <Text style={styles.progLabel}>
            {resolved} de {total} lançamentos resolvidos
          </Text>
          <Text style={styles.progLabel}>{pct}%</Text>
        </View>
        <View style={styles.track}>
          <View style={[styles.fill, { width: `${pct}%` }]} />
        </View>

        <Text style={styles.sub}>
          Escolha uma categoria e marque tudo que pertence a ela.
          {preview && preview.summary.rules_applied > 0
            ? ` ${preview.summary.suggested} ${
                preview.summary.suggested === 1 ? 'lançamento já veio' : 'lançamentos já vieram'
              } pronto pelas suas regras.`
            : ''}
        </Text>

        <View style={styles.bins}>
          {categories.map((category) => (
            <Bin
              key={category.id}
              label={category.name}
              active={bin === category.id}
              onPress={() => setBin(bin === category.id ? null : category.id)}
            />
          ))}
          <Bin
            label="Decidir depois"
            dashed
            active={bin === DEFER}
            onPress={() => setBin(bin === DEFER ? null : DEFER)}
          />
        </View>

        <Text style={styles.hint}>
          {pending.length === 0
            ? 'Tudo tem destino.'
            : bin === null
              ? `Escolha uma categoria acima. ${pending.length} sem destino.`
              : `Marque tudo que é ${binLabel(bin, categories)} — ${pending.length} sem destino.`}
        </Text>

        {deferred > 0 ? (
          <View style={styles.warn}>
            <Text style={styles.warnText}>
              <Text style={styles.warnStrong}>{deferred} ficam de fora</Text> deste import. O mês
              entra incompleto até você voltar neles.
            </Text>
          </View>
        ) : null}

        {error ? <Text style={styles.error}>{error}</Text> : null}

        {orderUnits(units, assignment).map((unit) => {
          const destination = assignment[unit.id];
          const settled = destination !== undefined;
          const isDefer = destination === DEFER;

          return (
            <View
              key={unit.id}
              style={[
                styles.row,
                marked[unit.id] && styles.rowMarked,
                settled && !isDefer && styles.rowTaken,
                isDefer && styles.rowDefer,
              ]}
            >
              <View style={styles.rowHead}>
                <Pressable
                  style={styles.rowMain}
                  disabled={settled || !unit.needsCategory}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: !!marked[unit.id], disabled: settled }}
                  onPress={() => toggleMark(unit.id)}
                >
                  <View
                    style={[
                      styles.box,
                      marked[unit.id] && styles.boxOn,
                      settled && styles.boxPlain,
                    ]}
                  >
                    <Text style={styles.boxMark}>
                      {settled ? (isDefer ? '·' : '✓') : marked[unit.id] ? '✓' : ''}
                    </Text>
                  </View>

                  <View style={styles.rowText}>
                    <Text style={styles.rowName} numberOfLines={1}>
                      {unit.label}
                    </Text>
                    <Text style={styles.rowMeta}>{describe(unit, destination, categories)}</Text>
                  </View>
                </Pressable>

                {unit.canSplit ? (
                  <Pressable
                    style={styles.iconButton}
                    accessibilityLabel="Ver lançamentos"
                    onPress={() =>
                      setOpen((current) => {
                        const next = { ...current };
                        if (next[unit.id]) delete next[unit.id];
                        else next[unit.id] = true;
                        return next;
                      })
                    }
                  >
                    <Ionicons
                      name={open[unit.id] ? 'chevron-up' : 'chevron-down'}
                      size={15}
                      color="#5c626b"
                    />
                  </Pressable>
                ) : null}

                {unit.isLoose ? (
                  <Pressable
                    style={styles.iconButton}
                    accessibilityLabel="Devolver ao grupo"
                    // Calcula fora dos updaters: chamar setAssignment dentro do
                    // updater de setRemoved é efeito colateral numa função que o
                    // React pode reexecutar.
                    onPress={() => restore(unit.groupIndex, unit.itemIndex as number, unit.id)}
                  >
                    <Ionicons name="arrow-undo-outline" size={15} color="#8a8f98" />
                  </Pressable>
                ) : null}
              </View>

              {open[unit.id]
                ? unit.items.map((entry, index) => (
                    <View key={`${unit.groupIndex}-${unit.itemIndexes[index]}`} style={styles.item}>
                      <Text style={styles.itemDesc} numberOfLines={1}>
                        {entry.description || 'Sem descrição'}
                      </Text>
                      <Text style={styles.itemValue}>{formatApiAmount(entry.amount)}</Text>
                      <Pressable
                        accessibilityLabel="Não é deste grupo"
                        hitSlop={8}
                        // Índice real do item no grupo, não a posição na lista
                        // exibida nem uma busca por conteúdo: dois lançamentos
                        // idênticos no mesmo grupo são comuns, e a busca acharia
                        // sempre o primeiro.
                        onPress={() =>
                          setRemoved((current) =>
                            removeItem(current, unit.groupIndex, unit.itemIndexes[index]),
                          )
                        }
                      >
                        <Text style={styles.itemRemove}>✕</Text>
                      </Pressable>
                    </View>
                  ))
                : null}
            </View>
          );
        })}

        <Pressable
          style={[styles.cta, (bin === null || markedIds.length === 0) && styles.ctaOff]}
          disabled={bin === null || markedIds.length === 0}
          onPress={applyBin}
        >
          <Text style={styles.ctaText}>
            {markedIds.length > 0 && bin !== null
              ? `Atribuir ${markedIds.length} a ${binLabel(bin, categories)}`
              : 'Atribuir'}
          </Text>
        </Pressable>

        <Pressable
          style={[styles.ghost, pending.length > 0 && styles.ctaOff]}
          disabled={pending.length > 0 || phase === 'saving'}
          onPress={save}
        >
          <Text style={styles.ghostText}>
            {phase === 'saving'
              ? 'Salvando…'
              : pending.length > 0
                ? `Importar · ${pending.length} sem categoria`
                : deferred > 0
                  ? `Importar ${resolved} de ${total} · ${deferred} pra depois`
                  : `Importar ${total} lançamentos`}
          </Text>
        </Pressable>

        <Text style={styles.note}>
          Não reconheceu um PIX? Manda pra Decidir depois — ele fica de fora e volta numa segunda
          passada, em vez de travar o mês. A seta abre os lançamentos do grupo, e o ✕ tira o que não
          pertence a ele.
        </Text>
      </ScrollView>
    </View>
  );
}

function Header({ title, right }: { title: string; right?: string | null }) {
  return (
    <View style={styles.bar}>
      <Pressable onPress={() => router.back()} hitSlop={8}>
        <Text style={styles.barSide}>Voltar</Text>
      </Pressable>
      <Text style={styles.barTitle}>{title}</Text>
      <Text style={[styles.barSide, styles.barRight]}>{right ?? ''}</Text>
    </View>
  );
}

function Bin({
  label,
  active,
  dashed,
  onPress,
}: {
  label: string;
  active: boolean;
  dashed?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      style={[styles.bin, dashed && styles.binDashed, active && styles.binOn]}
      onPress={onPress}
    >
      <Text style={[styles.binText, active && styles.binTextOn]}>{label}</Text>
    </Pressable>
  );
}

/** Pendentes primeiro: o que já tem destino desce e sai do caminho. */
function orderUnits(units: ReturnType<typeof buildUnits>, assignment: Assignment) {
  const pending = units.filter((unit) => unit.needsCategory && assignment[unit.id] === undefined);
  const rest = units.filter((unit) => !pending.includes(unit));
  return [...pending, ...rest];
}

function binLabel(bin: Destination, categories: Category[]) {
  if (bin === DEFER) return 'Decidir depois';
  return categories.find((category) => category.id === bin)?.name ?? 'categoria';
}

function describe(
  unit: ReturnType<typeof buildUnits>[number],
  destination: Destination | undefined,
  categories: Category[],
) {
  const parts: string[] = [];

  if (unit.isLoose) parts.push('tirado do grupo');
  else parts.push(`${unit.count} ${unit.count === 1 ? 'lançamento' : 'lançamentos'}`);

  // Soma em centavos, nunca em float (specs/09). O total do backend não serve
  // aqui porque deixa de valer quando o usuário tira item do grupo.
  const expenses = unit.items.filter((item) => item.type === 'expense');
  if (expenses.length > 0)
    parts.push(formatApiAmount(sumApiAmounts(expenses.map((i) => i.amount))));
  else parts.push('entrada');

  // Na segunda passada o usuário reimporta o mesmo arquivo pelos adiados, e sem
  // este aviso ele recategorizaria tudo sem saber que já entrou.
  if (unit.items.every((item) => item.likely_duplicate)) parts.push('já importado');

  if (destination !== undefined) parts.push(binLabel(destination, categories));

  return parts.join(' · ');
}

function monthLabel(month?: string) {
  if (!month) return 'Importar';
  return `${monthName(month)} de ${month.split('-')[0]}`;
}

function monthPosition(months: ImportMonth[] | undefined, current: string | undefined) {
  if (!months || !current || months.length < 2) return null;
  const index = months.findIndex((entry) => entry.month === current);
  return index >= 0 ? `mês ${index + 1}/${months.length}` : null;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#14171c' },
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 18,
    paddingTop: 52,
    paddingBottom: 10,
  },
  barTitle: { color: '#eef0f3', fontSize: 15, fontWeight: '500' },
  barSide: { color: '#8a8f98', fontSize: 12.5, width: 74 },
  barRight: { textAlign: 'right' },
  pad: { paddingHorizontal: 18, paddingBottom: 48 },

  h1: { color: '#eef0f3', fontSize: 19, fontWeight: '500', marginBottom: 6 },
  big: { color: '#5dcaa5', fontSize: 34, textAlign: 'center', marginBottom: 10 },
  sub: { color: '#8a8f98', fontSize: 12.5, lineHeight: 19, marginBottom: 14 },
  hint: { color: '#8a8f98', fontSize: 12.5, lineHeight: 19, marginBottom: 10 },
  note: { color: '#5c626b', fontSize: 11, lineHeight: 17, marginTop: 12 },
  error: { color: '#d85a30', fontSize: 12.5, lineHeight: 19, marginBottom: 12 },
  loading: { alignItems: 'center', gap: 10, paddingVertical: 20 },

  progRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  progLabel: { color: '#8a8f98', fontSize: 11 },
  track: { height: 6, backgroundColor: '#1c2028', borderRadius: 4, marginBottom: 14 },
  fill: { height: 6, backgroundColor: '#e8a33d', borderRadius: 4 },

  bins: { flexDirection: 'row', flexWrap: 'wrap', gap: 5, marginBottom: 12 },
  bin: {
    backgroundColor: '#1c2028',
    borderColor: '#262b33',
    borderWidth: 1,
    borderRadius: 16,
    paddingVertical: 6,
    paddingHorizontal: 11,
  },
  binDashed: { borderStyle: 'dashed' },
  binOn: { backgroundColor: '#e8a33d', borderColor: '#e8a33d' },
  binText: { color: '#cfd3d9', fontSize: 11 },
  binTextOn: { color: '#2a1c04' },

  row: {
    backgroundColor: '#1c2028',
    borderColor: '#262b33',
    borderWidth: 1,
    borderRadius: 11,
    marginBottom: 7,
    overflow: 'hidden',
  },
  rowMarked: { borderColor: '#e8a33d', backgroundColor: '#232832' },
  rowTaken: { opacity: 0.55 },
  rowDefer: { opacity: 0.8, borderStyle: 'dashed' },
  rowHead: { flexDirection: 'row', alignItems: 'center' },
  rowMain: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
    paddingVertical: 10,
    paddingLeft: 12,
  },
  rowText: { flex: 1 },
  rowName: { color: '#eef0f3', fontSize: 13, fontWeight: '500' },
  rowMeta: { color: '#8a8f98', fontSize: 10.5, marginTop: 2 },
  box: {
    width: 18,
    height: 18,
    borderRadius: 5,
    borderWidth: 1.5,
    borderColor: '#454c57',
    alignItems: 'center',
    justifyContent: 'center',
  },
  boxOn: { backgroundColor: '#e8a33d', borderColor: '#e8a33d' },
  boxPlain: { borderWidth: 0 },
  boxMark: { color: '#2a1c04', fontSize: 11 },
  iconButton: { paddingHorizontal: 10, paddingVertical: 10 },

  item: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: '#262b33',
  },
  itemDesc: { flex: 1, color: '#cfd3d9', fontSize: 11.5 },
  itemValue: { color: '#cfd3d9', fontSize: 11.5 },
  itemRemove: { color: '#5c626b', fontSize: 13 },

  warn: {
    backgroundColor: '#2a2016',
    borderColor: '#4a3a22',
    borderWidth: 1,
    borderRadius: 11,
    padding: 12,
    marginBottom: 10,
  },
  warnText: { color: '#e0c79a', fontSize: 11.5, lineHeight: 18 },
  warnStrong: { color: '#e8a33d', fontWeight: '500' },

  cta: {
    backgroundColor: '#e8a33d',
    borderRadius: 11,
    paddingVertical: 13,
    alignItems: 'center',
    marginTop: 6,
  },
  ctaOff: { opacity: 0.4 },
  ctaText: { color: '#2a1c04', fontSize: 14, fontWeight: '500' },
  ghost: {
    borderColor: '#262b33',
    borderWidth: 1,
    borderRadius: 11,
    paddingVertical: 13,
    alignItems: 'center',
    marginTop: 8,
  },
  ghostText: { color: '#8a8f98', fontSize: 13 },
});
