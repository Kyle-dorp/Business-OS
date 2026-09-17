import React from 'react'
import ReactDOM from 'react-dom/client'
// Explicit extension: App.jsx and App.tsx both existed once, and Vite resolves
// .jsx before .tsx, so every build silently compiled the wrong one. Naming the
// file removes the ambiguity permanently.
import App from './App.jsx'
// index.css is deliberately not imported. It was the pre-redesign Tailwind
// stylesheet, and because it loaded after App.jsx's theme files it won every
// tie — painting `body` #F9FAFB with #111827 text and a system font stack,
// directly over a design system built for a warm near-black. The sign-in card
// rendered cream-on-white and read as unstyled. The live app uses no Tailwind
// utility classes at all.

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
