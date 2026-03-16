import { createRouter, createWebHistory } from 'vue-router';
import { shouldRedirectToSettingsOnDesktop } from '@/services/runtime';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: () => import('../views/ChatView.vue'),
      meta: {
        keepAlive: true,
        keepAliveName: 'ChatView'
      }
    },
    {
      path: '/knowledge-base',
      name: 'knowledge-base',
      component: () => import('../views/KnowledgeBaseView.vue'),
      meta: {
        keepAlive: true,
        keepAliveName: 'KnowledgeBaseView'
      }
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue')
    }
  ]
});

router.beforeEach(async (to) => {
  if (to.name === 'settings') {
    return true;
  }

  const shouldRedirect = await shouldRedirectToSettingsOnDesktop();
  if (!shouldRedirect) {
    return true;
  }

  return {
    name: 'settings',
    query: {
      setup: 'required'
    }
  };
});

export default router;
