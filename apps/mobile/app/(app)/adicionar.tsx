import { useEffect, useState } from 'react';
import { Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import DateTimePicker from '@react-native-community/datetimepicker';

import { formatShortDate, isToday, toIsoDate } from '../../lib/dates';
import { centsToApiAmount, extractDigits, formatCents, isPositiveAmount } from '../../lib/money';
import {
  createTransaction,
  getCategories,
  type Category,
  type TransactionType,
} from '../../lib/transactions';

const TYPES: { value: TransactionType; label: string }[] = [
  { value: 'expense', label: 'Despesa' },
  { value: 'income', label: 'Receita' },
  { value: 'transfer', label: 'Transferência' },
];

const MAX_INSTALLMENTS = 12;
const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '00', '0', 'del'];

type OpenDetail = 'date' | 'merchant' | 'installments' | null;

export default function Adicionar() {
  const [type, setType] = useState<TransactionType>('expense');
  // Centavos como dígitos, nunca float — ver lib/money.ts.
  const [cents, setCents] = useState('');
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [date, setDate] = useState(new Date());
  const [merchant, setMerchant] = useState('');
  const [installments, setInstallments] = useState(1);
  const [openDetail, setOpenDetail] = useState<OpenDetail>(null);
  const [error, setError] = useState<string | undefined>();
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getCategories()
      .then((data) => {
        if (!cancelled) setCategories(data);
      })
      .catch(() => {
        if (!cancelled) setError('Não foi possível carregar as categorias.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Transferência não tem categoria, e receita usa outra lista — trocar de
  // tipo com uma categoria de despesa selecionada mandaria dado incoerente.
  const showsCategories = type !== 'transfer';
  const requiresCategory = type === 'expense';
  const canSubmit =
    isPositiveAmount(cents) && (!requiresCategory || categoryId !== null) && !submitting;

  function changeType(next: TransactionType) {
    setType(next);
    setCategoryId(null);
    if (next !== 'expense') setInstallments(1);
  }

  function pressKey(key: string) {
    setCents((current) => (key === 'del' ? current.slice(0, -1) : extractDigits(current + key)));
  }

  async function handleSave() {
    setSubmitting(true);
    setError(undefined);
    try {
      await createTransaction({
        amount: centsToApiAmount(cents),
        type,
        occurred_at: toIsoDate(date),
        category_id: showsCategories ? categoryId : null,
        merchant: merchant.trim() || null,
        installment_total: installments > 1 ? installments : null,
      });
      router.back();
    } catch {
      setError('Não foi possível salvar. Tente de novo.');
    } finally {
      setSubmitting(false);
    }
  }

  const dateLabel = isToday(date) ? 'Hoje' : formatShortDate(date);

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()}>
          <Text style={styles.cancel}>Cancelar</Text>
        </Pressable>
        <Text style={styles.headerTitle}>Novo lançamento</Text>
        <View style={styles.headerSpacer} />
      </View>

      <View style={styles.segmented}>
        {TYPES.map((option) => {
          const active = type === option.value;
          return (
            <Pressable
              key={option.value}
              style={[styles.segment, active && styles.segmentActive]}
              onPress={() => changeType(option.value)}
            >
              <Text style={[styles.segmentText, active && styles.segmentTextActive]}>
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <Text style={styles.amount}>R$ {formatCents(cents) || '0,00'}</Text>

      {showsCategories ? (
        <>
          <Text style={styles.label}>
            {requiresCategory ? 'Categoria (obrigatória)' : 'Categoria (opcional)'}
          </Text>
          <View style={styles.chips}>
            {categories.map((category) => {
              const active = categoryId === category.id;
              return (
                <Pressable
                  key={category.id}
                  style={[styles.chip, active && styles.chipActive]}
                  onPress={() => setCategoryId(active ? null : category.id)}
                >
                  <Text style={[styles.chipText, active && styles.chipTextActive]}>
                    {category.name}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </>
      ) : null}

      <View style={styles.chips}>
        <DetailPill
          label={dateLabel}
          active={openDetail === 'date'}
          onPress={() => setOpenDetail(openDetail === 'date' ? null : 'date')}
        />
        <DetailPill
          label={merchant.trim() || 'Onde'}
          active={openDetail === 'merchant'}
          onPress={() => setOpenDetail(openDetail === 'merchant' ? null : 'merchant')}
        />
        {type === 'expense' ? (
          <DetailPill
            label={installments > 1 ? `${installments}x` : 'À vista'}
            active={openDetail === 'installments'}
            onPress={() => setOpenDetail(openDetail === 'installments' ? null : 'installments')}
          />
        ) : null}
      </View>

      {openDetail === 'date' ? (
        <View>
          <DateTimePicker
            value={date}
            mode="date"
            maximumDate={new Date()}
            onChange={(_event, selected) => {
              if (selected) setDate(selected);
              // No Android o seletor é um diálogo modal e já se fecha na
              // escolha. No iOS ele fica embutido e dispara onChange a cada
              // giro da roda — fechar aqui faria a data sumir no primeiro
              // toque, deixando o campo quase impossível de usar.
              if (Platform.OS === 'android') setOpenDetail(null);
            }}
          />
          {Platform.OS === 'ios' ? (
            <Pressable style={styles.pickerDone} onPress={() => setOpenDetail(null)}>
              <Text style={styles.pickerDoneText}>Pronto</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}

      {openDetail === 'merchant' ? (
        <TextInput
          style={styles.input}
          placeholder="Mercado, posto, restaurante..."
          placeholderTextColor="#5c626b"
          value={merchant}
          onChangeText={setMerchant}
          autoFocus
        />
      ) : null}

      {openDetail === 'installments' ? (
        <View style={styles.chips}>
          {Array.from({ length: MAX_INSTALLMENTS }, (_, index) => index + 1).map((count) => {
            const active = installments === count;
            return (
              <Pressable
                key={count}
                style={[styles.chip, active && styles.chipActive]}
                onPress={() => {
                  setInstallments(count);
                  setOpenDetail(null);
                }}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>
                  {count === 1 ? 'À vista' : `${count}x`}
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}

      <View style={styles.keypad}>
        {KEYS.map((key) => (
          <Pressable key={key} style={styles.key} onPress={() => pressKey(key)}>
            <Text style={styles.keyText}>{key === 'del' ? '⌫' : key}</Text>
          </Pressable>
        ))}
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable
        style={[styles.save, !canSubmit && styles.saveDisabled]}
        disabled={!canSubmit}
        onPress={handleSave}
      >
        <Text style={styles.saveText}>Salvar</Text>
      </Pressable>
      <Text style={styles.hint}>
        {!isPositiveAmount(cents)
          ? 'Informe um valor'
          : requiresCategory && categoryId === null
            ? 'Escolha uma categoria'
            : 'Tudo pronto'}
      </Text>
    </ScrollView>
  );
}

function DetailPill({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable style={[styles.chip, active && styles.chipOpen]} onPress={onPress}>
      <Text style={styles.chipText}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    gap: 14,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  cancel: {
    fontSize: 13,
    color: '#8a8f98',
  },
  headerTitle: {
    fontSize: 15,
    fontWeight: '500',
  },
  headerSpacer: {
    width: 56,
  },
  segmented: {
    flexDirection: 'row',
    backgroundColor: '#1c2028',
    borderRadius: 20,
    padding: 3,
  },
  segment: {
    flex: 1,
    borderRadius: 18,
    paddingVertical: 8,
    alignItems: 'center',
  },
  segmentActive: {
    backgroundColor: '#f5f6f8',
  },
  segmentText: {
    fontSize: 12,
    color: '#8a8f98',
  },
  segmentTextActive: {
    color: '#14171c',
  },
  amount: {
    textAlign: 'center',
    fontSize: 30,
    fontWeight: '500',
  },
  label: {
    fontSize: 11,
    color: '#8a8f98',
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  chip: {
    backgroundColor: '#1c2028',
    borderRadius: 20,
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  chipActive: {
    backgroundColor: '#e8a33d',
  },
  chipOpen: {
    borderWidth: 1,
    borderColor: '#e8a33d',
  },
  chipText: {
    fontSize: 11,
    color: '#cfd3d9',
  },
  chipTextActive: {
    color: '#2a1c04',
  },
  input: {
    borderWidth: 1,
    borderColor: '#262b33',
    borderRadius: 10,
    paddingVertical: 11,
    paddingHorizontal: 12,
    fontSize: 14,
  },
  pickerDone: {
    alignSelf: 'flex-end',
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  pickerDoneText: {
    fontSize: 13,
    color: '#e8a33d',
    fontWeight: '500',
  },
  keypad: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  key: {
    width: '31.5%',
    backgroundColor: '#1c2028',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
  },
  keyText: {
    fontSize: 16,
  },
  error: {
    color: '#d85a30',
    fontSize: 12,
    textAlign: 'center',
  },
  save: {
    backgroundColor: '#e8a33d',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
  },
  saveDisabled: {
    opacity: 0.45,
  },
  saveText: {
    color: '#2a1c04',
    fontSize: 14,
    fontWeight: '500',
  },
  hint: {
    textAlign: 'center',
    fontSize: 11,
    color: '#8a8f98',
  },
});
