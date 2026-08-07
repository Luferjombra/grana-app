import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';

import {
  getNotifications,
  markNotificationRead,
  SEVERITY_COLORS,
  type Notification,
} from '../../lib/notifications';

export default function Notificacoes() {
  const [items, setItems] = useState<Notification[] | null>(null);
  const [failed, setFailed] = useState(false);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      getNotifications()
        .then((data) => {
          if (cancelled) return;
          setItems(data.items);
          setFailed(false);
        })
        .catch(() => {
          if (!cancelled) setFailed(true);
        });
      return () => {
        cancelled = true;
      };
    }, []),
  );

  async function handleRead(notification: Notification) {
    if (notification.read) return;

    // Marca na tela antes da resposta: o alerta já foi lido de fato, e
    // esperar a rede pra apagar o ponto deixaria o toque sem retorno.
    setItems(
      (current) =>
        current?.map((item) => (item.id === notification.id ? { ...item, read: true } : item)) ??
        null,
    );

    try {
      await markNotificationRead(notification.id);
    } catch {
      setItems(
        (current) =>
          current?.map((item) => (item.id === notification.id ? { ...item, read: false } : item)) ??
          null,
      );
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()}>
          <Text style={styles.back}>Voltar</Text>
        </Pressable>
        <Text style={styles.title}>Notificações</Text>
        <View style={styles.spacer} />
      </View>

      {failed ? <Text style={styles.error}>Não foi possível carregar os alertas.</Text> : null}

      {items && items.length === 0 ? (
        <Text style={styles.empty}>
          Nenhum alerta por enquanto. Avisamos quando um teto chegar perto do limite ou o mês
          estiver caminhando pro vermelho.
        </Text>
      ) : null}

      {items?.map((notification) => (
        <Pressable
          key={notification.id}
          style={[styles.item, notification.read && styles.itemRead]}
          onPress={() => handleRead(notification)}
        >
          <View
            style={[styles.stripe, { backgroundColor: SEVERITY_COLORS[notification.severity] }]}
          />
          <View style={styles.itemBody}>
            <Text style={styles.itemTitle}>{notification.title}</Text>
            <Text style={styles.itemMessage}>{notification.message}</Text>
          </View>
          {!notification.read ? <View style={styles.dot} /> : null}
        </Pressable>
      ))}
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
  back: {
    fontSize: 13,
    color: '#8a8f98',
  },
  title: {
    fontSize: 15,
    fontWeight: '500',
  },
  spacer: {
    width: 44,
  },
  error: {
    color: '#d85a30',
    fontSize: 13,
  },
  empty: {
    fontSize: 13,
    color: '#8a8f98',
    lineHeight: 19,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#1c2028',
    borderRadius: 10,
    padding: 12,
  },
  itemRead: {
    opacity: 0.55,
  },
  stripe: {
    width: 3,
    alignSelf: 'stretch',
    borderRadius: 2,
  },
  itemBody: {
    flex: 1,
    gap: 3,
  },
  itemTitle: {
    fontSize: 13,
    fontWeight: '500',
  },
  itemMessage: {
    fontSize: 12,
    color: '#8a8f98',
    lineHeight: 17,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: '#e8a33d',
  },
});
