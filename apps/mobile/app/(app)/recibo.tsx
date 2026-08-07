import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { router } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import DateTimePicker from '@react-native-community/datetimepicker';

import { formatShortDate, isToday, parseIsoDate, toIsoDate } from '../../lib/dates';
import {
  centsToApiAmount,
  extractDigits,
  formatCents,
  isPositiveAmount,
  numberToCents,
} from '../../lib/money';
import { confirmReceipt, getReceipt, uploadReceipt, type Receipt } from '../../lib/receipts';
import { getCategories, type Category } from '../../lib/transactions';

type Phase = 'choosing' | 'uploading' | 'processing' | 'review' | 'saving';

// O OCR roda em background no servidor; ~30s cobre o caso normal sem deixar
// o usuário preso numa tela girando pra sempre se algo travar.
const POLL_INTERVAL_MS = 1500;
const MAX_POLLS = 20;

export default function ReciboScreen() {
  const [phase, setPhase] = useState<Phase>('choosing');
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [cents, setCents] = useState('');
  const [merchant, setMerchant] = useState('');
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [date, setDate] = useState(new Date());
  const [pickingDate, setPickingDate] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const cancelled = useRef(false);
  useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
    };
  }, []);

  useEffect(() => {
    getCategories()
      .then((data) => {
        if (!cancelled.current) setCategories(data);
      })
      .catch(() => {});
  }, []);

  const pollUntilProcessed = useCallback(async (id: number) => {
    for (let attempt = 0; attempt < MAX_POLLS; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      if (cancelled.current) return;

      let current: Receipt;
      try {
        current = await getReceipt(id);
      } catch {
        // A foto já subiu e o OCR já rodou: mandar o usuário refotografar
        // criaria um segundo recibo e gastaria outro crédito do Mindee.
        // Segue pra revisão manual, que é o pior caso aceitável.
        if (cancelled.current) return;
        setPhase('review');
        setError('Perdemos a conexão ao ler o recibo. Confira os campos e salve.');
        return;
      }

      if (current.status === 'pending') continue;

      if (current.status === 'failed') {
        setPhase('review');
        setError('Não conseguimos ler o recibo. Preencha os campos à mão.');
        return;
      }

      // Campos vêm null quando a confiança do OCR foi baixa (specs/05): o
      // usuário confirma em vez de o app chutar um valor errado.
      const extracted = current.extracted_payload;
      setReceipt(current);
      if (extracted?.amount) setCents(numberToCents(extracted.amount));
      if (extracted?.merchant) setMerchant(extracted.merchant);
      if (extracted?.occurred_at) {
        const parsed = parseIsoDate(extracted.occurred_at);
        if (parsed) setDate(parsed);
      }
      setPhase('review');
      return;
    }

    setPhase('review');
    setError('O processamento está demorando. Confira os campos e salve à mão.');
  }, []);

  async function pick(source: 'camera' | 'library') {
    setError(undefined);

    const permission =
      source === 'camera'
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (!permission.granted) {
      setError(
        source === 'camera'
          ? 'Precisamos da câmera pra fotografar o recibo.'
          : 'Precisamos de acesso às fotos pra ler o recibo.',
      );
      return;
    }

    const options: ImagePicker.ImagePickerOptions = {
      mediaTypes: ['images'],
      // Comprime: o backend recusa acima de 10MB, e foto de celular moderno
      // passa disso fácil. 0.7 mantém o recibo legível pro OCR.
      quality: 0.7,
    };

    const result =
      source === 'camera'
        ? await ImagePicker.launchCameraAsync(options)
        : await ImagePicker.launchImageLibraryAsync(options);

    if (result.canceled) return;

    const asset = result.assets[0];
    setImageUri(asset.uri);
    setPhase('uploading');

    try {
      const created = await uploadReceipt(asset.uri, asset.mimeType ?? 'image/jpeg');
      if (cancelled.current) return;
      setReceipt(created);
      setPhase('processing');
      await pollUntilProcessed(created.id);
    } catch {
      if (cancelled.current) return;
      setPhase('choosing');
      setError('Não foi possível enviar a foto. Tente de novo.');
    }
  }

  async function handleConfirm() {
    if (!receipt || categoryId === null) return;

    setPhase('saving');
    setError(undefined);
    try {
      await confirmReceipt(receipt.id, {
        amount: centsToApiAmount(cents),
        category_id: categoryId,
        occurred_at: toIsoDate(date),
        merchant: merchant.trim() || null,
      });
      router.back();
    } catch {
      setPhase('review');
      setError('Não foi possível salvar. Tente de novo.');
    }
  }

  const canConfirm = isPositiveAmount(cents) && categoryId !== null && phase === 'review';

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()}>
          <Text style={styles.cancel}>Cancelar</Text>
        </Pressable>
        <Text style={styles.headerTitle}>Recibo</Text>
        <View style={styles.headerSpacer} />
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {phase === 'choosing' ? (
        <>
          <Text style={styles.lead}>
            Fotografe o recibo e a gente lê o valor e o comerciante. Você confere antes de salvar.
          </Text>
          <Pressable style={styles.primaryButton} onPress={() => pick('camera')}>
            <Text style={styles.primaryButtonText}>Tirar foto</Text>
          </Pressable>
          <Pressable style={styles.secondaryButton} onPress={() => pick('library')}>
            <Text style={styles.secondaryButtonText}>Escolher das fotos</Text>
          </Pressable>
        </>
      ) : null}

      {imageUri ? <Image source={{ uri: imageUri }} style={styles.preview} /> : null}

      {phase === 'uploading' || phase === 'processing' ? (
        <View style={styles.busy}>
          <ActivityIndicator color="#e8a33d" />
          <Text style={styles.busyText}>
            {phase === 'uploading' ? 'Enviando a foto...' : 'Lendo o recibo...'}
          </Text>
        </View>
      ) : null}

      {phase === 'review' || phase === 'saving' ? (
        <>
          <Text style={styles.label}>Valor</Text>
          <View style={styles.amountField}>
            <Text style={styles.prefix}>R$</Text>
            <TextInput
              style={styles.amountInput}
              placeholder="0,00"
              placeholderTextColor="#5c626b"
              value={formatCents(cents)}
              onChangeText={(text) => setCents(extractDigits(text))}
              keyboardType="number-pad"
            />
          </View>

          <Text style={styles.label}>Onde</Text>
          <TextInput
            style={styles.input}
            placeholder="Mercado, posto, restaurante..."
            placeholderTextColor="#5c626b"
            value={merchant}
            onChangeText={setMerchant}
          />

          <Text style={styles.label}>Data</Text>
          {/* Seletor em vez de texto livre: a pessoa escreveria 05/08/2026 e
              o backend só aceita ISO. */}
          <Pressable style={styles.input} onPress={() => setPickingDate((open) => !open)}>
            <Text style={styles.inputText}>{isToday(date) ? 'Hoje' : formatShortDate(date)}</Text>
          </Pressable>
          {pickingDate ? (
            <View>
              <DateTimePicker
                value={date}
                mode="date"
                maximumDate={new Date()}
                onChange={(_event, selected) => {
                  if (selected) setDate(selected);
                  if (Platform.OS === 'android') setPickingDate(false);
                }}
              />
              {Platform.OS === 'ios' ? (
                <Pressable style={styles.pickerDone} onPress={() => setPickingDate(false)}>
                  <Text style={styles.pickerDoneText}>Pronto</Text>
                </Pressable>
              ) : null}
            </View>
          ) : null}

          <Text style={styles.label}>Categoria (obrigatória)</Text>
          {receipt?.extracted_payload?.category_hint ? (
            <Text style={styles.hint}>
              O leitor sugeriu: {receipt.extracted_payload.category_hint}
            </Text>
          ) : null}
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

          <Pressable
            style={[styles.primaryButton, !canConfirm && styles.buttonDisabled]}
            disabled={!canConfirm}
            onPress={handleConfirm}
          >
            <Text style={styles.primaryButtonText}>
              {phase === 'saving' ? 'Salvando...' : 'Confirmar e salvar'}
            </Text>
          </Pressable>
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    gap: 10,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
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
  lead: {
    fontSize: 13,
    color: '#8a8f98',
    lineHeight: 19,
    marginBottom: 8,
  },
  error: {
    color: '#d85a30',
    fontSize: 13,
  },
  preview: {
    width: '100%',
    height: 180,
    borderRadius: 10,
    resizeMode: 'cover',
  },
  busy: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 16,
  },
  busyText: {
    fontSize: 13,
    color: '#8a8f98',
  },
  label: {
    fontSize: 11,
    color: '#8a8f98',
    marginTop: 6,
  },
  hint: {
    fontSize: 11,
    color: '#5c626b',
  },
  amountField: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderWidth: 1,
    borderColor: '#262b33',
    borderRadius: 10,
    paddingHorizontal: 12,
  },
  prefix: {
    fontSize: 16,
    color: '#8a8f98',
  },
  amountInput: {
    flex: 1,
    paddingVertical: 12,
    fontSize: 20,
    fontWeight: '500',
  },
  input: {
    borderWidth: 1,
    borderColor: '#262b33',
    borderRadius: 10,
    paddingVertical: 11,
    paddingHorizontal: 12,
    fontSize: 14,
  },
  inputText: {
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
  chipText: {
    fontSize: 11,
    color: '#cfd3d9',
  },
  chipTextActive: {
    color: '#2a1c04',
  },
  primaryButton: {
    backgroundColor: '#e8a33d',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 10,
  },
  primaryButtonText: {
    color: '#2a1c04',
    fontSize: 14,
    fontWeight: '500',
  },
  secondaryButton: {
    borderWidth: 1,
    borderColor: '#262b33',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
  },
  secondaryButtonText: {
    fontSize: 14,
    color: '#cfd3d9',
  },
  buttonDisabled: {
    opacity: 0.45,
  },
});
