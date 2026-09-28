import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 개발할 때만 쓰는 설정. 평소에는 ./studio 가 빌드된 화면을 서버에서 바로 내보낸다.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:7870' } },
})
