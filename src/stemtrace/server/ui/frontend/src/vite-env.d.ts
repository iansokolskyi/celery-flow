/// <reference types="vite/client" />

declare global {
  interface Window {
    /** Base path injected by the server (e.g. "/stemtrace"). */
    __STEMTRACE_BASE__?: string
  }
}

export {}
