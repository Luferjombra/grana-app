// O client do Supabase é criado no import de lib/supabase.ts e recusa URL
// vazia, então qualquer teste que importe a cadeia da API quebraria na coleta.
// Valores fictícios: nenhum teste deve chamar a rede de verdade.
process.env.EXPO_PUBLIC_SUPABASE_URL = 'https://test.supabase.co';
process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key';
process.env.EXPO_PUBLIC_API_URL = 'http://localhost:8000';

// Sem módulo nativo, o AsyncStorage derruba o processo assim que o Supabase
// tenta restaurar a sessão no import. Storage em memória resolve, e o pacote
// não traz mock próprio nesta versão.
jest.mock('@react-native-async-storage/async-storage', () => {
  const store = new Map();
  return {
    __esModule: true,
    default: {
      getItem: (key) => Promise.resolve(store.get(key) ?? null),
      setItem: (key, value) => {
        store.set(key, value);
        return Promise.resolve();
      },
      removeItem: (key) => {
        store.delete(key);
        return Promise.resolve();
      },
      clear: () => {
        store.clear();
        return Promise.resolve();
      },
    },
  };
});
