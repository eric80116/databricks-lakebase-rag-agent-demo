import Chat from './components/Chat'
import DevPanel from './components/DevPanel'

function App() {
  return (
    <div>
      <div className="header">
        <div className="header-content">
          <div className="header-title">Sentiva</div>
          <div className="header-subtitle">Digital safety, simplified.</div>
        </div>
      </div>
      <DevPanel />
      <Chat />
    </div>
  )
}

export default App
