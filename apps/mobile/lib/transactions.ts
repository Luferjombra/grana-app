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

export function createTransaction(data: NewTransaction) {
  return api.post<{ id: number }>('/transactions', data);
}
