import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import Icons from 'unplugin-icons/vite'
import IconsResolver from 'unplugin-icons/resolver'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // lucide 图标按需编译（模板中以 <i-lucide-xxx /> 使用）
    Icons({
      compiler: 'vue3',
      autoInstall: false,
      scale: 1,
    }),
    // Vue / Vue Router / Pinia / Element Plus 服务式 API 自动引入
    AutoImport({
      imports: ['vue', 'vue-router', 'pinia'],
      resolvers: [ElementPlusResolver()],
      dts: 'src/types/auto-imports.d.ts',
    }),
    // Element Plus 组件 + lucide 图标按需自动注册（样式随组件引入）
    Components({
      resolvers: [
        ElementPlusResolver(),
        IconsResolver({ prefix: 'i', enabledCollections: ['lucide'] }),
      ],
      dts: 'src/types/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // WebSocket 专用规则（更长前缀优先匹配，target 必须 ws:// 才能完成升级握手）
      '/api/console/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
      '/api/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
      // 业务 REST 接口 → FastAPI
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // 兼容裸 /ws 通道
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
