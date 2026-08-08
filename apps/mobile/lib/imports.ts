import { api, authorizedFetch } from './api';

/** Uma linha do extrato, como o preview devolve. */
export type ImportItem = {
  occurred_at: string;
  amount: string;
  type: 'expense' | 'income';
  description: string;
  external_id: string | null;
  likely_duplicate: boolean;
  category_id: number | null;
};

export type ImportGroup = {
  /** Chave de agrupamento. Vazia quando o lançamento não tem descrição
   *  aproveitável — nesse caso o grupo tem um item só, de propósito. */
  merchant_key: string;
  label: string;
  suggested_category_id: number | null;
  /** Falso em grupo só de entrada: só despesa exige categoria (specs/09). */
  needs_category: boolean;
  count: number;
  total: string;
  likely_duplicates: number;
  items: ImportItem[];
};

export type ImportMonth = { month: string; total: number };

export type ImportPreview = {
  /** Mês que este preview cobre. Omitido no pedido, vem o mais recente. */
  month: string;
  months: ImportMonth[];
  groups: ImportGroup[];
  summary: {
    total: number;
    merchants: number;
    suggested: number;
    likely_duplicates: number;
    rules_applied: number;
  };
};

export type ImportConfirmRow = {
  amount: string;
  type: 'expense' | 'income';
  occurred_at: string;
  description: string | null;
  category_id: number | null;
  external_id: string | null;
};

export type ImportResult = {
  imported: number;
  skipped: number;
  months_touched: string[];
  /** Quantas regras o backend aprendeu com estas escolhas. */
  rules_learned: number;
};

export type PickedFile = { uri: string; name: string; mimeType?: string | null };

/**
 * Sobe o extrato e devolve o preview de **um mês**. Nada é gravado aqui.
 *
 * Usa `authorizedFetch` em vez de `api.post` porque é multipart: o fetch precisa
 * gerar o boundary sozinho, e fixar Content-Type quebraria o parse no servidor.
 */
export async function previewImport(file: PickedFile, month?: string): Promise<ImportPreview> {
  const form = new FormData();
  // O React Native aceita este objeto no lugar de um Blob; o backend lê o
  // filename pra decidir entre OFX e CSV, então ele não pode faltar.
  form.append('file', {
    uri: file.uri,
    name: file.name,
    type: file.mimeType || 'application/octet-stream',
  } as unknown as Blob);

  if (month) form.append('month', month);

  const response = await authorizedFetch('/transactions/import', { method: 'POST', body: form });
  return response.json() as Promise<ImportPreview>;
}

export function confirmImport(rows: ImportConfirmRow[]) {
  return api.post<ImportResult>('/transactions/import/confirm', { rows });
}
