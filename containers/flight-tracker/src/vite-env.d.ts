/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Base URL of the backend API. Set to "/api" in the Docker build. When
  // unset, the app runs in local-only mode (browser storage, no backend).
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
