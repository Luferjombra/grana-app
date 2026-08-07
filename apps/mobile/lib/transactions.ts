import { api } from './api';

export type Bucket = 'necessidades' | 'desejos' | 'poupanca';
export type TransactionType = 'expense' | 'income' | 'transfer';

export type Category = {
  id: number;
  name: string;
  bucket: Bucket;
  icon: string | null;
  is_default: boolean;
};

export type NewTransaction = {
  /** Valor **cheio** da compra. Ao parcelar, o backend divide entre as
   *  parcelas e cria uma transação por mês. */
  amount: string;
  type: TransactionType;
  occurred_at: string;
  category_id?: number | null;
  merchant?: string | null;
  installment_total?: number | null;
};

export function getCategories() {
  return api.get<Category[]>('/categories');
}

export type Transaction = {
  id: number;
  amount: string;
  type: TransactionType;
  occurred_at: string;
  merchant: string | null;
  note: string | null;
  entry_method: string;
  installment_number: number | null;
  installment_total: number | null;
  categories: Pick<Category, 'id' | 'name' | 'bucket' | 'icon'> | null;
};

export function createTransaction(data: NewTransaction) {
  return api.post<Transaction & { installments_created: number }>('/transactions', data);
}

export type TransactionPage = {
  items: Transaction[];
  /** null na última página. Ignorar isso esconderia lançamentos sem avisar. */
  next_cursor: string | null;
};

export function listTransactions(month: string, cursor?: string | null) {
  const query = cursor ? `?month=${month}&cursor=${encodeURIComponent(cursor)}` : `?month=${month}`;
  return api.get<TransactionPage>(`/transactions${query}`);
}
