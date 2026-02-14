import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
import {VitePWA} from 'vite-plugin-pwa'

export default defineConfig({
    base: '/Blacklist/',
    plugins: [
        vue(),
        // PWA 配置
        VitePWA({
            registerType: 'autoUpdate', // 自动更新 Service Worker
            includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'favicon-16x16.png', 'favicon-32x32.png'],
            manifest: {
                name: '黑名单管理中心',
                short_name: 'Shield Admin',
                description: '安全·高效·简洁的黑名单管理系统',
                theme_color: '#6366f1', // 与你项目的主题色(靛蓝)一致
                background_color: '#ffffff',
                display: 'standalone', // 类似原生 App 的体验
                icons: [
                    {
                        src: 'android-chrome-192x192.png',
                        sizes: '192x192',
                        type: 'image/png'
                    },
                    {
                        src: 'android-chrome-512x512.png',
                        sizes: '512x512',
                        type: 'image/png'
                    },
                    {
                        src: 'android-chrome-512x512.png', // 通常用最大的图标作为 maskable
                        sizes: '512x512',
                        type: 'image/png',
                        purpose: 'any maskable'
                    }
                ]
            },
            workbox: {
                // 缓存策略配置
                globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'], // 缓存静态资源
                runtimeCaching: []
            }
        })
    ],
    server: {
        host: "0.0.0.0",
        port: 8080,
        proxy: {
            '/blacklist-api': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
                ws: true,
                rewrite: (path) => path.replace(/^\/blacklist-api/, '')
            }
        }
    },
    // 构建配置
    build: {
        // 指定使用 terser 进行混淆压缩
        minify: 'terser',

        // Terser 详细配置
        terserOptions: {
            compress: {
                // 生产环境移除 console.log，防止调试信息泄露
                drop_console: true,
                // 移除 debugger 断点
                drop_debugger: true,
            },
            // 混淆变量名和函数名（默认已开启，这里显式写出来以便了解）
            mangle: true,
            format: {
                // 移除所有注释
                comments: false,
            },
        },

        rollupOptions: {
            output: {
                // 核心：手动分包配置
                manualChunks(id) {
                    if (id.includes('node_modules')) {
                        if (id.includes('naive-ui')) {
                            return 'naive-ui'
                        }
                        if (id.includes('echarts') || id.includes('zrender')) {
                            return 'echarts'
                        }
                        return 'vendor'
                    }
                },
                // 确保输出文件名包含 hash
                entryFileNames: `assets/[name].[hash].js`,
                chunkFileNames: `assets/[name].[hash].js`,
                assetFileNames: `assets/[name].[hash].[ext]`
            }
        }
    }
})
