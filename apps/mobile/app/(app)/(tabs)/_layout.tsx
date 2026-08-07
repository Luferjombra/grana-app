import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

/**
 * Só as abas que têm dado de verdade por trás. Insights e Metas entram
 * quando os endpoints delas existirem — aba vazia com "em breve" seria
 * prometer o que o app ainda não faz.
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
    </Tabs>
  );
}
