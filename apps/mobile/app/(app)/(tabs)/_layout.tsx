import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

/**
 * Só as abas que têm dado de verdade por trás — aba vazia com "em breve" seria
 * prometer o que o app não faz.
 *
 * Insights entrou quando os 5 endpoints dela passaram a existir. **Metas segue
 * fora**: os três endpoints de gamificação ainda são `NotImplementedError`, e a
 * regra de XP depende de decisão de produto.
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
    </Tabs>
  );
}
