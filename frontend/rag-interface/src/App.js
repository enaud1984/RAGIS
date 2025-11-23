import React, { useState, useRef, useEffect } from "react";
import "./App.css";

// Frontend semplice per la chat RAG
// - effettua login usando l'endpoint `/login`
// - salva token/ruolo in localStorage
// - invia Authorization header alle chiamate protette

const API_BASE = "http://127.0.0.1:8000";

function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!username || !password) {
      setError("Inserisci username e password");
      return;
    }

    setLoading(true);
    try {
      // Chiamata al backend per autenticare
      const res = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!res.ok) {
        if (res.status === 401) setError("Credenziali non valide");
        else setError(`Errore login: ${res.status}`);
        setLoading(false);
        return;
      }

      const data = await res.json();
      // data: { token, username, ruolo }
      const ruolo = data.ruolo || "";
      const isAdmin = ruolo.toLowerCase() === "admin"; // admin se ruolo == 'admin'

      // Salva sessione (token e ruolo) nel localStorage
      const user = { username: data.username || username, isAdmin, token: data.token, ruolo };
      localStorage.setItem("rag_user", JSON.stringify(user));
      onLogin(user); // avvisa l'app che l'utente è loggato
    } catch (err) {
      console.error("Login error", err);
      setError("Errore connessione al server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <h2>Login</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={loading}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading}>{loading ? "Accedo..." : "Accedi"}</button>
        {error && <div className="status">{error}</div>}
      </form>
    </div>
  );
}

