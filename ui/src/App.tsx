import { useEffect, useState } from 'react'
import { fetchPositions, sendInput, type Position } from './api'
import { InputPanel, type Exchange } from './components/InputPanel'
import { WorldView } from './components/WorldView'
import './App.css'

function App() {
  const [positions, setPositions] = useState<Position[]>([])
  const [history, setHistory] = useState<Exchange[]>([])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchPositions()
      .then(setPositions)
      .catch((e) => setError(String(e)))
  }, [])

  const handleSubmit = async (text: string) => {
    setPending(true)
    setError(null)
    try {
      const result = await sendInput(text)
      setHistory((h) => [...h, { input: text, response: result.response }])
      setPositions(result.positions)
    } catch (e) {
      setError(String(e))
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="app">
      <InputPanel history={history} pending={pending} onSubmit={handleSubmit} />
      <div className="world-pane">
        <WorldView positions={positions} />
        {error && <p className="error">{error}</p>}
      </div>
    </div>
  )
}

export default App
