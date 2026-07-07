import { useState, type FormEvent } from 'react'

export interface Exchange {
  input: string
  response: string | null
}

interface Props {
  history: Exchange[]
  pending: boolean
  onSubmit: (text: string) => void
}

export function InputPanel({ history, pending, onSubmit }: Props) {
  const [text, setText] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || pending) return
    onSubmit(trimmed)
    setText('')
  }

  return (
    <div className="input-panel">
      <div className="history">
        {history.map((exchange, i) => (
          <div className="exchange" key={i}>
            <p className="player-line">&gt; {exchange.input}</p>
            {exchange.response && <p className="world-line">{exchange.response}</p>}
          </div>
        ))}
        {pending && <p className="pending-line">...</p>}
      </div>
      <form className="input-form" onSubmit={handleSubmit}>
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="What do you do?"
          disabled={pending}
          autoFocus
        />
        <button type="submit" disabled={pending || !text.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}
