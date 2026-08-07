// O client do Supabase é criado no import de lib/supabase.ts e recusa URL
// vazia, então qualquer teste que importe a cadeia da API quebraria na coleta.
// Valores fictícios: nenhum teste deve chamar a rede de verdade.
process.env.EXPO_PUBLIC_SUPABASE_URL = 'https://test.supabase.co';
process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key';
process.env.EXPO_PUBLIC_API_URL = 'http://localhost:8000';
