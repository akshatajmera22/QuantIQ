import { useEffect, useState } from "react";
import {
  BarChart3,
  Check,
  ChevronDown,
  Database,
  FileSpreadsheet,
  FileText,
  History,
  Menu,
  MessageSquare,
  Plus,
  Send,
  Server,
  Settings,
  Sparkles,
  Upload,
  X,
} from "lucide-react";

const API_URL = "http://127.0.0.1:8000";

const DATA_TYPES = [
  {
    id: "excel",
    name: "Excel",
    description: "Upload one or multiple Excel files",
    icon: FileSpreadsheet,
  },
  {
    id: "csv",
    name: "CSV",
    description: "Upload CSV data",
    icon: FileText,
  },
  {
    id: "mysql",
    name: "MySQL",
    description: "Connect to a MySQL database",
    icon: Database,
  },
  {
    id: "sqlserver",
    name: "SQL Server",
    description: "Connect to SQL Server",
    icon: Server,
  },
];

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedType, setSelectedType] = useState(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const [history, setHistory] = useState([]);

  // IMPORTANT:
  // No automobile dataset.
  // No Sample Superstore fallback.
  // No default dataset.
  const [dataset, setDataset] = useState(null);

  // =========================================================
  // LOAD ACTIVE DATASET
  // =========================================================

  const loadActiveDataset = async () => {
    try {
      const response = await fetch(`${API_URL}/database`);

      const data = await response.json();

      if (
        response.ok &&
        data.success &&
        data.connected &&
        data.active_dataset
      ) {
        const active = data.active_dataset;

        const currentDataset = {
          id: active.id,
          name: active.name,
          type: active.type,
          status: active.status,
        };

        setDataset(currentDataset);

        return currentDataset;
      }

      setDataset(null);
      return null;
    } catch (error) {
      console.error("Failed to load dataset:", error);
      setDataset(null);
      return null;
    }
  };

  // =========================================================
  // INITIAL LOAD
  // =========================================================

  useEffect(() => {
    const savedHistory = localStorage.getItem("quantiq_history");

    if (savedHistory) {
      try {
        setHistory(JSON.parse(savedHistory));
      } catch {
        setHistory([]);
      }
    }

    loadActiveDataset();
  }, []);

  // =========================================================
  // SAVE HISTORY
  // =========================================================

  useEffect(() => {
    localStorage.setItem(
      "quantiq_history",
      JSON.stringify(history)
    );
  }, [history]);

  // =========================================================
  // HISTORY
  // =========================================================

  const addHistory = (text) => {
    const item = {
      id: Date.now(),
      question: text,
      createdAt: new Date().toISOString(),
    };

    setHistory((prev) => {
      const filtered = prev.filter(
        (oldItem) =>
          oldItem.question.toLowerCase() !==
          text.toLowerCase()
      );

      return [item, ...filtered].slice(0, 30);
    });
  };

  // =========================================================
  // ASK QUESTION
  // =========================================================

  const askQuestion = async (providedQuestion = null) => {
    const text = (
      providedQuestion ?? question
    ).trim();

    if (!text || loading) {
      return;
    }

    // Never query without an active dataset.
    if (!dataset) {
      setMessages((prev) => [
        ...prev,
        {
          role: "user",
          content: text,
        },
        {
          role: "assistant",
          error: true,
          content:
            "No dataset is connected. Please upload a CSV or Excel dataset first.",
        },
      ]);

      setQuestion("");
      return;
    }

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: text,
      },
    ]);

    setQuestion("");
    setLoading(true);

    addHistory(text);

    try {
      // Verify backend dataset before querying.
      const databaseResponse = await fetch(
        `${API_URL}/database`
      );

      const databaseData =
        await databaseResponse.json();

      if (
        !databaseResponse.ok ||
        !databaseData.success ||
        !databaseData.connected ||
        !databaseData.active_dataset
      ) {
        setDataset(null);

        throw new Error(
          "No dataset is connected. Please upload a CSV or Excel dataset first."
        );
      }

      const active =
        databaseData.active_dataset;

      setDataset({
        id: active.id,
        name: active.name,
        type: active.type,
        status: active.status,
      });

      // Send question.
      const response = await fetch(
        `${API_URL}/query`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question: text,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error ||
            data.message ||
            "The analysis service returned an error."
        );
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            data.answer ||
            "I couldn't generate an answer.",
          sql: data.sql,
          rows: data.rows || [],
          rowCount: data.row_count || 0,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          error: true,
          content:
            error.message ||
            "I couldn't connect to the QuantIQ backend.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // =========================================================
  // KEYBOARD
  // =========================================================

  const handleKeyDown = (event) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      askQuestion();
    }
  };

  // =========================================================
  // NEW CHAT
  // =========================================================

  const newChat = () => {
    setMessages([]);
    setQuestion("");
  };

  // =========================================================
  // OPEN HISTORY
  // =========================================================

  const openHistory = async (item) => {
    setMessages([
      {
        role: "user",
        content: item.question,
      },
    ]);

    setQuestion("");

    await askQuestion(item.question);
  };

  // =========================================================
  // FILE SELECTION
  // =========================================================

  const handleFileSelect = (event) => {
    const files = Array.from(
      event.target.files || []
    );

    setSelectedFiles(files);
    setUploadError("");
  };

  // =========================================================
  // UPLOAD DATA
  // =========================================================

  const connectData = async () => {
    if (!selectedType) {
      setUploadError(
        "Please choose a data source."
      );
      return;
    }

    if (
      selectedType === "excel" ||
      selectedType === "csv"
    ) {
      if (selectedFiles.length === 0) {
        setUploadError(
          "Please choose at least one file."
        );
        return;
      }
    }

    if (
      selectedType !== "excel" &&
      selectedType !== "csv"
    ) {
      setUploadError(
        "MySQL and SQL Server connections are not implemented yet."
      );
      return;
    }

    setUploading(true);
    setUploadError("");

    try {
      const formData = new FormData();

      formData.append(
        "source_type",
        selectedType
      );

      selectedFiles.forEach((file) => {
        formData.append("files", file);
      });

      const response = await fetch(
        `${API_URL}/upload`,
        {
          method: "POST",
          body: formData,
        }
      );

      let data;

      try {
        data = await response.json();
      } catch {
        throw new Error(
          `Upload failed with HTTP ${response.status}.`
        );
      }

      if (!response.ok) {
        throw new Error(
          data.detail ||
            data.error ||
            data.message ||
            `Upload failed with HTTP ${response.status}.`
        );
      }

      if (!data.success) {
        throw new Error(
          data.detail ||
            data.error ||
            data.message ||
            "The backend rejected the dataset."
        );
      }

      // IMPORTANT:
      // Do not trust the frontend state.
      // Ask the backend which dataset is actually active.
      const activeDataset =
        await loadActiveDataset();

      if (!activeDataset) {
        throw new Error(
          "The file uploaded, but the backend did not activate the dataset."
        );
      }

      // Start fresh analysis.
      setMessages([]);
      setQuestion("");

      // Close modal.
      setUploadOpen(false);

      setSelectedType(null);
      setSelectedFiles([]);
      setUploadError("");
    } catch (error) {
      console.error(
        "UPLOAD ERROR:",
        error
      );

      setUploadError(
        error.message ||
          "The data upload failed."
      );
    } finally {
      setUploading(false);
    }
  };

  // =========================================================
  // EXAMPLE QUESTIONS
  // =========================================================

  const exampleQuestions = [
    "What is the total sales?",
    "What is the average value?",
    "How many records are there?",
    "Show me the top 5 categories",
  ];

  // =========================================================
  // OPEN UPLOAD MODAL
  // =========================================================

  const openUploadModal = () => {
    setUploadError("");
    setSelectedType(null);
    setSelectedFiles([]);
    setUploadOpen(true);
  };

  // =========================================================
  // RENDER
  // =========================================================

  return (
    <div className="flex h-screen overflow-hidden bg-[#05070d] text-white">

      {/* =====================================================
          SIDEBAR
      ===================================================== */}

      {sidebarOpen && (
        <aside className="flex w-[280px] shrink-0 flex-col border-r border-white/10 bg-[#080b12]">

          {/* BRAND */}

          <div className="flex h-[72px] items-center gap-3 border-b border-white/10 px-5">

            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-400/30 bg-cyan-400/10">

              <Sparkles
                size={20}
                className="text-cyan-300"
              />

            </div>

            <div>

              <div className="text-lg font-bold tracking-wide">
                QUANT
                <span className="text-cyan-400">
                  IQ
                </span>
              </div>

              <div className="text-[11px] text-slate-500">
                AI Data Analyst
              </div>

            </div>

          </div>

          {/* NEW ANALYSIS */}

          <div className="p-4">

            <button
              onClick={newChat}
              className="flex w-full items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-medium transition hover:border-cyan-400/30 hover:bg-cyan-400/5"
            >

              <Plus size={18} />

              New analysis

            </button>

          </div>

          {/* HISTORY */}

          <div className="flex-1 overflow-y-auto px-3">

            <div className="mb-3 flex items-center justify-between px-2">

              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Recent
              </div>

              {history.length > 0 && (
                <History
                  size={14}
                  className="text-slate-600"
                />
              )}

            </div>

            {history.length === 0 ? (

              <div className="px-3 py-6 text-center text-xs text-slate-600">
                Your questions will appear here.
              </div>

            ) : (

              history.map((item) => (

                <button
                  key={item.id}
                  onClick={() =>
                    openHistory(item)
                  }
                  className="mb-1 flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm text-slate-300 transition hover:bg-white/5"
                >

                  <MessageSquare
                    size={15}
                    className="shrink-0 text-slate-500"
                  />

                  <span className="truncate">
                    {item.question}
                  </span>

                </button>

              ))

            )}

          </div>

          {/* CURRENT DATA */}

          <div className="border-t border-white/10 p-4">

            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Current data
            </div>

            {dataset ? (

              <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-3">

                <div className="flex items-center gap-3">

                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-cyan-400/10">

                    <Database
                      size={17}
                      className="text-cyan-300"
                    />

                  </div>

                  <div className="min-w-0">

                    <div className="truncate text-sm font-medium">
                      {dataset.name}
                    </div>

                    <div className="text-xs text-slate-500">
                      {dataset.type} •{" "}
                      {dataset.status}
                    </div>

                  </div>

                </div>

              </div>

            ) : (

              <div className="rounded-xl border border-yellow-400/20 bg-yellow-400/5 p-3">

                <div className="flex items-center gap-3">

                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-yellow-400/10">

                    <Database
                      size={17}
                      className="text-yellow-300"
                    />

                  </div>

                  <div>

                    <div className="text-sm font-medium text-yellow-200">
                      No dataset
                    </div>

                    <div className="text-xs text-yellow-200/50">
                      Upload CSV or Excel
                    </div>

                  </div>

                </div>

              </div>

            )}

          </div>

          {/* SETTINGS */}

          <div className="border-t border-white/10 p-3">

            <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-400 hover:bg-white/5 hover:text-white">

              <Settings size={17} />

              Settings

            </button>

          </div>

        </aside>
      )}

      {/* =====================================================
          MAIN
      ===================================================== */}

      <main className="flex min-w-0 flex-1 flex-col">

        {/* HEADER */}

        <header className="flex h-[72px] shrink-0 items-center justify-between border-b border-white/10 bg-[#070a11]/90 px-5 backdrop-blur">

          <div className="flex items-center gap-3">

            <button
              onClick={() =>
                setSidebarOpen(
                  !sidebarOpen
                )
              }
              className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white"
            >

              <Menu size={20} />

            </button>

            <div>

              <div className="text-sm font-semibold">
                Data Analysis
              </div>

              <div className="text-xs text-slate-500">
                Ask questions in plain English
              </div>

            </div>

          </div>

          {/* THIS BUTTON OPENS MODAL */}
          <button
            onClick={openUploadModal}
            className="flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 transition hover:border-cyan-400/30 hover:bg-white/5"
          >

            <Upload size={15} />

            Upload data

          </button>

        </header>

        {/* ===================================================
            CHAT
        =================================================== */}

        <section className="flex-1 overflow-y-auto">

          {messages.length === 0 ? (

            <div className="flex h-full items-center justify-center px-6">

              <div className="w-full max-w-3xl text-center">

                <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-400/30 bg-cyan-400/10 shadow-[0_0_40px_rgba(34,211,238,0.12)]">

                  <BarChart3
                    size={30}
                    className="text-cyan-300"
                  />

                </div>

                <h1 className="text-4xl font-bold tracking-tight">
                  Talk to your data.
                </h1>

                <p className="mx-auto mt-4 max-w-xl text-sm leading-6 text-slate-400">

                  {dataset
                    ? `Ask questions about ${dataset.name} in plain English.`
                    : "Upload a CSV or Excel dataset to start asking questions."}

                </p>

                {dataset && (

                  <div className="mt-10 grid grid-cols-1 gap-3 sm:grid-cols-2">

                    {exampleQuestions.map(
                      (item) => (

                        <button
                          key={item}
                          onClick={() =>
                            askQuestion(item)
                          }
                          className="rounded-xl border border-white/10 bg-white/[0.025] p-4 text-left text-sm text-slate-300 transition hover:border-cyan-400/30 hover:bg-cyan-400/5"
                        >

                          {item}

                        </button>

                      )
                    )}

                  </div>

                )}

              </div>

            </div>

          ) : (

            <div className="mx-auto w-full max-w-4xl px-6 py-8">

              {messages.map(
                (message, index) => (

                  <div
                    key={index}
                    className={`mb-8 flex gap-4 ${
                      message.role ===
                      "user"
                        ? "justify-end"
                        : "justify-start"
                    }`}
                  >

                    {message.role ===
                      "assistant" && (

                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-cyan-400/20 bg-cyan-400/10">

                        <Sparkles
                          size={17}
                          className="text-cyan-300"
                        />

                      </div>

                    )}

                    <div
                      className={`max-w-[80%] rounded-2xl px-5 py-4 ${
                        message.role ===
                        "user"
                          ? "bg-cyan-400 text-slate-950"
                          : message.error
                          ? "border border-red-400/20 bg-red-400/5 text-red-300"
                          : "border border-white/10 bg-white/[0.035] text-slate-200"
                      }`}
                    >

                      <div className="text-sm leading-7">
                        {message.content}
                      </div>

                      {message.role ===
                        "assistant" &&
                        !message.error &&
                        message.sql && (

                          <details className="mt-5 border-t border-white/10 pt-4">

                            <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-medium text-slate-400 hover:text-cyan-300">

                              <ChevronDown
                                size={14}
                              />

                              View generated SQL

                            </summary>

                            <pre className="mt-3 overflow-x-auto rounded-xl bg-black/40 p-4 text-xs leading-6 text-cyan-200">
                              {message.sql}
                            </pre>

                          </details>

                        )}

                    </div>

                  </div>

                )
              )}

              {loading && (

                <div className="flex gap-4">

                  <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-cyan-400/20 bg-cyan-400/10">

                    <Sparkles
                      size={17}
                      className="animate-pulse text-cyan-300"
                    />

                  </div>

                  <div className="rounded-2xl border border-white/10 bg-white/[0.035] px-5 py-4 text-sm text-slate-400">

                    Analyzing your data...

                  </div>

                </div>

              )}

            </div>

          )}

        </section>

        {/* ===================================================
            INPUT
        =================================================== */}

        <div className="shrink-0 border-t border-white/10 bg-[#070a11] px-5 py-5">

          <div className="mx-auto max-w-4xl">

            <div className="relative rounded-2xl border border-white/10 bg-white/[0.04] shadow-2xl focus-within:border-cyan-400/30">

              <textarea
                value={question}
                onChange={(event) =>
                  setQuestion(
                    event.target.value
                  )
                }
                onKeyDown={handleKeyDown}
                placeholder={
                  dataset
                    ? "Ask anything about your data..."
                    : "Upload data first..."
                }
                disabled={!dataset}
                rows={1}
                className="w-full resize-none bg-transparent px-5 py-4 pr-14 text-sm text-white outline-none placeholder:text-slate-600 disabled:cursor-not-allowed"
              />

              <button
                onClick={() =>
                  askQuestion()
                }
                disabled={
                  !question.trim() ||
                  loading ||
                  !dataset
                }
                className="absolute bottom-2.5 right-2.5 flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-400 text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-30"
              >

                <Send size={16} />

              </button>

            </div>

            <div className="mt-2 flex items-center justify-center gap-2 text-[11px] text-slate-600">

              <FileSpreadsheet size={13} />

              {dataset
                ? `Analyzing ${dataset.name}`
                : "No dataset connected"}

            </div>

          </div>

        </div>

      </main>

      {/* =====================================================
          UPLOAD MODAL
      ===================================================== */}

      {uploadOpen && (

        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-5 backdrop-blur-sm">

          <div className="w-full max-w-2xl rounded-2xl border border-white/10 bg-[#0b0f18] shadow-2xl">

            {/* MODAL HEADER */}

            <div className="flex items-center justify-between border-b border-white/10 px-6 py-5">

              <div>

                <h2 className="text-lg font-semibold">
                  Add data
                </h2>

                <p className="mt-1 text-xs text-slate-500">
                  Connect your data to QuantIQ
                </p>

              </div>

              <button
                onClick={() =>
                  setUploadOpen(false)
                }
                className="rounded-lg p-2 text-slate-500 hover:bg-white/5 hover:text-white"
              >

                <X size={18} />

              </button>

            </div>

            {/* MODAL BODY */}

            <div className="p-6">

              {/* SOURCE SELECTION */}

              {!selectedType && (

                <>
                  <div className="mb-4 text-sm font-medium text-slate-300">
                    Choose your data source
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">

                    {DATA_TYPES.map(
                      (type) => {

                        const Icon =
                          type.icon;

                        return (

                          <button
                            key={type.id}
                            onClick={() => {
                              setSelectedType(
                                type.id
                              );
                              setSelectedFiles(
                                []
                              );
                              setUploadError(
                                ""
                              );
                            }}
                            className="rounded-xl border border-white/10 bg-white/[0.02] p-5 text-left transition hover:border-cyan-400/40 hover:bg-cyan-400/5"
                          >

                            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-cyan-400/10">

                              <Icon
                                size={21}
                                className="text-cyan-300"
                              />

                            </div>

                            <div className="text-sm font-medium">
                              {type.name}
                            </div>

                            <div className="mt-1 text-xs leading-5 text-slate-500">
                              {type.description}
                            </div>

                          </button>

                        );
                      }
                    )}

                  </div>
                </>

              )}

              {/* SELECTED SOURCE */}

              {selectedType && (

                <>

                  <button
                    onClick={() => {
                      setSelectedType(
                        null
                      );
                      setSelectedFiles(
                        []
                      );
                      setUploadError(
                        ""
                      );
                    }}
                    className="mb-5 text-xs text-cyan-300 hover:text-cyan-200"
                  >
                    ← Back to data sources
                  </button>

                  <div className="mb-5 flex items-center gap-3">

                    {(() => {

                      const source =
                        DATA_TYPES.find(
                          (item) =>
                            item.id ===
                            selectedType
                        );

                      const Icon =
                        source?.icon ||
                        Database;

                      return (
                        <>
                          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-400/10">

                            <Icon
                              size={19}
                              className="text-cyan-300"
                            />

                          </div>

                          <div>

                            <div className="text-sm font-medium">
                              {source?.name}
                            </div>

                            <div className="text-xs text-slate-500">
                              {source?.description}
                            </div>

                          </div>
                        </>
                      );

                    })()}

                  </div>

                  {/* EXCEL / CSV */}

                  {(selectedType ===
                    "excel" ||
                    selectedType ===
                      "csv") && (

                    <>

                      <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-white/15 bg-white/[0.02] px-6 py-10 text-center transition hover:border-cyan-400/40 hover:bg-cyan-400/5">

                        <Upload
                          size={28}
                          className="mb-4 text-cyan-300"
                        />

                        <div className="text-sm font-medium">
                          Choose{" "}
                          {selectedType ===
                          "excel"
                            ? "Excel"
                            : "CSV"}{" "}
                          file
                          {selectedType ===
                            "excel" &&
                            "s"}
                        </div>

                        <div className="mt-2 text-xs text-slate-500">
                          Click here to browse your computer
                        </div>

                        <input
                          type="file"
                          accept={
                            selectedType ===
                            "excel"
                              ? ".xlsx,.xls,.xlsm"
                              : ".csv"
                          }
                          multiple={
                            selectedType ===
                            "excel"
                          }
                          onChange={
                            handleFileSelect
                          }
                          className="hidden"
                        />

                      </label>

                      {/* SELECTED FILES */}

                      {selectedFiles.length >
                        0 && (

                        <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-4">

                          <div className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">
                            Selected files
                          </div>

                          <div className="space-y-2">

                            {selectedFiles.map(
                              (
                                file,
                                index
                              ) => (

                                <div
                                  key={index}
                                  className="flex items-center gap-3 rounded-lg bg-white/[0.03] px-3 py-2"
                                >

                                  <FileText
                                    size={15}
                                    className="shrink-0 text-cyan-400"
                                  />

                                  <span className="truncate text-xs text-slate-300">
                                    {file.name}
                                  </span>

                                  <Check
                                    size={15}
                                    className="ml-auto shrink-0 text-green-400"
                                  />

                                </div>

                              )
                            )}

                          </div>

                        </div>

                      )}

                    </>

                  )}

                  {/* DATABASE SOURCES */}

                  {(selectedType ===
                    "mysql" ||
                    selectedType ===
                      "sqlserver") && (

                    <div className="rounded-xl border border-yellow-400/20 bg-yellow-400/5 p-5">

                      <div className="text-sm font-medium text-yellow-200">
                        Database connection coming next
                      </div>

                      <p className="mt-2 text-xs leading-5 text-yellow-200/60">
                        File uploads are being connected first.
                        MySQL and SQL Server will use secure
                        connection settings once implemented.
                      </p>

                    </div>

                  )}

                </>

              )}

            </div>

            {/* ERROR */}

            {uploadError && (

              <div className="mx-6 mb-4 rounded-xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-xs leading-5 text-red-300">

                {uploadError}

              </div>

            )}

            {/* FOOTER */}

            <div className="flex items-center justify-end gap-3 border-t border-white/10 px-6 py-4">

              <button
                onClick={() =>
                  setUploadOpen(false)
                }
                disabled={uploading}
                className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:bg-white/5 hover:text-white disabled:opacity-50"
              >
                Cancel
              </button>

              {selectedType ===
                "excel" ||
              selectedType ===
                "csv" ? (

                <button
                  onClick={connectData}
                  disabled={
                    uploading ||
                    selectedFiles.length ===
                      0
                  }
                  className="rounded-lg bg-cyan-400 px-5 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-30"
                >

                  {uploading
                    ? "Uploading..."
                    : "Connect data"}

                </button>

              ) : (

                selectedType && (

                  <button
                    disabled
                    className="rounded-lg bg-cyan-400/30 px-5 py-2 text-sm font-medium text-slate-950"
                  >
                    Coming soon
                  </button>

                )

              )}

            </div>

          </div>

        </div>

      )}

    </div>
  );
}

export default App;