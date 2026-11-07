import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import Console from './Console.jsx'
import WhatsApp from './WhatsApp.jsx'
import { rememberReferral } from './api.js'
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
