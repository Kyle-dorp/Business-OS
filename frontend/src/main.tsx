import React from 'react'
import ReactDOM from 'react-dom/client'
// Explicit extension: App.jsx and App.tsx both existed once, and Vite resolves
// .jsx before .tsx, so every build silently compiled the wrong one. Naming the
// file removes the ambiguity permanently.
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
