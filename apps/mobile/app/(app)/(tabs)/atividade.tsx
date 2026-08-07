import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from 'expo-router';

import { currentMonth, dayGroupLabel } from '../../../lib/dates';
import { formatApiAmount } from '../../../lib/money';
import { listTransactions, type Transaction } from '../../../lib/transactions';

export default function Atividade() {
  const [items, setItems] = useState<Transaction[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const month = currentMonth();

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      listTransactions(month)
        .then((page) => {
          if (cancelled) return;
          setItems(page.items);
          setCursor(page.next_cursor);
          setFailed(false);
        })
        .catch(() => {
          if (!cancelled) setFailed(true);
        });
      return () => {
        cancelled = true;
      };
    }, [month]),
  );

  async function loadMore() {
    if (!cursor || loadingMore) return;

    setLoadingMore(true);
    try {
      const page = await listTransactions(month, cursor);
      setItems((current) => [...(current ?? []), ...page.items]);
      setCursor(page.next_cursor);
    } catch {
      setFailed(true);
    } finally {
      setLoadingMore(false);
    }
  }

  const groups = groupByDay(items ?? []);

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Atividade</Text>

      {failed ? <Text style={styles.error}>Não foi possível carregar os lançamentos.</Text> : null}

      {items && items.length === 0 ? (
        <Text style={styles.empty}>
          Nenhum lançamento neste mês. Toque em Adicionar na tela de início pra registrar o
          primeiro.
        </Text>
      ) : null}

      {groups.map(([day, transactions]) => (
        <View key={day} style={styles.group}>
          <Text style={styles.groupLabel}>{dayGroupLabel(day).toUpperCase()}</Text>
          {transactions.map((transaction) => (
            <View key={transaction.id} style={styles.row}>
              <View style={styles.rowMain}>
                <Text style={styles.rowTitle}>
                  {transaction.merchant || transaction.categories?.name || 'Lançamento'}
                </Text>
                <Text style={styles.rowSub}>
                  {transaction.categories?.name ?? 'Sem categoria'}
                  {transaction.installment_total
                    ? ` · ${transaction.installment_number}/${transaction.installment_total}`
                    : ''}
                </Text>
              </View>
              <Text style={[styles.rowAmount, amountStyle(transaction.type)]}>
                {signFor(transaction.type)}
                {formatApiAmount(transaction.amount)}
              </Text>
            </View>
          ))}
        </View>
      ))}

      {cursor ? (
        <Pressable style={styles.more} onPress={loadMore} disabled={loadingMore}>
          <Text style={styles.moreText}>
            {loadingMore ? 'Carregando...' : 'Carregar mais lançamentos'}
          </Text>
        </Pressable>
      ) : null}
    </ScrollView>
  );
}

/** Agrupa por dia mantendo a ordem que veio da API (mais recente primeiro). */
function groupByDay(transactions: Transaction[]): [string, Transaction[]][] {
  const groups = new Map<string, Transaction[]>();
  for (const transaction of transactions) {
    const day = transaction.occurred_at;
    const bucket = groups.get(day);
    if (bucket) bucket.push(transaction);
    else groups.set(day, [transaction]);
  }
  return [...groups.entries()];
}

function signFor(type: Transaction['type']): string {
  if (type === 'income') return '+';
  if (type === 'expense') return '-';
  return '';
}

function amountStyle(type: Transaction['type']) {
  return type === 'income' ? styles.amountIn : undefined;
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    gap: 16,
  },
  title: {
    fontSize: 18,
    fontWeight: '500',
  },
  error: {
    color: '#d85a30',
    fontSize: 13,
  },
  empty: {
    fontSize: 13,
    color: '#8a8f98',
    lineHeight: 19,
  },
  group: {
    gap: 8,
  },
  groupLabel: {
    fontSize: 11,
    color: '#8a8f98',
    letterSpacing: 0.8,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  rowMain: {
    flex: 1,
    gap: 2,
  },
  rowTitle: {
    fontSize: 14,
  },
  rowSub: {
    fontSize: 11,
    color: '#8a8f98',
  },
  rowAmount: {
    fontSize: 14,
    fontWeight: '500',
  },
  amountIn: {
    color: '#5dcaa5',
  },
  more: {
    borderWidth: 1,
    borderColor: '#262b33',
    borderRadius: 10,
    paddingVertical: 11,
    alignItems: 'center',
    marginTop: 4,
  },
  moreText: {
    fontSize: 13,
    color: '#cfd3d9',
  },
});
