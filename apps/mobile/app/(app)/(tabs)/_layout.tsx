import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

/**
 * Só as abas que têm dado de verdade por trás — aba vazia com "em breve" seria
 * prometer o que o app não faz.
 *
 * Insights entrou quando os 5 endpoints dela passaram a existir.
 *
 * Metas entrou depois, e **não** com gamificação: ela nunca precisou da regra de
 * XP, precisava de uma meta. A reserva de emergência já era uma (tem alvo,
 * progresso e prazo implícito) e estava construída sem ter onde morar — criada no
 * onboarding e invisível desde então, com o alerta de marco sem destino. XP e
 * conquistas entram como segunda seção quando a regra for decidida.
 */
export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: '#e8a33d',
        tabBarInactiveTintColor: '#8a8f98',
        tabBarStyle: { backgroundColor: '#14171c', borderTopColor: '#262b33' },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Início',
          tabBarIcon: ({ color, size }) => <Ionicons name="home" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="atividade"
        options={{
          title: 'Atividade',
          tabBarIcon: ({ color, size }) => <Ionicons name="list" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="insights"
        options={{
          title: 'Insights',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="trending-up" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="metas"
        options={{
          title: 'Metas',
          tabBarIcon: ({ color, size }) => <Ionicons name="flag" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
