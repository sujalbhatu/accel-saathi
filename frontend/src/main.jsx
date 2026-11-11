import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import Console from './Console.jsx'
import WhatsApp from './WhatsApp.jsx'
import { rememberReferral } from './api.js'
// One type family for all ten languages (Anek, by Ek Type). Each script's file is fetched only when its letters appear.
import '@fontsource-variable/anek-latin/wght.css'
import '@fontsource-variable/anek-devanagari/wght.css'
import '@fontsource-variable/anek-bangla/wght.css'
import '@fontsource-variable/anek-gujarati/wght.css'
import '@fontsource-variable/anek-gurmukhi/wght.css'
import '@fontsource-variable/anek-kannada/wght.css'
import '@fontsource-variable/anek-malayalam/wght.css'
import '@fontsource-variable/anek-tamil/wght.css'
import '@fontsource-variable/anek-telugu/wght.css'
import './styles.css'

rememberReferral()

function Root() {
  const [hash, setHash] = React.useState(window.location.hash)
  React.useEffect(() => {
    const on = () => setHash(window.location.hash)
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  if (hash.startsWith('#/console')) { document.body.className = 'console'; return <Console /> }
  if (hash.startsWith('#/whatsapp')) { document.body.className = 'whatsapp'; return <WhatsApp /> }
  document.body.className = 'customer'
  return <App hash={hash} />
}

createRoot(document.getElementById('root')).render(<Root />)
