import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "@fontsource/inter/latin-300.css"
import "@fontsource/inter/latin-400.css"
import "@fontsource/inter/latin-500.css"
import "@fontsource/inter/latin-600.css"
import "@fontsource/inter/latin-700.css"
import "@fontsource/newsreader/latin-400.css"
import "@fontsource/newsreader/latin-400-italic.css"
import "@fontsource/space-grotesk/latin-300.css"
import "@fontsource/space-grotesk/latin-400.css"
import "@fontsource/space-grotesk/latin-500.css"
import "@fontsource/space-grotesk/latin-700.css"
import App from "./app/app"
import "./app/styles.css"

const rootElement = document.getElementById("root")

if (!rootElement) {
  throw new Error("Unable to find root element")
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
