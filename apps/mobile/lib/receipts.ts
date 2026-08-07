import { api, authorizedFetch } from './api';

export type ReceiptStatus = 'pending' | 'processed' | 'failed';

/** Campos que o OCR conseguiu ler. Vêm null quando a confiança foi baixa —
 *  a spec 05 pede confirmação manual em vez de aceitar palpite. */
export type ExtractedPayload = {
  merchant: string | null;
  amount: number | null;
  occurred_at: string | null;
  category_hint: string | null;
};

export type Receipt = {
  id: number;
  status: ReceiptStatus;
  image_url: string;
  extracted_payload: (ExtractedPayload & { raw?: unknown }) | null;
  matched_transaction_id: number | null;
};

export type ReceiptConfirm = {
  amount: string;
  category_id: number;
  occurred_at: string;
  merchant?: string | null;
  installment_total?: number | null;
};

export async function uploadReceipt(uri: string, mimeType: string): Promise<Receipt> {
  const form = new FormData();
  // O React Native aceita este formato de "arquivo" no FormData; não dá pra
  // usar Blob aqui porque o fetch nativo não lê o arquivo local por Blob.
  form.append('file', {
    uri,
    name: filenameFor(uri, mimeType),
    type: mimeType,
  } as unknown as Blob);

  // Sem Content-Type manual: o fetch precisa gerar o boundary do multipart.
  const response = await authorizedFetch('/receipts', { method: 'POST', body: form });
  return response.json() as Promise<Receipt>;
}

export function getReceipt(id: number) {
  return api.get<Receipt>(`/receipts/${id}`);
}

export function confirmReceipt(id: number, data: ReceiptConfirm) {
  return api.post<{ id: number }>(`/receipts/${id}/confirm`, data);
}

/** O backend infere o mimetype pela extensão do nome, então ela precisa
 *  corresponder ao arquivo — 'receipt' sem extensão faz o Mindee recusar. */
export function filenameFor(uri: string, mimeType: string): string {
  const fromUri = uri.split('?')[0].split('/').pop() ?? '';
  if (/\.(jpe?g|png|heic|heif)$/i.test(fromUri)) return fromUri;

  const extension = mimeType.split('/')[1]?.replace('jpeg', 'jpg') ?? 'jpg';
  return `recibo.${extension}`;
}
