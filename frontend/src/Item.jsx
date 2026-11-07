import React from 'react'
import { inr } from './api.js'
import { tr } from './i18n.js'

// One service in plain words: why it is here, what it does, what happens without it, what it costs a day,
// and how many similar businesses on Accel have it. The text comes from the server in the owner's language.
export default function ItemDetails({ lang, line, showWhy = true }) {
  const share = line.take_up >= 10 ? tr(lang, 'takeUpAll') : line.take_up ? tr(lang, 'takeUp', { n: line.take_up }) : ''
  return (
    <div className="item-more">
      {showWhy && line.why && <p><b>{tr(lang, 'forYou')}</b> {line.why}</p>}
      {line.does && <p>{line.does}</p>}
      {line.skip && <p className="skip">{line.skip}</p>}
      <p className="muted">{tr(lang, 'perDay', { amt: inr(line.per_day) })}{share ? ` · ${share}` : ''}</p>
    </div>
  )
}
