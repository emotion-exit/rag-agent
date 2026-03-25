import { createRouter, createWebHistory } from 'vue-router';
import { hasAuthSession } from '@/services/auth';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: {
        public: true
      }
    },
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

router.beforeEach((to) => {
  const isPublicRoute = Boolean(to.meta.public);
  const authenticated = hasAuthSession();

  if (!isPublicRoute && !authenticated) {
    return {
      name: 'login',
      query: {
        redirect: to.fullPath
      }
    };
  }

  if (isPublicRoute && authenticated && to.name === 'login') {
    return { name: 'chat' };
  }

  return true;
});

export default router;