function App() {
  const [user, setUser] = useState(null); // {username, isAdmin, token, ruolo}
  const [searchMode, setSearchMode] = useState({ local: false, online: false });
  const [promptUtente, setPromptUtente] = useState("");
  const [chatMessages, setChatMessages] = useState([
    { sender: "system", text: "Benvenuto nella chat RAG!" },
  ]);
  const [statusMessage, setStatusMessage] = useState("");
  const [reindexing, setReindexing] = useState(false);
  const textareaRef = useRef(null);

  // State per il form di creazione utenti (solo admin)
  const [showNewUserForm, setShowNewUserForm] = useState(false);
  const [newUserData, setNewUserData] = useState({ username: "", password: "" });
  const [newUserLoading, setNewUserLoading] = useState(false);
  const [newUserError, setNewUserError] = useState("");

  // Load persisted session
  useEffect(() => {
    // Al caricamento dell'app prova a leggere la sessione salvata
    const raw = localStorage.getItem("rag_user");
    if (raw) {
      try {
        setUser(JSON.parse(raw));
      } catch (e) {
        console.warn("Invalid stored user", e);
      }
    }
  }, []);

  const handleCheckboxChange = (e) => {
    const { name, checked } = e.target;
    setSearchMode((prev) => ({ ...prev, [name]: checked }));
  };

  const handleSendPrompt = async () => {
    if (reindexing) {
      setStatusMessage("Attendere: reindicizzazione in corso...");
      return;
    }
    if (promptUtente.trim() !== "") {
      try {
        setStatusMessage("Invio richiesta...");
        // Prepara headers: include token se disponibile
        const headers = { "Content-Type": "application/json" };
        if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;

        // Chiamata al servizio RAG
        const response = await fetch(`${API_BASE}/chat/`, {
          method: "POST",
          headers,
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
    // backend expects a `files` list parameter
    formData.append("files", file);

    try {
      setStatusMessage("Caricamento documento...");
      const headers = {};
      if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;

      const response = await fetch(`${API_BASE}/upload/`, {
        method: "POST",
        headers,
        body: formData,
      });
      const data = await response.json();
      // backend currently uses "messagio" in response in main.py; support both
      setStatusMessage(data.message || data.messagio || "Documento caricato.");
    } catch (error) {
      console.error("Errore upload:", error);
      setStatusMessage("Errore nel caricamento.");
    }
  };

  const handleReindex = async () => {
    try {
      setReindexing(true);
      setStatusMessage("Indicizzazione in corso...");
      // Solo admin dovrebbe chiamare questo endpoint
      const headers = {};
      if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;
      const response = await fetch(`${API_BASE}/reindex/`, { headers });
      const data = await response.json();
      setStatusMessage(data.message || "Indicizzazione completata.");
    } catch (error) {
      console.error("Errore reindex:", error);
      setStatusMessage("Errore nella reindicizzazione.");
    } finally {
      setReindexing(false);
    }
  };

  const handleLogout = () => {
    // Rimuove sessione e resetta UI
    localStorage.removeItem("rag_user");
    setUser(null);
    setChatMessages([{ sender: "system", text: "Benvenuto nella chat RAG!" }]);
    setStatusMessage("");
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setNewUserError("");

    // Validazione
    if (!newUserData.username || !newUserData.password) {
      setNewUserError("Inserisci username e password");
      return;
    }

    setNewUserLoading(true);
    try {
      // Chiama endpoint /registrazione con ruolo fisso "Collaboratore"
      const headers = { "Content-Type": "application/json" };
      if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;

      const response = await fetch(`${API_BASE}/registrazione`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          username: newUserData.username,
          password: newUserData.password,
          ruolo: "Collaboratore", // Ruolo fisso per nuovi utenti
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setNewUserError(data.detail || "Errore nella creazione dell'utente");
        setNewUserLoading(false);
        return;
      }

      // Successo
      setStatusMessage("Utente creato con successo!");
      setNewUserData({ username: "", password: "" });
      setShowNewUserForm(false);
    } catch (err) {
      console.error("Errore creazione utente:", err);
      setNewUserError("Errore connessione al server");
    } finally {
      setNewUserLoading(false);
    }
  };

  // Textarea dinamica
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      const maxHeight = 3 * 24 + 12;
      el.style.height = Math.min(el.scrollHeight, maxHeight) + "px";
    }
  }, [promptUtente]);

  if (!user) {
    return <Login onLogin={setUser} />;
  }

  return (
    <div className="container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="top-section">
          <div className="logo">
            <img src="/ragis-logo.png" className="logo-img" />
          </div>

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
        </div>

        <div className="bottom-section">
          {user && user.isAdmin && (
            <>
              <button onClick={handleReindex}>Ricostruisci DB</button>
              <label htmlFor="file-upload-sidebar" className="upload-doc-btn">
                Aggiungi documento al DB
              </label>
              <button onClick={() => setShowNewUserForm(!showNewUserForm)} className="add-user-btn">
                Aggiungi Utente
              </button>
            </>
          )}
          {!user?.isAdmin && user && (
            <label htmlFor="file-upload-sidebar" className="upload-doc-btn">
              Aggiungi documento al DB
            </label>
          )}
          <input
            id="file-upload-sidebar"
            type="file"
            onChange={handleUploadDocument}
            style={{ display: "none" }}
          />
          <div className="account">Account: {user ? user.username : "-"}</div>
          {user && (
            <button onClick={handleLogout} className="logout-btn">
              Logout
            </button>
          )}
        </div>
      </aside>

      {/* Form creazione nuovo utente (solo per admin, visibile quando showNewUserForm è true) */}
      {user && user.isAdmin && showNewUserForm && (
        <div className="overlay">
          <div className="dialog new-user-dialog">
            <h3>Crea nuovo utente</h3>
            <form onSubmit={handleCreateUser}>
              <input
                type="text"
                placeholder="Username"
                value={newUserData.username}
                onChange={(e) => setNewUserData({ ...newUserData, username: e.target.value })}
                disabled={newUserLoading}
              />
              <input
                type="password"
                placeholder="Password"
                value={newUserData.password}
                onChange={(e) => setNewUserData({ ...newUserData, password: e.target.value })}
                disabled={newUserLoading}
              />
              <p className="role-info">Ruolo: <strong>Collaboratore</strong> (fisso)</p>
              {newUserError && <div className="status error">{newUserError}</div>}
              <div className="dialog-buttons">
                <button type="submit" disabled={newUserLoading}>
                  {newUserLoading ? "Creazione..." : "Crea"}
                </button>
                <button type="button" onClick={() => setShowNewUserForm(false)} disabled={newUserLoading}>
                  Annulla
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Main */}
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

        {/* Prompt utente */}
        <div className="prompt-wrapper">
          <div className="input-container">
            <label htmlFor="file-upload" className="icon-button">+</label>
            <input
              id="file-upload"
              type="file"
              onChange={handleUploadDocument}
              style={{ display: "none" }}
            />
            <textarea
              ref={textareaRef}
              className="chat-input"
              value={promptUtente}
              onChange={(e) => setPromptUtente(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendPrompt();
                }
              }}
              placeholder="Scrivi il tuo messaggio..."
              rows={1}
            />
            <button className="icon-button send" onClick={handleSendPrompt}>
              Invia
            </button>
          </div>
        </div>

        <footer className="footer">AI system rilasciato da RAGIS group</footer>
        {statusMessage && <div className="status">{statusMessage}</div>}
      </main>

      {/* Dialogo reindex */}
      {reindexing && (
        <div className="overlay">
          <div className="dialog">
            <h3>Reindicizzazione in corso...</h3>
            <p>Attendere il completamento prima di usare nuovamente la chat.</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;