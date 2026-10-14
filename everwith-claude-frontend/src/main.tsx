import {StrictMode} from 'react'
import {createRoot} from 'react-dom/client'
import './styles/base.css'
import './styles/shell.css'
import './styles/pages.css'
import './styles/chat.css'
import './styles/stage.css'
import './styles/games.css'
import './styles/story.css'
import {App} from './app/App'

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
