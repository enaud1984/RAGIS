import React, { useState, useRef, useEffect } from "react";
import "./App.css";
import LoaderBubble from "./LoaderBubble";

// Frontend semplice per la chat RAG
// - effettua login usando l'endpoint `/login`
// - salva token/ruolo in localStorage
// - invia Authorization header alle chiamate protette

//const API_BASE = "http://127.0.0.1:8000";
 const API_BASE = `http://${window.location.hostname}:8000`;

// Funzione per formattare markdown con grassetto
function formatMarkdown(text) {
  if (!text) return "";
  
  // Converti **testo** o __testo__ in grassetto
  let formatted = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  formatted = formatted.replace(/__(.*?)__/g, '<strong>$1</strong>');
  
  // Identifica e metti in grassetto pattern comuni:
  // - Numeri seguiti da punto (es. "1.", "2.", "3.")
  formatted = formatted.replace(/(\d+\.\s)/g, '<strong>$1</strong>');
  
  // - Parole che iniziano con maiuscola seguite da due punti (es. "Verbale:", "Data:")
  formatted = formatted.replace(/([A-Z][a-z\u00C0-\u00FF]+:)/g, '<strong>$1</strong>');
  
  // - Date nel formato YYYY-MM-DD
  formatted = formatted.replace(/(\d{4}-\d{2}-\d{2})/g, '<strong>$1</strong>');
  
  // - Percorsi file (es. D:\RAGIS\...)
  formatted = formatted.replace(/([A-Z]:\\[^\s<]+)/g, '<strong>$1</strong>');
  
  // Converti a capo in <br>
  formatted = formatted.replace(/\n/g, '<br>');
  
  return formatted;
}

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
      <div className="login-logo">
        <img src="/ragis-logo.png" alt="RAGIS Logo" className="logo-img" />
      </div>
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
  const [chatMessages, setChatMessages] = useState([]);
  const [statusMessage, setStatusMessage] = useState("");
  const [reindexing, setReindexing] = useState(false);
  const [showParamsPanel, setShowParamsPanel] = useState(false);
  const [modelParams, setModelParams] = useState({
    llm_model: "mistral:latest",
    embed_model: "intfloat/e5-large-v2",
    chunk_size: "1500",
    chunk_overlap: "200",
    top_k: "8",
    distance_threshold: "0.6"
  });
  const [defaultParams, setDefaultParams] = useState(null);
  const [llmModels, setLlmModels] = useState([]);
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [downloadingModel, setDownloadingModel] = useState(false);

  // Valori di default hardcoded per il reset
  const HARDCODED_DEFAULTS = {
    llm_model: "mistral:latest",
    embed_model: "intfloat/e5-large-v2",
    chunk_size: "1500",
    chunk_overlap: "200",
    top_k: "8",
    distance_threshold: "0.6"
  };
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const textareaRef = useRef(null);
  const chatMessagesRef = useRef(null);
  const [shouldSaveChat, setShouldSaveChat] = useState(false);

  // State per il form di creazione utenti (solo admin)
  const [showNewUserForm, setShowNewUserForm] = useState(false);
  const [newUserData, setNewUserData] = useState({ username: "", password: "", ruolo: "Collaboratore" });
  const [newUserLoading, setNewUserLoading] = useState(false);
  const [newUserError, setNewUserError] = useState("");

  // State per gestione utenti
  const [showUsersList, setShowUsersList] = useState(false);
  const [usersList, setUsersList] = useState([]);
  const [usersListLoading, setUsersListLoading] = useState(false);
  const [showEditUserForm, setShowEditUserForm] = useState(false);
  const [editUserData, setEditUserData] = useState({ id: null, username: "", password: "", ruolo: "Collaboratore" });
  const [editUserLoading, setEditUserLoading] = useState(false);
  const [editUserError, setEditUserError] = useState("");

  // State per categorie espandibili sidebar
  const [openCategory, setOpenCategory] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [currentChatId, setCurrentChatId] = useState(Date.now());

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

  // Carica i parametri dal DB quando l'utente è admin e apre il pannello
  useEffect(() => {
    if (user && user.isAdmin && showParamsPanel && !defaultParams) {
      loadCurrentParams();
      loadLlmModels();
    }
  }, [user, showParamsPanel]);

  // Carica i parametri del modello per tutti gli utenti all'avvio
  useEffect(() => {
    if (user && user.token) {
      loadCurrentParams();
      loadLlmModels(); // Carica anche la lista dei modelli
    }
  }, [user]);

  // Carica cronologia chat dal localStorage
  useEffect(() => {
    const loadChatHistory = () => {
      const stored = localStorage.getItem('chatHistory');
      if (stored) {
        const history = JSON.parse(stored);
        // Filtra chat più vecchie di 48h
        const now = Date.now();
        const filtered = history.filter(chat => (now - chat.timestamp) < 48 * 60 * 60 * 1000);
        setChatHistory(filtered);
        // Aggiorna localStorage con solo le chat valide
        localStorage.setItem('chatHistory', JSON.stringify(filtered));
      }
    };
    loadChatHistory();
  }, []);

  // Salva automaticamente la chat quando i messaggi cambiano E shouldSaveChat è true
  useEffect(() => {
    if (chatMessages.length > 0 && !isLoading && shouldSaveChat) {
      const timer = setTimeout(() => {
        // Salva la chat corrente
        const firstUserMessage = chatMessages.find(msg => msg.sender === "utente");
        const preview = firstUserMessage 
          ? firstUserMessage.text.substring(0, 50) + (firstUserMessage.text.length > 50 ? '...' : '')
          : 'Chat senza messaggi';
        
        const chatToSave = {
          id: currentChatId,
          timestamp: Date.now(), // Aggiorna sempre il timestamp ad ora
          preview: preview,
          messages: chatMessages
        };
        
        // Carica la cronologia corrente dal localStorage
        const stored = localStorage.getItem('chatHistory');
        const currentHistory = stored ? JSON.parse(stored) : [];
        
        // Controlla se questa chat esiste già
        const existingIndex = currentHistory.findIndex(chat => chat.id === currentChatId);
        let updatedHistory;
        
        if (existingIndex >= 0) {
          // Aggiorna la chat esistente
          updatedHistory = [...currentHistory];
          updatedHistory[existingIndex] = chatToSave;
        } else {
          // Aggiungi nuova chat
          updatedHistory = [chatToSave, ...currentHistory].slice(0, 20); // Max 20 chat
        }
        
        // Salva nel localStorage e aggiorna lo stato
        localStorage.setItem('chatHistory', JSON.stringify(updatedHistory));
        setChatHistory(updatedHistory);
        setShouldSaveChat(false); // Reset flag
      }, 500); // Debounce di 500ms per evitare troppi salvataggi
      
      return () => clearTimeout(timer);
    }
  }, [chatMessages, isLoading, currentChatId, shouldSaveChat]);

  // Scroll automatico verso il basso quando i messaggi cambiano
  useEffect(() => {
    if (chatMessagesRef.current) {
      // Usa setTimeout per assicurarsi che il DOM sia aggiornato
      setTimeout(() => {
        if (chatMessagesRef.current) {
          chatMessagesRef.current.scrollTop = chatMessagesRef.current.scrollHeight;
        }
      }, 100);
    }
  }, [chatMessages]);

  const loadCurrentParams = async () => {
    try {
      const headers = {};
      if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;
      
      const response = await fetch(`${API_BASE}/get_parameters`, { headers });
      if (response.ok) {
        const data = await response.json();
        const params = {
          llm_model: data.llm_model || "mistral",
          embed_model: data.embed_model || "intfloat/e5-large-v2",
          chunk_size: String(data.chunk_size || 1500),
          chunk_overlap: String(data.chunk_overlap || 200),
          top_k: String(data.top_k || 8),
          distance_threshold: String(data.distance_threshold || 0.6)
        };
        setModelParams(params);
        setDefaultParams(params);
      }
    } catch (err) {
      console.error("Errore caricamento parametri:", err);
    }
  };

  const loadLlmModels = async () => {
    try {
      const headers = {};
      if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;
      
      const response = await fetch(`${API_BASE}/get_models`, { headers });
      if (response.ok) {
        const data = await response.json();
        if (data.models && Array.isArray(data.models)) {
          setLlmModels(data.models);
        }
      }
    } catch (err) {
      console.error("Errore caricamento modelli LLM:", err);
      // Fallback a lista base in caso di errore
      setLlmModels(["mistral:latest", "qwen2.5:latest", "gemma2:2b"]);
    }
  };

  const handleResetParams = () => {
    setModelParams({ ...HARDCODED_DEFAULTS });
    setStatusMessage("Parametri ripristinati ai valori di default");
    // Salva automaticamente i parametri resettati
    saveResetParams(HARDCODED_DEFAULTS);
  };

  const saveResetParams = async (params) => {
    try {
      const headers = { "Content-Type": "application/json" };
      if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;
      
      const body = {};
      if (params.llm_model && params.llm_model.trim() !== "") 
        body.llm_model = params.llm_model.trim();
      if (params.embed_model && params.embed_model.trim() !== "") 
        body.embed_model = params.embed_model.trim();
      if (params.chunk_size && params.chunk_size !== "") 
        body.chunk_size = parseInt(params.chunk_size);
      if (params.chunk_overlap && params.chunk_overlap !== "") 
        body.chunk_overlap = parseInt(params.chunk_overlap);
      if (params.top_k && params.top_k !== "") 
        body.top_k = parseInt(params.top_k);
      if (params.distance_threshold && params.distance_threshold !== "") 
        body.distance_threshold = parseFloat(params.distance_threshold);
      
      const response = await fetch(`${API_BASE}/save_parameters`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      
      if (response.ok) {
        const data = await response.json();
        setStatusMessage("Parametri ripristinati e salvati con successo");
      }
    } catch (err) {
      console.error("Errore salvataggio reset:", err);
    }
  };

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
      const currentPrompt = promptUtente;
      setPromptUtente(""); // Svuota immediatamente la barra
      setShowSuggestions(false); // Nascondi suggerimenti
      setIsLoading(true);
      
      try {
        setStatusMessage("Invio richiesta...");
        // Inserisci subito il messaggio utente e un placeholder di buffering
        let placeholderIndex = -1;
        setChatMessages((prev) => {
          const next = [
            ...prev,
            { sender: "utente", text: currentPrompt },
            { sender: "RAGIS", text: "", loading: true },
          ];
          placeholderIndex = next.length - 1; // indice del placeholder appena aggiunto
          return next;
        });

        // Prepara headers: include token se disponibile
        const headers = { "Content-Type": "application/json" };
        if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;

        // Chiamata al servizio RAG
        const response = await fetch(`${API_BASE}/chat/`, {
          method: "POST",
          headers,
          body: JSON.stringify({ prompt: currentPrompt }),
        });
        const data = await response.json();

        // Sostituisci il placeholder con la risposta finale
        setChatMessages((prev) => {
          const next = [...prev];
          // Trova l'ultimo placeholder loading dal fondo se l'indice non è affidabile
          let idx = placeholderIndex;
          if (idx < 0 || !next[idx]?.loading) {
            for (let i = next.length - 1; i >= 0; i--) {
              if (next[i].sender === "RAGIS" && next[i].loading) {
                idx = i;
                break;
              }
            }
          }
          if (idx >= 0) {
            next[idx] = { sender: "RAGIS", text: data.answer || "Errore nella risposta", loading: false };
          } else {
            // fallback: aggiungi risposta in coda
            next.push({ sender: "RAGIS", text: data.answer || "Errore nella risposta", loading: false });
          }
          
          return next;
        });
        setStatusMessage("Risposta ricevuta.");
        setIsLoading(false);
        setShouldSaveChat(true); // Attiva il salvataggio
      } catch (error) {
        console.error("Errore:", error);
        // In caso di errore, sostituisci l'eventuale placeholder con errore
        setChatMessages((prev) => {
          const next = [...prev];
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].sender === "RAGIS" && next[i].loading) {
              next[i] = { sender: "RAGIS", text: "Errore nella richiesta.", loading: false };
              return next;
            }
          }
          return next;
        });
        setStatusMessage("Errore nella richiesta.");
        setIsLoading(false);
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

  const handleParamChange = (e) => {
    const { name, value } = e.target;
    setModelParams((prev) => ({ ...prev, [name]: value }));
  };

  const handleSaveParams = async () => {
    try {
      // Verifica se il modello selezionato è installato
      const selectedModel = llmModels.find(m => 
        (typeof m === 'string' ? m : m.name) === modelParams.llm_model
      );
      const needsDownload = selectedModel && typeof selectedModel === 'object' && !selectedModel.installed;
      
      // Se il modello non è installato, scaricalo prima
      if (needsDownload) {
        setDownloadingModel(true);
        setStatusMessage(`Download di ${modelParams.llm_model} in corso...`);
        
        const headers = { "Content-Type": "application/json" };
        if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;
        
        const downloadResponse = await fetch(`${API_BASE}/download_model`, {
          method: "POST",
          headers,
          body: JSON.stringify({ model_name: modelParams.llm_model })
        });
        
        if (!downloadResponse.ok) {
          const errorData = await downloadResponse.json();
          setStatusMessage(`Errore download: ${errorData.detail || 'Download fallito'}`);
          setDownloadingModel(false);
          return;
        }
        
        // Ricarica la lista dei modelli per aggiornare lo stato
        await loadLlmModels();
        setDownloadingModel(false);
      }
      
      setStatusMessage("Salvataggio parametri...");
      const headers = { "Content-Type": "application/json" };
      if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;
      
      // Invia solo i parametri che hanno un valore non vuoto
      const body = {};
      if (modelParams.llm_model && modelParams.llm_model.trim() !== "") 
        body.llm_model = modelParams.llm_model.trim();
      if (modelParams.embed_model && modelParams.embed_model.trim() !== "") 
        body.embed_model = modelParams.embed_model.trim();
      if (modelParams.chunk_size && modelParams.chunk_size !== "") 
        body.chunk_size = parseInt(modelParams.chunk_size);
      if (modelParams.chunk_overlap && modelParams.chunk_overlap !== "") 
        body.chunk_overlap = parseInt(modelParams.chunk_overlap);
      if (modelParams.top_k && modelParams.top_k !== "") 
        body.top_k = parseInt(modelParams.top_k);
      if (modelParams.distance_threshold && modelParams.distance_threshold !== "") 
        body.distance_threshold = parseFloat(modelParams.distance_threshold);
      
      // Se non ci sono parametri da salvare
      if (Object.keys(body).length === 0) {
        setStatusMessage("Nessun parametro da salvare");
        return;
      }
      
      const response = await fetch(`${API_BASE}/save_parameters`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        // Gestisce errori di validazione FastAPI che possono essere array
        let errorMsg = "Errore nel salvataggio parametri";
        if (data.detail) {
          if (typeof data.detail === 'string') {
            errorMsg = data.detail;
          } else if (Array.isArray(data.detail)) {
            errorMsg = data.detail.map(err => err.msg || JSON.stringify(err)).join(", ");
          }
        }
        setStatusMessage(errorMsg);
        return;
      }
      
      const data = await response.json();
      setStatusMessage(data.message || "Parametri aggiornati.");
      setShowParamsPanel(false);
      
    } catch (err) {
      console.error("Errore salvataggio parametri:", err);
      setStatusMessage("Errore di rete durante il salvataggio.");
      setDownloadingModel(false);
    }
  };

  const handleLogout = () => {
    // Rimuove sessione e resetta UI
    localStorage.removeItem("rag_user");
    setUser(null);
    setChatMessages([]);
    setStatusMessage("");
  };

  const loadChatFromHistory = (chat) => {
    setShouldSaveChat(false); // Impedisci il salvataggio quando si carica una chat
    setChatMessages(chat.messages);
    setCurrentChatId(chat.id);
    // Scroll dopo il caricamento
    setTimeout(() => {
      if (chatMessagesRef.current) {
        chatMessagesRef.current.scrollTop = chatMessagesRef.current.scrollHeight;
      }
    }, 150);
  };

  const saveChatToHistory = () => {
    // Salva la chat corrente senza reset (per aggiornamenti incrementali)
    if (chatMessages.length > 0) {
      const firstUserMessage = chatMessages.find(msg => msg.sender === "utente");
      const preview = firstUserMessage 
        ? firstUserMessage.text.substring(0, 50) + (firstUserMessage.text.length > 50 ? '...' : '')
        : 'Chat senza messaggi';
      
      const chatToSave = {
        id: currentChatId,
        timestamp: currentChatId,
        preview: preview,
        messages: chatMessages
      };
      
      // Controlla se questa chat esiste già
      const existingIndex = chatHistory.findIndex(chat => chat.id === currentChatId);
      let updatedHistory;
      
      if (existingIndex >= 0) {
        // Aggiorna la chat esistente
        updatedHistory = [...chatHistory];
        updatedHistory[existingIndex] = chatToSave;
      } else {
        // Aggiungi nuova chat
        updatedHistory = [chatToSave, ...chatHistory].slice(0, 20); // Max 20 chat
      }
      
      setChatHistory(updatedHistory);
      localStorage.setItem('chatHistory', JSON.stringify(updatedHistory));
    }
  };

  const saveCurrentChatAndReset = () => {
    // Salva la chat corrente solo se ci sono messaggi
    if (chatMessages.length > 0) {
      const firstUserMessage = chatMessages.find(msg => msg.sender === "utente");
      const preview = firstUserMessage 
        ? firstUserMessage.text.substring(0, 50) + (firstUserMessage.text.length > 50 ? '...' : '')
        : 'Chat senza messaggi';
      
      const chatToSave = {
        id: currentChatId,
        timestamp: currentChatId,
        preview: preview,
        messages: chatMessages
      };
      
      // Controlla se questa chat esiste già (per evitare duplicati)
      const existingIndex = chatHistory.findIndex(chat => chat.id === currentChatId);
      let updatedHistory;
      
      if (existingIndex >= 0) {
        // Aggiorna la chat esistente
        updatedHistory = [...chatHistory];
        updatedHistory[existingIndex] = chatToSave;
      } else {
        // Aggiungi nuova chat
        updatedHistory = [chatToSave, ...chatHistory].slice(0, 20); // Max 20 chat
      }
      
      setChatHistory(updatedHistory);
      localStorage.setItem('chatHistory', JSON.stringify(updatedHistory));
    }
    
    // Reset della chat
    setChatMessages([]);
    setCurrentChatId(Date.now());
    window.location.reload();
  };

  const deleteChatFromHistory = (chatId) => {
    const updated = chatHistory.filter(chat => chat.id !== chatId);
    setChatHistory(updated);
    localStorage.setItem('chatHistory', JSON.stringify(updated));
  };

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(diff / (1000 * 60 * 60));
    
    if (minutes < 5) return 'Pochi minuti fa';
    if (minutes < 60) return `${minutes} minuti fa`;
    if (hours < 24) return `${hours}h fa`;
    return `${Math.floor(hours / 24)}g fa`;
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
          ruolo: newUserData.ruolo,
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
      setNewUserData({ username: "", password: "", ruolo: "Collaboratore" });
      setShowNewUserForm(false);
    } catch (err) {
      console.error("Errore creazione utente:", err);
      setNewUserError("Errore connessione al server");
    } finally {
      setNewUserLoading(false);
    }
  };

  const handleSuggestionClick = (text) => {
    setPromptUtente(text);
    setShowSuggestions(false);
    // Esegui automaticamente il prompt
    setTimeout(() => {
      handleSendPrompt();
    }, 100);
  };

  const loadUsersList = async () => {
    setUsersListLoading(true);
    try {
      const headers = {};
      if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;

      const response = await fetch(`${API_BASE}/lista-utenti`, { headers });
      const data = await response.json();

      if (!response.ok) {
        const errorMsg = typeof data.detail === 'string' 
          ? data.detail 
          : Array.isArray(data.detail) 
            ? data.detail.map(err => err.msg || JSON.stringify(err)).join(", ")
            : "Errore caricamento utenti";
        setStatusMessage(errorMsg);
        setUsersListLoading(false);
        return;
      }

      setUsersList(data.utenti || []);
      setShowUsersList(true);
    } catch (err) {
      console.error("Errore caricamento lista utenti:", err);
      setStatusMessage("Errore connessione al server");
    } finally {
      setUsersListLoading(false);
    }
  };

  const handleEditUser = async (e) => {
    e.preventDefault();
    setEditUserError("");

    if (!editUserData.username && !editUserData.password && !editUserData.ruolo) {
      setEditUserError("Inserisci almeno un campo da modificare");
      return;
    }

    setEditUserLoading(true);
    try {
      const headers = { "Content-Type": "application/json" };
      if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;

      // Il backend richiede tutti i campi, inviamo stringhe vuote per quelli non modificati
      const body = {
        username: editUserData.username || "",
        password: editUserData.password || "",
        ruolo: editUserData.ruolo || "Collaboratore"
      };

      const response = await fetch(`${API_BASE}/aggiorna-utente/${editUserData.id}`, {
        method: "PUT",
        headers,
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        const errorMsg = typeof data.detail === 'string' 
          ? data.detail 
          : Array.isArray(data.detail) 
            ? data.detail.map(err => err.msg || JSON.stringify(err)).join(", ")
            : "Errore aggiornamento utente";
        setEditUserError(errorMsg);
        setEditUserLoading(false);
        return;
      }

      setStatusMessage("Utente aggiornato con successo!");
      setEditUserData({ id: null, username: "", password: "", ruolo: "Collaboratore" });
      setShowEditUserForm(false);
      loadUsersList(); // Ricarica lista
    } catch (err) {
      console.error("Errore aggiornamento utente:", err);
      setEditUserError("Errore connessione al server");
    } finally {
      setEditUserLoading(false);
    }
  };

  const handleDeleteUser = async (userId, username) => {
    if (!window.confirm(`Sei sicuro di voler cancellare l'utente "${username}"?`)) {
      return;
    }

    try {
      const headers = {};
      if (user && user.token) headers["Authorization"] = `Bearer ${user.token}`;

      const response = await fetch(`${API_BASE}/cancella-utente/${userId}`, {
        method: "DELETE",
        headers,
      });

      const data = await response.json();

      if (!response.ok) {
        const errorMsg = typeof data.detail === 'string' 
          ? data.detail 
          : Array.isArray(data.detail) 
            ? data.detail.map(err => err.msg || JSON.stringify(err)).join(", ")
            : "Errore cancellazione utente";
        setStatusMessage(errorMsg);
        return;
      }

      setStatusMessage("Utente cancellato con successo!");
      loadUsersList(); // Ricarica lista
    } catch (err) {
      console.error("Errore cancellazione utente:", err);
      setStatusMessage("Errore connessione al server");
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
      {/* Overlay per chiudere sidebar su mobile */}
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)}></div>}
      
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        {/* Sezione statica: Logo, Nuova Chat, Menu Principale */}
        <div className="sidebar-header">
          <div className="logo">
            <img src="/ragis-logo.png" className="logo-img" alt="RAGIS Logo" />
          </div>

          {/* Pulsante Nuova Chat */}
          <button className="new-chat-btn" onClick={saveCurrentChatAndReset}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14m-7-7h14" />
            </svg>
            Nuova chat
          </button>

          {/* Mini-titolo sezione menu */}
          <div className="section-title">Menu Principale</div>

          {/* Categoria Documenti - Visibile per tutti */}
          <div className="sidebar-category">
            <button 
              className={`category-header ${openCategory === 'documents' ? 'open' : ''}`}
              onClick={() => setOpenCategory(openCategory === 'documents' ? null : 'documents')}
            >
              <span style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
                <svg className="category-icon" viewBox="0 0 24 24" fill="none">
                  <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
                <span>Documenti</span>
              </span>
              <span className="arrow">▶</span>
            </button>
            {openCategory === 'documents' && (
              <div className="category-content">
                {user && user.isAdmin && (
                  <button onClick={handleReindex}>Ricostruisci DB</button>
                )}
                <button onClick={() => document.getElementById('file-upload-sidebar').click()}>
                  Aggiungi documento
                </button>
              </div>
            )}
          </div>

          {user && user.isAdmin && (
            <>
              {/* Categoria Parametri */}
              <div className="sidebar-category">
                <button 
                  className={`category-header ${openCategory === 'params' ? 'open' : ''}`}
                  onClick={() => setOpenCategory(openCategory === 'params' ? null : 'params')}
                >
                  <span style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
                    <svg className="category-icon" viewBox="0 0 24 24" fill="none">
                      <path d="M12 15a3 3 0 100-6 3 3 0 000 6z"></path>
                      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"></path>
                    </svg>
                    <span>Parametri</span>
                  </span>
                  <span className="arrow">▶</span>
                </button>
                {openCategory === 'params' && (
                  <div className="category-content">
                    <button onClick={() => setShowParamsPanel(true)}>Modifica parametri</button>
                  </div>
                )}
              </div>

              {/* Categoria Gestione Utenti */}
              <div className="sidebar-category">
                <button 
                  className={`category-header ${openCategory === 'users' ? 'open' : ''}`}
                  onClick={() => setOpenCategory(openCategory === 'users' ? null : 'users')}
                >
                  <span style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
                    <svg className="category-icon" viewBox="0 0 24 24" fill="none">
                      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"></path>
                      <circle cx="9" cy="7" r="4"></circle>
                      <path d="M23 21v-2a4 4 0 00-3-3.87m-4-12a4 4 0 010 7.75"></path>
                    </svg>
                    <span>Gestione Utenti</span>
                  </span>
                  <span className="arrow">▶</span>
                </button>
                {openCategory === 'users' && (
                  <div className="category-content">
                    <button onClick={() => setShowNewUserForm(true)}>Aggiungi utente</button>
                    <button onClick={loadUsersList}>Lista utenti</button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Sezione scrollabile: Cronologia, Ricerca */}
        <div className="top-section">
          {/* Sezione Cronologia Chat */}
          <div className="chat-history-section">
            <div className="section-title">Cronologia (48h)</div>
            <div className="chat-history-list">
              {chatHistory.length === 0 ? (
                <div className="no-history">Nessuna chat salvata</div>
              ) : (
                [...chatHistory]
                  .sort((a, b) => b.timestamp - a.timestamp) // Ordina per timestamp decrescente
                  .map((chat) => (
                  <div key={chat.id} className="chat-history-item">
                    <div className="chat-preview" onClick={() => loadChatFromHistory(chat)}>
                      <div className="chat-text">{chat.preview}</div>
                      <div className="chat-time">{formatTimestamp(chat.timestamp)}</div>
                    </div>
                    <button 
                      className="delete-chat-btn" 
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteChatFromHistory(chat.id);
                      }}
                      title="Elimina chat"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M18 6L6 18M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Sezione Ricerca - scrollabile */}
          <div className="search-section">
            <div className="section-title">Ricerca</div>
            
            <div className="search-options">
              <label>
                <span>Ricerca - Solo locale</span>
                <input
                  type="checkbox"
                  name="local"
                  checked={searchMode.local}
                  onChange={handleCheckboxChange}
                />
                <span className="switch"></span>
              </label>
              <label>
                <span>Ricerca - Locale + Online</span>
                <input
                  type="checkbox"
                  name="online"
                  checked={searchMode.online}
                  onChange={handleCheckboxChange}
                />
                <span className="switch"></span>
              </label>
            </div>

            <input
              id="file-upload-sidebar"
              type="file"
              onChange={handleUploadDocument}
              style={{ display: "none" }}
            />
          </div>
        </div>

        <div className="bottom-section">
          <div className="account">Account: {user ? user.username : "-"}</div>
          {user && (
            <button onClick={handleLogout} className="logout-btn">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
              <span className="logout-text">Logout</span>
            </button>
          )}
        </div>
      </aside>

      {/* Modal parametri del sistema (solo admin) */}
      {user && user.isAdmin && showParamsPanel && (
        <div className="overlay" onClick={() => setShowParamsPanel(false)}>
          <div className="dialog params-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="params-dialog-header">
              <h3>Parametri del Sistema</h3>
              <button onClick={handleResetParams} className="reset-icon-btn" title="Reset ai valori di default">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="1 4 1 10 7 10"></polyline>
                  <polyline points="23 20 23 14 17 14"></polyline>
                  <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"></path>
                </svg>
              </button>
            </div>
            <div className="params-form">
              <div className="field-row model-field-row">
                <label>Modello LLM:</label>
                <div className="custom-select-wrapper">
                  <div 
                    className="custom-select-trigger" 
                    onClick={() => setShowModelDropdown(!showModelDropdown)}
                  >
                    <span>{modelParams.llm_model}</span>
                    <svg className={`chevron ${showModelDropdown ? 'open' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                  </div>
                  {showModelDropdown && (
                    <div className="custom-select-dropdown">
                      {llmModels.length > 0 ? (
                        llmModels.map((model) => {
                          const modelName = typeof model === 'string' ? model : model.name;
                          const isInstalled = typeof model === 'string' ? true : model.installed;
                          const isSelected = modelName === modelParams.llm_model;
                          return (
                            <div 
                              key={modelName} 
                              className={`custom-select-option ${isSelected ? 'selected' : ''}`}
                              onClick={() => {
                                setModelParams({...modelParams, llm_model: modelName});
                                setShowModelDropdown(false);
                              }}
                            >
                              <span className="model-name">
                                {modelName} {isInstalled ? '✓' : ''}
                              </span>
                              {!isInstalled && (
                                <svg 
                                  className="download-model-icon" 
                                  xmlns="http://www.w3.org/2000/svg" 
                                  viewBox="0 0 24 24" 
                                  fill="none" 
                                  stroke="currentColor" 
                                  strokeWidth="2" 
                                  strokeLinecap="round" 
                                  strokeLinejoin="round"
                                >
                                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                  <polyline points="7 10 12 15 17 10"></polyline>
                                  <line x1="12" y1="15" x2="12" y2="3"></line>
                                </svg>
                              )}
                            </div>
                          );
                        })
                      ) : (
                        <div className="custom-select-option" onClick={() => setShowModelDropdown(false)}>
                          <span className="model-name">mistral:latest</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
              <div className="field-row">
                <label>Modello Embeddings:</label>
                <input name="embed_model" value={modelParams.embed_model} onChange={handleParamChange} placeholder="es. intfloat/e5-large-v2" />
              </div>
              <div className="field-row">
                <label>Dimensione Chunk:</label>
                <input name="chunk_size" type="number" value={modelParams.chunk_size} onChange={handleParamChange} placeholder="1500" />
              </div>
              <div className="field-row">
                <label>Overlap Chunk:</label>
                <input name="chunk_overlap" type="number" value={modelParams.chunk_overlap} onChange={handleParamChange} placeholder="200" />
              </div>
              <div className="field-row">
                <label>Top K:</label>
                <input name="top_k" type="number" value={modelParams.top_k} onChange={handleParamChange} placeholder="8" />
              </div>
              <div className="field-row">
                <label>Soglia Distanza (Distance Threshold):</label>
                <input name="distance_threshold" type="number" step="0.01" value={modelParams.distance_threshold} onChange={handleParamChange} placeholder="0.6" />
              </div>
              <div className="dialog-buttons">
                <button onClick={handleSaveParams} className="save-btn" disabled={downloadingModel}>
                  {downloadingModel ? "Download in corso..." : "Salva"}
                </button>
                <button onClick={() => setShowParamsPanel(false)} className="close-btn" disabled={downloadingModel}>Chiudi</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Form creazione nuovo utente (solo per admin, visibile quando showNewUserForm è true) */}
      {user && user.isAdmin && showNewUserForm && (
        <div className="overlay" onClick={() => setShowNewUserForm(false)}>
          <div className="dialog new-user-dialog" onClick={(e) => e.stopPropagation()}>
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
              <div className="role-select">
                <label>Ruolo:</label>
                <select
                  value={newUserData.ruolo}
                  onChange={(e) => setNewUserData({ ...newUserData, ruolo: e.target.value })}
                  disabled={newUserLoading}
                >
                  <option value="Collaboratore">Collaboratore</option>
                  <option value="Admin">Admin</option>
                </select>
              </div>
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

      {/* Modal Lista Utenti (solo admin) */}
      {user && user.isAdmin && showUsersList && (
        <div className="overlay" onClick={() => setShowUsersList(false)}>
          <div className="dialog users-list-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Lista Utenti</h3>
            {usersListLoading ? (
              <p>Caricamento...</p>
            ) : (
              <div className="users-list">
                {usersList.length === 0 ? (
                  <p>Nessun utente trovato</p>
                ) : (
                  <table className="users-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Username</th>
                        <th>Ruolo</th>
                        <th style={{textAlign: 'right', paddingRight: '20px'}}>Azioni</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usersList.map((u) => (
                        <tr key={u.id}>
                          <td>{u.id}</td>
                          <td style={{fontWeight: '500'}}>{u.username}</td>
                          <td>
                            <span className={`role-badge ${u.ruolo.toLowerCase()}`}>
                              {u.ruolo}
                            </span>
                          </td>
                          <td className="actions">
                            <button
                              className="edit-btn"
                              onClick={() => {
                                setEditUserData({ id: u.id, username: u.username, password: "", ruolo: u.ruolo });
                                setShowEditUserForm(true);
                                setShowUsersList(false);
                              }}
                              title="Modifica utente"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                              </svg>
                            </button>
                            <button
                              className="delete-btn"
                              onClick={() => handleDeleteUser(u.id, u.username)}
                              title="Cancella utente"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                              </svg>
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
            <div className="dialog-buttons">
              <button onClick={() => setShowUsersList(false)}>Chiudi</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Modifica Utente (solo admin) */}
      {user && user.isAdmin && showEditUserForm && (
        <div className="overlay" onClick={() => setShowEditUserForm(false)}>
          <div className="dialog new-user-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Modifica Utente</h3>
            <form onSubmit={handleEditUser}>
              <input
                type="text"
                placeholder="Nuovo Username (lascia vuoto per non modificare)"
                value={editUserData.username}
                onChange={(e) => setEditUserData({ ...editUserData, username: e.target.value })}
                disabled={editUserLoading}
              />
              <input
                type="password"
                placeholder="Nuova Password (lascia vuoto per non modificare)"
                value={editUserData.password}
                onChange={(e) => setEditUserData({ ...editUserData, password: e.target.value })}
                disabled={editUserLoading}
              />
              <div className="role-select">
                <label>Ruolo:</label>
                <select
                  value={editUserData.ruolo}
                  onChange={(e) => setEditUserData({ ...editUserData, ruolo: e.target.value })}
                  disabled={editUserLoading}
                >
                  <option value="Collaboratore">Collaboratore</option>
                  <option value="Admin">Admin</option>
                </select>
              </div>
              {editUserError && <div className="status error">{editUserError}</div>}
              <div className="dialog-buttons">
                <button type="submit" disabled={editUserLoading}>
                  {editUserLoading ? "Aggiornamento..." : "Aggiorna"}
                </button>
                <button type="button" onClick={() => setShowEditUserForm(false)} disabled={editUserLoading}>
                  Annulla
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Main */}
      <main className="main" ref={chatMessagesRef}>
        {/* Pulsante hamburger per mobile */}
        {!sidebarOpen && (
          <button className="hamburger-btn" onClick={() => setSidebarOpen(true)}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>
        )}
        
        {/* Header con modello LLM */}
        <div className="chat-header">
          <div className="model-indicator">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
              <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
              <line x1="12" y1="22.08" x2="12" y2="12"></line>
            </svg>
            <span className="model-name">{modelParams.llm_model || "mistral"}</span>
          </div>
        </div>
        
        <div className="chat-area">
          <div className="chat">
            <div className="chat-messages">
              {chatMessages.map((msg, index) => (
                <div
                  key={index}
                  className={`message ${msg.sender === "utente" ? "user" : "rag"}`}
                >
                  <strong>{msg.sender}:</strong>{" "}
                  {msg.loading ? (
                    <LoaderBubble />
                  ) : msg.sender === "RAGIS" ? (
                    <span dangerouslySetInnerHTML={{ __html: formatMarkdown(msg.text) }} />
                  ) : (
                    msg.text
                  )}
                </div>
              ))}
            </div>
          </div>
          
          {/* Suggerimenti dinamici - visibili solo quando chat vuota e nessun prompt */}
          {showSuggestions && chatMessages.length === 0 && !promptUtente && (
            <div className="welcome-suggestions">
              <h2 className="welcome-title"> Benvenuto in RAGIS</h2>
              <p className="welcome-subtitle">Il tuo assistente legale intelligente per la ricerca nei documenti</p>
              <div className="suggestion-cards">
                <div className="suggestion-card" onClick={() => handleSuggestionClick("Cerca documenti relativi a contratti")}>
                  <svg className="suggestion-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span className="suggestion-text">Cerca nei documenti</span>
                </div>
                <div className="suggestion-card" onClick={() => handleSuggestionClick("Mostrami le notifiche più recenti")}>
                  <svg className="suggestion-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                  <span className="suggestion-text">Notifiche recenti</span>
                </div>
                <div className="suggestion-card" onClick={() => handleSuggestionClick("Analizza i solleciti di pagamento")}>
                  <svg className="suggestion-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="suggestion-text">Analisi solleciti</span>
                </div>
                <div className="suggestion-card" onClick={() => handleSuggestionClick("Trova corrispondenza per cliente")}>
                  <svg className="suggestion-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                  <span className="suggestion-text">Cerca corrispondenza</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Prompt utente */}
        <div className="prompt-wrapper">
          <div className="input-container">
            {false && ( /* Metti True per visualizzare il +*/
              <>
                <label htmlFor="file-upload" className="icon-button">+</label>
                <input
                  id="file-upload"
                  type="file"
                  onChange={handleUploadDocument}
                  style={{ display: "none" }}
                />
              </>
            )}
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
              disabled={isLoading}
            />
            <button className="icon-button send" onClick={handleSendPrompt} disabled={isLoading}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </button>
          </div>
          <footer className="footer">AI system rilasciato da RAGIS group</footer>
        </div>
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