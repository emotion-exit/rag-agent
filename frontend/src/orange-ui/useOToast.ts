import { inject, ref, type InjectionKey, type Ref } from 'vue';

export type OToastTone = 'success' | 'error' | 'warning' | 'info';

export interface OToastItem {
  id: number;
  title?: string;
  message: string;
  tone: OToastTone;
  duration: number;
}

export interface OToastApi {
  items: Ref<OToastItem[]>;
  push: (toast: Partial<OToastItem> & { message: string }) => number;
  success: (message: string, title?: string) => number;
  error: (message: string, title?: string) => number;
  warning: (message: string, title?: string) => number;
  info: (message: string, title?: string) => number;
  remove: (id: number) => void;
  clear: () => void;
}

export const orangeToastKey = Symbol('orange-toast') as InjectionKey<OToastApi>;

let toastSeed = 0;

export function createOToastApi(): OToastApi {
  const items = ref<OToastItem[]>([]);

  function remove(id: number) {
    items.value = items.value.filter((item) => item.id !== id);
  }

  function push(toast: Partial<OToastItem> & { message: string }) {
    const id = ++toastSeed;
    const nextItem: OToastItem = {
      id,
      title: toast.title,
      message: toast.message,
      tone: toast.tone || 'info',
      duration: toast.duration ?? 2800
    };

    items.value = [...items.value, nextItem];

    if (nextItem.duration > 0) {
      window.setTimeout(() => remove(id), nextItem.duration);
    }

    return id;
  }

  return {
    items,
    push,
    success(message, title) {
      return push({ message, title, tone: 'success' });
    },
    error(message, title) {
      return push({ message, title, tone: 'error' });
    },
    warning(message, title) {
      return push({ message, title, tone: 'warning' });
    },
    info(message, title) {
      return push({ message, title, tone: 'info' });
    },
    remove,
    clear() {
      items.value = [];
    }
  };
}

export function useOToast() {
  const api = inject(orangeToastKey, null);

  if (!api) {
    throw new Error('useOToast 必须在 OConfigProvider 内部使用');
  }

  return api;
}
