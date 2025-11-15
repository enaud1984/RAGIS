import React, { useState } from "react";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

function App() {
  const [searchMode, setSearchMode] = useState({ local: false, online: false });
  const [promptUtente, setPromptUtente] = useState("");
  const [chatMessages, setChatMessages] = useState([
    { sender: "system", text: "Benvenuto nella chat RAG!" },
  ]);
  const [statusMessage, setStatusMessage] = useState("");

  const handleCheckboxChange = (e) => {
    const { name, checked } = e.target;
    setSearchMode((prev) => ({ ...prev, [name]: checked }));
  };

  const handleSendPrompt = async () => {
    if (promptUtente.trim() !== "") {
      try {
        setStatusMessage("Invio richiesta...");
        const response = await fetch(`${API_BASE}/chat/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: promptUtente }),
        });
        const data = await response.json();

        setChatMessages((prev) => [
          ...prev,
          { sender: "utente", text: promptUtente },
          { sender: "RAG", text: data.answer || "Errore nella risposta" },
        ]);
        setPromptUtente("");
        setStatusMessage("Risposta ricevuta.");
      } catch (error) {
        console.error("Errore:", error);
        setStatusMessage("Errore nella richiesta.");
      }
    }
  };

  const handleUploadDocument = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      setStatusMessage("Caricamento documento...");
      const response = await fetch(`${API_BASE}/upload/`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      setStatusMessage(data.message || "Documento caricato.");
    } catch (error) {
      console.error("Errore upload:", error);
      setStatusMessage("Errore nel caricamento.");
    }
  };

  const handleReindex = async () => {
    try {
      setStatusMessage("Indicizzazione in corso...");
      const response = await fetch(`${API_BASE}/reindex/`);
      const data = await response.json();
      setStatusMessage(data.message || "Indicizzazione completata.");
    } catch (error) {
      console.error("Errore reindex:", error);
      setStatusMessage("Errore nella reindicizzazione.");
    }
  };

  const handleDebugDB = async () => {
    try {
      const response = await fetch(`${API_BASE}/debug_db/`);
      const data = await response.json();
      alert(`Documenti nel DB: ${data.documenti}`);
    } catch (error) {
      console.error("Errore debug DB:", error);
    }
  };

  return (
    <div className="container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="logo">LOGO</div>
        <div className="search-options">
          <label>
            <input
              type="checkbox"
              name="local"
              checked={searchMode.local}
              onChange={handleCheckboxChange}
            />
            Ricerca - Solo locale
          </label>
          <label>
            <input
              type="checkbox"
              name="online"
              checked={searchMode.online}
              onChange={handleCheckboxChange}
            />
            Ricerca - Locale + Online
          </label>
        </div>
        <div className="chat-log">LOG vecchie chat</div>

        <input
          type="file"
          onChange={handleUploadDocument}
          style={{ marginBottom: "10px" }}
        />
        <button onClick={handleReindex}>Ricostruisci DB</button>
        <button onClick={handleDebugDB}>Debug DB</button>

        <div className="account">Account Loggato</div>
      </aside>

      {/* Main content */}
      <main className="main">
        <div className="chat-area">
          <div className="chat">
            <div className="chat-messages">
              {chatMessages.map((msg, index) => (
                <div
                  key={index}
                  className={`message ${msg.sender === "utente" ? "user" : "rag"}`}
                >
                  <strong>{msg.sender}:</strong> {msg.text}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Prompt utente in basso */}
        <div className="prompt-utente">
          <textarea
            value={promptUtente}
            onChange={(e) => setPromptUtente(e.target.value)}
            placeholder="Scrivi il tuo messaggio..."
          />
          <button onClick={handleSendPrompt}>Invia</button>
        </div>

        <footer className="footer">AI system rilasciato da RAGIS group</footer>
        {statusMessage && <div className="status">{statusMessage}</div>}
      </main>
    </div>
  );
}

export default App;
