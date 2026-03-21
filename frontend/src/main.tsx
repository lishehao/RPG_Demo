import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
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
