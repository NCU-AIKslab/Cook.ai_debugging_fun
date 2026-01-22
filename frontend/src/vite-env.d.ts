/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_API_URL: string
    // 可以在這裡添加其他環境變數
}

interface ImportMeta {
    readonly env: ImportMetaEnv
}
