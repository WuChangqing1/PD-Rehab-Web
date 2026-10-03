import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import 'element-plus/dist/index.css'
import '@/styles/main.css'
// Loaded after main.css so the responsive overrides win without !important
// scattered through every page.
import '@/styles/responsive.css'

import App from '@/App.vue'
import router from '@/router'
import { setUnauthorizedHandler } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// When the backend rejects the token, clear local state and return to login.
setUnauthorizedHandler(() => {
  const auth = useAuthStore()
  auth.setToken(null)
  auth.user = null
  if (router.currentRoute.value.name !== 'login') {
    router.push({
      name: 'login',
      query: { redirect: router.currentRoute.value.fullPath },
    })
  }
})

app.mount('#app')
