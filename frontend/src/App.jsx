import { useEffect, useState } from "react";

import {
  BarChart3,
  Check,
  ChevronDown,
  Database,
  FileSpreadsheet,
  FileText,
  History,
  Loader2,
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


const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";


async function apiFetch(url, options = {}) {
  const token = sessionStorage.getItem("quantiq_auth_token");
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    sessionStorage.removeItem("quantiq_auth_token");
    window.dispatchEvent(new Event("quantiq:unauthorized"));
  }

  return response;
}


/* ============================================================
   DATA TYPES
============================================================ */

const DATA_TYPES = [
  {
    id: "excel",
    name: "Excel",
    description:
      "Upload one or multiple Excel files",
    icon: FileSpreadsheet,
  },

  {
    id: "csv",
    name: "CSV",
    description:
      "Upload CSV data",
    icon: FileText,
  },

  {
    id: "mysql",
    name: "MySQL",
    description:
      "Connect to a MySQL database",
    icon: Database,
  },

  {
    id: "sqlserver",
    name: "SQL Server",
    description:
      "Connect to SQL Server",
    icon: Server,
  },
];


/* ============================================================
   HELPERS
============================================================ */

function formatValue(value) {

  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {

    return "—";
  }

  if (
    typeof value === "number"
  ) {

    return value.toLocaleString(
      undefined,
      {
        maximumFractionDigits: 4,
      }
    );
  }

  return String(value);
}


function extractRows(data) {

  if (
    Array.isArray(
      data?.rows
    )
  ) {

    return data.rows;
  }

  if (
    Array.isArray(
      data?.results
    )
  ) {

    const firstResult =
      data.results[0];

    if (
      Array.isArray(
        firstResult?.rows
      )
    ) {

      return firstResult.rows;
    }
  }

  return [];
}


function extractRowCount(
  data,
  rows
) {

  if (
    typeof data?.row_count ===
    "number"
  ) {

    return data.row_count;
  }

  if (
    typeof data?.count ===
    "number"
  ) {

    return data.count;
  }

  if (
    Array.isArray(
      data?.results
    )
  ) {

    const total =
      data.results.reduce(
        (
          sum,
          result
        ) => {

          return (
            sum +
            (
              typeof result?.row_count ===
              "number"

                ? result.row_count

                : Array.isArray(
                    result?.rows
                  )

                ? result.rows.length

                : 0
            )
          );
        },
        0
      );

    if (total > 0) {

      return total;
    }
  }

  return rows.length;
}


function extractSQL(
  data
) {

  if (
    typeof data?.sql ===
    "string"
  ) {

    return data.sql;
  }

  if (
    Array.isArray(
      data?.sql
    )
  ) {

    return data.sql.join(
      "\n\n"
    );
  }

  if (
    typeof data?.query ===
    "string"
  ) {

    return data.query;
  }

  if (
    Array.isArray(
      data?.results
    )
  ) {

    const sqlStatements =
      data.results
        .map(
          (
            result
          ) =>
            result?.sql
        )
        .filter(Boolean);

    if (
      sqlStatements.length > 0
    ) {

      return sqlStatements.join(
        "\n\n"
      );
    }
  }

  return "";
}


/* ============================================================
   MAIN APP
============================================================ */

function App() {

  const [authChecked, setAuthChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);

  useEffect(() => {
    let mounted = true;

    const checkSession = async () => {
      const token = sessionStorage.getItem("quantiq_auth_token");

      if (!token) {
        if (mounted) {
          setIsAuthenticated(false);
          setAuthChecked(true);
        }
        return;
      }

      try {
        const response = await apiFetch(`${API_URL}/auth/me`);
        if (mounted) {
          setIsAuthenticated(response.ok);
        }
      } catch {
        if (mounted) {
          setIsAuthenticated(false);
        }
      } finally {
        if (mounted) {
          setAuthChecked(true);
        }
      }
    };

    const handleUnauthorized = () => {
      if (mounted) {
        setIsAuthenticated(false);
      }
    };

    window.addEventListener("quantiq:unauthorized", handleUnauthorized);
    checkSession();

    return () => {
      mounted = false;
      window.removeEventListener("quantiq:unauthorized", handleUnauthorized);
    };
  }, []);

  const handleLogin = async (event) => {
    event.preventDefault();
    setLoginError("");

    if (!loginUsername.trim() || !loginPassword) {
      setLoginError("Enter your username and password.");
      return;
    }

    setLoginLoading(true);
    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: loginUsername.trim(),
          password: loginPassword,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok || !data?.success || !data?.token) {
        throw new Error(
          data?.detail || "Login failed. Check your credentials and backend configuration."
        );
      }

      sessionStorage.setItem("quantiq_auth_token", data.token);
      setIsAuthenticated(true);
      setLoginPassword("");
      setLoginError("");
    } catch (error) {
      setLoginError(
        error?.message || "Unable to connect to the QuantIQ authentication service."
      );
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem("quantiq_auth_token");
    setIsAuthenticated(false);
    setLoginPassword("");
    setLoginError("");
  };

  /* ==========================================================
     UI STATE
  ========================================================== */

  const [
    sidebarOpen,
    setSidebarOpen,
  ] = useState(true);


  const [
    question,
    setQuestion,
  ] = useState("");


  const [
    messages,
    setMessages,
  ] = useState([]);


  const [
    loading,
    setLoading,
  ] = useState(false);


  const [
    uploadOpen,
    setUploadOpen,
  ] = useState(false);


  const [
    selectedType,
    setSelectedType,
  ] = useState(null);


  const [
    selectedFiles,
    setSelectedFiles,
  ] = useState([]);


  const [
    uploading,
    setUploading,
  ] = useState(false);


  const [
    uploadError,
    setUploadError,
  ] = useState("");


  const [
    history,
    setHistory,
  ] = useState([]);


  const [
    dataset,
    setDataset,
  ] = useState(null);


  /* ==========================================================
     MYSQL
  ========================================================== */

  const [
    mysqlForm,
    setMysqlForm,
  ] = useState({
    host: "localhost",
    port: "3306",
    username: "",
    password: "",
    database: "",
  });


  const [
    mysqlDatabases,
    setMysqlDatabases,
  ] = useState([]);


  const [
    mysqlTesting,
    setMysqlTesting,
  ] = useState(false);


  const [
    mysqlLoadingDatabases,
    setMysqlLoadingDatabases,
  ] = useState(false);


  const [
    mysqlConnected,
    setMysqlConnected,
  ] = useState(false);


  /* ==========================================================
     SETTINGS
  ========================================================== */

  const [
    settingsOpen,
    setSettingsOpen,
  ] = useState(false);


  const [
    backendStatus,
    setBackendStatus,
  ] = useState("Checking...");


  const [
    backendChecking,
    setBackendChecking,
  ] = useState(false);


  const [
    disconnecting,
    setDisconnecting,
  ] = useState(false);


  /* ==========================================================
     BACKEND STATUS
  ========================================================== */

  const checkBackendStatus =
    async () => {

      setBackendChecking(true);

      try {

        const response =
          await apiFetch(
            `${API_URL}/health`
          );

        if (!response.ok) {

          throw new Error(
            "Backend unavailable"
          );
        }

        const data =
          await response.json();

        setBackendStatus(
          data?.success === false
            ? "Unavailable"
            : "Connected"
        );

      } catch {

        setBackendStatus(
          "Unavailable"
        );

      } finally {

        setBackendChecking(
          false
        );
      }
    };


  useEffect(() => {

    checkBackendStatus();

  }, []);


  /* ==========================================================
     LOAD HISTORY
  ========================================================== */

  useEffect(() => {

    const saved =
      localStorage.getItem(
        "quantiq_history"
      );

    if (!saved) {
      return;
    }

    try {

      const parsed =
        JSON.parse(saved);

      if (
        Array.isArray(parsed)
      ) {

        setHistory(parsed);
      }

    } catch {

      setHistory([]);
    }

  }, []);


  /* ==========================================================
     SAVE HISTORY
  ========================================================== */

  useEffect(() => {

    localStorage.setItem(
      "quantiq_history",
      JSON.stringify(history)
    );

  }, [history]);


  /* ==========================================================
     HISTORY
  ========================================================== */

  const addHistory = (
    text
  ) => {

    const clean =
      text.trim();

    if (!clean) {
      return;
    }

    const item = {
      id: Date.now(),
      question: clean,
      createdAt:
        new Date().toISOString(),
    };

    setHistory(
      (previous) => {

        const filtered =
          previous.filter(
            (oldItem) =>
              oldItem.question
                .toLowerCase() !==
              clean.toLowerCase()
          );

        return [
          item,
          ...filtered,
        ].slice(
          0,
          30
        );
      }
    );
  };


  /* ==========================================================
     ASK QUESTION
  ========================================================== */

  const askQuestion =
    async (
      providedQuestion = null
    ) => {

      const text = (
        providedQuestion ??
        question
      ).trim();

      if (
        !text ||
        loading
      ) {

        return;
      }


      /* ------------------------------------------------------
         DATA SOURCE CHECK
      ------------------------------------------------------ */

      if (!dataset) {

        setMessages(
          (previous) => [
            ...previous,

            {
              role: "user",
              content: text,
            },

            {
              role: "assistant",
              error: true,
              content:
                "Please connect or upload a data source first.",
            },
          ]
        );

        setQuestion("");

        return;
      }


      /* ------------------------------------------------------
         IMPORTANT:
         Capture the PREVIOUS conversation before adding
         the current question.

         This prevents the current question from appearing
         twice in the planner context.
      ------------------------------------------------------ */

      const conversation =
        messages
          .slice(-8)
          .map(
            (
              message
            ) => ({
              role:
                message.role,

              content:
                message.content ||
                "",

              sql:
                message.sql ||
                null,
            })
          );


      /* ------------------------------------------------------
         ADD USER MESSAGE
      ------------------------------------------------------ */

      setMessages(
        (previous) => [
          ...previous,

          {
            role: "user",
            content: text,
          },
        ]
      );

      setQuestion("");

      setLoading(true);

      addHistory(text);


      /* ------------------------------------------------------
         BACKEND REQUEST
      ------------------------------------------------------ */

      try {

        const response =
          await apiFetch(
            `${API_URL}/query`,
            {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body:
                JSON.stringify({
                  question: text,

                  conversation:
                    conversation,
                }),
            }
          );


        let data;

        try {

          data =
            await response.json();

        } catch {

          throw new Error(
            "The backend returned an invalid response."
          );
        }


        if (
          !response.ok
        ) {

          throw new Error(
            data?.detail ||
            data?.error ||
            data?.message ||
            "The analysis service returned an error."
          );
        }


        /* ----------------------------------------------------
           RESULTS
        ---------------------------------------------------- */

        const rows =
          extractRows(data);

        const rowCount =
          extractRowCount(
            data,
            rows
          );

        const sql =
          extractSQL(data);


        /* ----------------------------------------------------
           BACKEND FAILURE
        ---------------------------------------------------- */

        if (
          data?.success === false
        ) {

          throw new Error(
            data?.error ||
            data?.message ||
            "I could not find an answer for that question."
          );
        }


        /* ----------------------------------------------------
           ANSWER
        ---------------------------------------------------- */

        const answer =
          data?.answer ||
          "I couldn't generate an answer.";


        /* ----------------------------------------------------
           STORE ASSISTANT RESPONSE

           SQL is stored with the assistant message.
           Therefore the NEXT question can receive:

              previous question
              previous answer
              previous SQL
        ---------------------------------------------------- */

        setMessages(
          (previous) => [
            ...previous,

            {
              role: "assistant",

              content:
                answer,

              sql:
                sql,

              rows:
                rows,

              rowCount:
                rowCount,
            },
          ]
        );

      } catch (
        error
      ) {

        setMessages(
          (previous) => [
            ...previous,

            {
              role:
                "assistant",

              error:
                true,

              content:
                error?.message ||
                "I couldn't connect to the QuantIQ backend.",
            },
          ]
        );

      } finally {

        setLoading(false);
      }
    };


  /* ==========================================================
     ENTER
  ========================================================== */

  const handleKeyDown =
    (event) => {

      if (
        event.key ===
          "Enter" &&
        !event.shiftKey
      ) {

        event.preventDefault();

        askQuestion();
      }
    };


  /* ==========================================================
     NEW ANALYSIS
  ========================================================== */

  const newChat =
    async () => {

      const hasCurrentData =
        Boolean(
          dataset ||
          mysqlConnected
        );


      if (!hasCurrentData) {

        setMessages([]);

        setQuestion("");

        setUploadError("");

        setSelectedType(
          null
        );

        setSelectedFiles([]);

        setUploadOpen(true);

        return;
      }


      const confirmed =
        window.confirm(
          "Are you sure you want to disconnect the current data source?\n\nYour current analysis will be cleared and you will be taken to the data connection page."
        );


      if (!confirmed) {
        return;
      }


      setDisconnecting(true);

      setUploadError("");


      try {

        const response =
          await apiFetch(
            `${API_URL}/disconnect`,
            {
              method: "POST",
            }
          );


        const data =
          await response.json();


        if (
          !response.ok ||
          !data?.success
        ) {

          throw new Error(
            data?.detail ||
            data?.message ||
            "Could not disconnect the current data source."
          );
        }


        setDataset(null);

        setMysqlConnected(
          false
        );

        setMysqlDatabases(
          []
        );

        setMysqlForm({
          host: "localhost",
          port: "3306",
          username: "",
          password: "",
          database: "",
        });

        setMessages([]);

        setQuestion("");

        setSelectedType(
          null
        );

        setSelectedFiles(
          []
        );

        setUploadError("");

        setUploadOpen(true);

      } catch (
        error
      ) {

        setUploadError(
          error?.message ||
          "Could not disconnect the current data source."
        );

      } finally {

        setDisconnecting(
          false
        );
      }
    };


  /* ==========================================================
     OPEN HISTORY
  ========================================================== */

  const openHistory =
    (item) => {

      setMessages([]);

      setQuestion(
        item.question
      );

      setTimeout(
        () => {

          askQuestion(
            item.question
          );

        },
        0
      );
    };


  /* ==========================================================
     FILE SELECT
  ========================================================== */

  const handleFileSelect =
    (event) => {

      const files =
        Array.from(
          event.target.files ||
          []
        );

      setSelectedFiles(
        files
      );

      setUploadError("");
    };


  /* ==========================================================
     MYSQL FORM
  ========================================================== */

  const handleMysqlChange =
    (
      field,
      value
    ) => {

      setMysqlForm(
        (previous) => ({
          ...previous,
          [field]:
            value,
        })
      );

      setUploadError("");
    };


  /* ==========================================================
     TEST MYSQL
  ========================================================== */

  const testMysqlConnection =
    async () => {

      if (
        !mysqlForm.host.trim()
      ) {

        setUploadError(
          "MySQL host is required."
        );

        return;
      }

      if (
        !mysqlForm.port.trim()
      ) {

        setUploadError(
          "MySQL port is required."
        );

        return;
      }

      if (
        !mysqlForm.username.trim()
      ) {

        setUploadError(
          "MySQL username is required."
        );

        return;
      }

      setMysqlTesting(true);

      setUploadError("");

      try {

        const response =
          await apiFetch(
            `${API_URL}/mysql/test`,
            {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body:
                JSON.stringify({
                  host:
                    mysqlForm.host.trim(),

                  port:
                    Number(
                      mysqlForm.port
                    ),

                  username:
                    mysqlForm.username.trim(),

                  password:
                    mysqlForm.password,

                  database:
                    mysqlForm.database ||
                    null,
                }),
            }
          );


        const data =
          await response.json();


        if (
          !response.ok ||
          !data.success
        ) {

          throw new Error(
            data?.detail ||
            data?.message ||
            "MySQL connection test failed."
          );
        }


        setMysqlConnected(
          true
        );

        setUploadError("");

      } catch (
        error
      ) {

        setMysqlConnected(
          false
        );

        setUploadError(
          error?.message ||
          "Could not connect to MySQL."
        );

      } finally {

        setMysqlTesting(
          false
        );
      }
    };


  /* ==========================================================
     LOAD MYSQL DATABASES
  ========================================================== */

  const loadMysqlDatabases =
    async () => {

      if (
        !mysqlForm.host.trim()
      ) {

        setUploadError(
          "MySQL host is required."
        );

        return;
      }

      if (
        !mysqlForm.port.trim()
      ) {

        setUploadError(
          "MySQL port is required."
        );

        return;
      }

      if (
        !mysqlForm.username.trim()
      ) {

        setUploadError(
          "MySQL username is required."
        );

        return;
      }

      setMysqlLoadingDatabases(
        true
      );

      setUploadError("");

      try {

        const connectResponse =
          await apiFetch(
            `${API_URL}/mysql/connect`,
            {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body:
                JSON.stringify({
                  host:
                    mysqlForm.host.trim(),

                  port:
                    Number(
                      mysqlForm.port
                    ),

                  username:
                    mysqlForm.username.trim(),

                  password:
                    mysqlForm.password,

                  database:
                    null,
                }),
            }
          );


        const connectData =
          await connectResponse.json();


        if (
          !connectResponse.ok ||
          connectData?.connected !== true
        ) {

          throw new Error(
            connectData?.detail ||
            connectData?.message ||
            "Could not connect to MySQL."
          );
        }


        setMysqlConnected(
          true
        );


        const response =
          await apiFetch(
            `${API_URL}/mysql/databases`
          );


        const data =
          await response.json();


        if (
          !response.ok ||
          !data.success
        ) {

          throw new Error(
            data?.detail ||
            data?.message ||
            "Could not load MySQL databases."
          );
        }


        setMysqlDatabases(
          Array.isArray(
            data.databases
          )
            ? data.databases
            : []
        );

      } catch (
        error
      ) {

        setMysqlConnected(
          false
        );

        setMysqlDatabases(
          []
        );

        setUploadError(
          error?.message ||
          "Could not load MySQL databases."
        );

      } finally {

        setMysqlLoadingDatabases(
          false
        );
      }
    };


  /* ==========================================================
     DISCONNECT CURRENT SOURCE
  ========================================================== */

  const disconnectCurrentSource =
    async () => {

      if (
        !dataset &&
        !mysqlConnected
      ) {

        return;
      }

      setDisconnecting(
        true
      );

      setUploadError("");

      try {

        const response =
          await apiFetch(
            `${API_URL}/disconnect`,
            {
              method: "POST",
            }
          );


        const data =
          await response.json();


        if (
          !response.ok ||
          !data.success
        ) {

          throw new Error(
            data?.detail ||
            data?.message ||
            "Could not disconnect the current data source."
          );
        }


        setDataset(null);

        setMysqlConnected(
          false
        );

        setMysqlDatabases(
          []
        );

        setMysqlForm({
          host: "localhost",
          port: "3306",
          username: "",
          password: "",
          database: "",
        });

        setMessages([]);

        setQuestion("");

        setSelectedType(
          null
        );

        setSelectedFiles([]);

        setUploadError("");

      } catch (
        error
      ) {

        setUploadError(
          error?.message ||
          "Could not disconnect the current data source."
        );

      } finally {

        setDisconnecting(
          false
        );
      }
    };


  /* ==========================================================
     CONNECT DATA
  ========================================================== */

  const connectData =
    async () => {

      if (!selectedType) {
        return;
      }


      /* ------------------------------------------------------
         FILE
      ------------------------------------------------------ */

      if (
        (
          selectedType ===
            "excel" ||
          selectedType ===
            "csv"
        ) &&
        selectedFiles.length === 0
      ) {

        setUploadError(
          "Please choose at least one file."
        );

        return;
      }


      /* ------------------------------------------------------
         MYSQL
      ------------------------------------------------------ */

      if (
        selectedType ===
        "mysql"
      ) {

        if (
          !mysqlForm.host.trim()
        ) {

          setUploadError(
            "MySQL host is required."
          );

          return;
        }

        if (
          !mysqlForm.port.trim()
        ) {

          setUploadError(
            "MySQL port is required."
          );

          return;
        }

        if (
          !mysqlForm.username.trim()
        ) {

          setUploadError(
            "MySQL username is required."
          );

          return;
        }

        if (
          !mysqlForm.database.trim()
        ) {

          setUploadError(
            "Please select a MySQL database."
          );

          return;
        }


        setUploading(true);

        setUploadError("");


        try {

          const response =
            await apiFetch(
              `${API_URL}/mysql/connect`,
              {
                method: "POST",

                headers: {
                  "Content-Type":
                    "application/json",
                },

                body:
                  JSON.stringify({
                    host:
                      mysqlForm.host.trim(),

                    port:
                      Number(
                        mysqlForm.port
                      ),

                    username:
                      mysqlForm.username.trim(),

                    password:
                      mysqlForm.password,

                    database:
                      mysqlForm.database.trim(),
                  }),
              }
            );


          const data =
            await response.json();


          if (
            !response.ok ||
            data?.connected !== true
          ) {

            throw new Error(
              data?.detail ||
              data?.message ||
              "MySQL connection failed."
            );
          }


          setMysqlConnected(
            true
          );


          setDataset({
            name:
              mysqlForm.database.trim(),

            type:
              "MySQL",

            status:
              "Connected",

            source:
              "mysql",
          });


          setMessages([]);

          setQuestion("");

          setUploadOpen(
            false
          );

          setSelectedType(
            null
          );

          setSelectedFiles([]);

          setUploadError("");

        } catch (
          error
        ) {

          setUploadError(
            error?.message ||
            "Could not connect to MySQL."
          );

        } finally {

          setUploading(
            false
          );
        }

        return;
      }


      /* ------------------------------------------------------
         SQL SERVER
      ------------------------------------------------------ */

      if (
        selectedType !==
          "excel" &&
        selectedType !==
          "csv"
      ) {

        setUploadError(
          "SQL Server connection is not implemented yet."
        );

        return;
      }


      /* ------------------------------------------------------
         FILE UPLOAD
      ------------------------------------------------------ */

      setUploading(true);

      setUploadError("");


      try {

        const formData =
          new FormData();


        formData.append(
          "source_type",
          selectedType
        );


        selectedFiles.forEach(
          (
            file
          ) => {

            formData.append(
              "files",
              file
            );
          }
        );


        const response =
          await apiFetch(
            `${API_URL}/upload`,
            {
              method: "POST",
              body:
                formData,
            }
          );


        const data =
          await response.json();


        if (
          !response.ok ||
          !data.success
        ) {

          throw new Error(
            data?.detail ||
            data?.error ||
            data?.message ||
            "The data upload failed."
          );
        }


        setDataset({
          name:
            data.dataset ||
            "Uploaded dataset",

          type:
            selectedType ===
            "excel"
              ? "Excel"
              : "CSV",

          status:
            "Connected",

          source:
            "file",
        });


        setMessages([]);

        setQuestion("");

        setUploadOpen(
          false
        );

        setSelectedType(
          null
        );

        setSelectedFiles([]);

        setUploadError("");

      } catch (
        error
      ) {

        setUploadError(
          error?.message ||
          "The data upload failed."
        );

      } finally {

        setUploading(
          false
        );
      }
    };


  /* ==========================================================
     AUTHENTICATION SCREEN
  ========================================================== */

  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#05070d] text-white">
        <div className="flex items-center gap-3 text-cyan-300">
          <Loader2 className="animate-spin" size={22} />
          <span>Checking secure session...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#05070d] px-5 text-white">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(6,182,212,0.14),transparent_55%)]" />
        <div className="pointer-events-none absolute -left-24 top-1/3 h-72 w-72 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="pointer-events-none absolute -right-24 bottom-0 h-72 w-72 rounded-full bg-blue-500/10 blur-3xl" />

        <div className="relative w-full max-w-md rounded-3xl border border-white/10 bg-[#0b101a]/95 p-8 shadow-2xl shadow-black/40">
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-cyan-400/30 bg-cyan-400/10">
              <Sparkles size={24} className="text-cyan-300" />
            </div>
            <div>
              <div className="text-xl font-bold tracking-wide">QuantIQ</div>
              <div className="text-sm text-slate-400">AI Data Analyst</div>
            </div>
          </div>

          <div className="mb-7">
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
              Private workspace
            </p>
            <h1 className="text-3xl font-semibold tracking-tight">Welcome back</h1>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Sign in to securely access your data workspace.
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label htmlFor="quantiq-username" className="mb-2 block text-sm font-medium text-slate-300">
                Username
              </label>
              <input
                id="quantiq-username"
                type="text"
                autoComplete="username"
                value={loginUsername}
                onChange={(event) => setLoginUsername(event.target.value)}
                className="w-full rounded-xl border border-white/10 bg-[#070b12] px-4 py-3 text-white outline-none transition placeholder:text-slate-600 focus:border-cyan-400/70 focus:ring-2 focus:ring-cyan-400/10"
                placeholder="Enter your username"
                required
              />
            </div>

            <div>
              <label htmlFor="quantiq-password" className="mb-2 block text-sm font-medium text-slate-300">
                Password
              </label>
              <input
                id="quantiq-password"
                type="password"
                autoComplete="current-password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                className="w-full rounded-xl border border-white/10 bg-[#070b12] px-4 py-3 text-white outline-none transition placeholder:text-slate-600 focus:border-cyan-400/70 focus:ring-2 focus:ring-cyan-400/10"
                placeholder="Enter your password"
                required
              />
            </div>

            {loginError && (
              <div role="alert" className="rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm leading-5 text-red-300">
                {loginError}
              </div>
            )}

            <button
              type="submit"
              disabled={loginLoading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-400 px-4 py-3 font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loginLoading && <Loader2 size={18} className="animate-spin" />}
              {loginLoading ? "Signing in..." : "Sign in securely"}
            </button>
          </form>

          <div className="mt-6 border-t border-white/10 pt-5 text-center text-xs text-slate-500">
            Access is restricted to authorized users.
          </div>
        </div>
      </div>
    );
  }

  /* ==========================================================
     RENDER
  ========================================================== */

  return (

    <div className="relative flex h-screen overflow-hidden bg-[#05070d] text-white">

      <button
        type="button"
        onClick={handleLogout}
        title="Log out of QuantIQ"
        className="absolute bottom-4 right-4 z-50 rounded-lg border border-white/15 bg-[#101722] px-3 py-2 text-xs font-medium text-slate-300 shadow-lg transition hover:border-cyan-400/40 hover:text-cyan-200"
      >
        Log out
      </button>

      {/* ======================================================
          SIDEBAR
      ====================================================== */}

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
              disabled={disconnecting}
              className="flex w-full items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-medium transition hover:border-cyan-400/30 hover:bg-cyan-400/5 disabled:opacity-50"
            >

              {disconnecting ? (
                <Loader2
                  size={18}
                  className="animate-spin"
                />
              ) : (
                <Plus size={18} />
              )}

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

              history.map(
                (
                  item
                ) => (

                  <button
                    key={item.id}
                    onClick={() =>
                      openHistory(
                        item
                      )
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
                )
              )

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

                      {dataset.type}
                      {" • "}
                      {dataset.status}

                    </div>

                  </div>

                </div>

              </div>

            ) : (

              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">

                <div className="flex items-center gap-3">

                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/5">

                    <Database
                      size={17}
                      className="text-slate-500"
                    />

                  </div>


                  <div>

                    <div className="text-sm font-medium text-slate-400">

                      No data source

                    </div>

                    <div className="text-xs text-slate-600">

                      Connect or upload data

                    </div>

                  </div>

                </div>

              </div>

            )}

          </div>


          {/* SETTINGS */}

          <div className="border-t border-white/10 p-3">

            <button
              onClick={() =>
                setSettingsOpen(
                  true
                )
              }
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-400 hover:bg-white/5 hover:text-white"
            >

              <Settings
                size={17}
              />

              Settings

            </button>

          </div>

        </aside>

      )}


      {/* ======================================================
          MAIN
      ====================================================== */}

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


          <button
            onClick={() => {

              setUploadError("");

              setSelectedType(
                null
              );

              setSelectedFiles(
                []
              );

              setUploadOpen(
                true
              );

            }}
            className="flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 transition hover:border-cyan-400/30 hover:bg-white/5"
          >

            <Upload
              size={15}
            />

            Upload data

          </button>

        </header>


        {/* CHAT */}

        <section className="flex-1 overflow-y-auto">

          {messages.length === 0 ? (

            <div className="flex h-full items-center justify-center px-6">

              <div className="w-full max-w-3xl text-center">

                <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-400/30 bg-cyan-400/10">

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
                    ? `Ask anything about ${dataset.name} in plain English.`
                    : "Upload or connect your data and ask questions about it in plain English."}

                </p>


                <div className="mt-10 text-sm text-slate-600">

                  {dataset
                    ? "You can ask follow-up questions naturally."
                    : "Connect or upload data to get started."}

                </div>

              </div>

            </div>

          ) : (

            <div className="mx-auto w-full max-w-5xl px-6 py-8">

              {messages.map(
                (
                  message,
                  index
                ) => (

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
                      className={`max-w-[95%] rounded-2xl px-5 py-4 ${
                        message.role ===
                        "user"
                          ? "bg-cyan-400 text-slate-950"
                          : message.error
                          ? "border border-red-400/20 bg-red-400/5 text-red-300"
                          : "border border-white/10 bg-white/[0.035] text-slate-200"
                      }`}
                    >

                      <div className="whitespace-pre-line text-sm leading-7">

                        {message.content}

                      </div>


                      {message.role ===
                        "assistant" &&
                        !message.error &&
                        message.rows &&
                        message.rows.length >
                          0 && (

                        <div className="mt-5 overflow-hidden rounded-xl border border-white/10 bg-black/20">

                          <div className="flex items-center justify-between border-b border-white/10 bg-white/[0.025] px-4 py-3">

                            <div className="flex items-center gap-2">

                              <BarChart3
                                size={14}
                                className="text-cyan-300"
                              />

                              <span className="text-xs font-semibold text-slate-300">

                                Results

                              </span>

                            </div>


                            <span className="text-xs text-slate-500">

                              {message.rowCount.toLocaleString()}
                              {" "}
                              {message.rowCount === 1
                                ? "record"
                                : "records"}

                            </span>

                          </div>


                          <div className="max-h-[500px] overflow-auto">

                            <table className="min-w-full text-left text-xs">

                              <thead className="sticky top-0 z-10 border-b border-white/10 bg-[#0b0f18]">

                                <tr>

                                  {Object.keys(
                                    message.rows[0]
                                  ).map(
                                    (
                                      column
                                    ) => (

                                      <th
                                        key={
                                          column
                                        }
                                        className="whitespace-nowrap px-4 py-3 font-semibold text-cyan-300"
                                      >

                                        {column}

                                      </th>

                                    )
                                  )}

                                </tr>

                              </thead>


                              <tbody>

                                {message.rows
                                  .slice(
                                    0,
                                    100
                                  )
                                  .map(
                                    (
                                      row,
                                      rowIndex
                                    ) => (

                                      <tr
                                        key={
                                          rowIndex
                                        }
                                        className="border-b border-white/5 last:border-0 hover:bg-white/[0.03]"
                                      >

                                        {Object.keys(
                                          message.rows[0]
                                        ).map(
                                          (
                                            column
                                          ) => (

                                            <td
                                              key={
                                                column
                                              }
                                              className="whitespace-nowrap px-4 py-3 text-slate-300"
                                            >

                                              {formatValue(
                                                row[
                                                  column
                                                ]
                                              )}

                                            </td>

                                          )
                                        )}

                                      </tr>

                                    )
                                  )}

                              </tbody>

                            </table>

                          </div>


                          {message.rowCount >
                            100 && (

                            <div className="border-t border-white/10 px-4 py-3 text-xs text-slate-500">

                              Showing first 100 of{" "}
                              {message.rowCount.toLocaleString()}
                              {" "}
                              records.

                            </div>

                          )}

                        </div>

                      )}


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


        {/* INPUT */}

        <div className="shrink-0 border-t border-white/10 bg-[#070a11] px-5 py-5">

          <div className="mx-auto max-w-5xl">

            <div className="relative rounded-2xl border border-white/10 bg-white/[0.04] shadow-2xl focus-within:border-cyan-400/30">

              <textarea
                value={question}
                onChange={(
                  event
                ) =>
                  setQuestion(
                    event.target.value
                  )
                }
                onKeyDown={
                  handleKeyDown
                }
                placeholder="Ask anything about your data..."
                rows={1}
                className="w-full resize-none bg-transparent px-5 py-4 pr-14 text-sm text-white outline-none placeholder:text-slate-600"
              />


              <button
                onClick={() =>
                  askQuestion()
                }
                disabled={
                  !question.trim() ||
                  loading
                }
                className="absolute bottom-2.5 right-2.5 flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-400 text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-30"
              >

                <Send size={16} />

              </button>

            </div>


            <div className="mt-2 flex items-center justify-center gap-2 text-[11px] text-slate-600">

              <FileSpreadsheet
                size={13}
              />

              QuantIQ analyzes your connected company data

            </div>

          </div>

        </div>

      </main>


      {/* ======================================================
          SETTINGS MODAL
      ====================================================== */}

      {settingsOpen && (

        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-5 backdrop-blur-sm"
          onMouseDown={(
            event
          ) => {

            if (
              event.target ===
              event.currentTarget
            ) {

              setSettingsOpen(
                false
              );
            }
          }}
        >

          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-white/10 bg-[#0b0f18] shadow-2xl">

            <div className="flex items-center justify-between border-b border-white/10 px-6 py-5">

              <div>

                <h2 className="text-lg font-semibold">

                  Settings

                </h2>

                <p className="mt-1 text-xs text-slate-500">

                  Manage your QuantIQ workspace

                </p>

              </div>


              <button
                onClick={() =>
                  setSettingsOpen(
                    false
                  )
                }
                className="rounded-lg p-2 text-slate-500 hover:bg-white/5 hover:text-white"
              >

                <X size={18} />

              </button>

            </div>


            <div className="space-y-4 p-6">

              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">

                <div className="flex items-center justify-between">

                  <div>

                    <div className="text-sm font-medium text-slate-200">

                      Backend connection

                    </div>

                    <div className="mt-1 text-xs text-slate-500">

                      QuantIQ API server status

                    </div>

                  </div>


                  <div className="flex items-center gap-2">

                    <span
                      className={`h-2.5 w-2.5 rounded-full ${
                        backendStatus ===
                        "Connected"
                          ? "bg-emerald-400"
                          : backendStatus ===
                            "Unavailable"
                          ? "bg-red-400"
                          : "bg-yellow-400"
                      }`}
                    />

                    <span className="text-xs text-slate-400">

                      {backendStatus}

                    </span>

                  </div>

                </div>


                <button
                  type="button"
                  onClick={
                    checkBackendStatus
                  }
                  disabled={
                    backendChecking
                  }
                  className="mt-4 flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs font-medium text-slate-300 hover:bg-white/5 disabled:opacity-40"
                >

                  {backendChecking && (

                    <Loader2
                      size={14}
                      className="animate-spin"
                    />

                  )}

                  {backendChecking
                    ? "Checking..."
                    : "Check connection"}

                </button>

              </div>


              {/* CURRENT DATA */}

              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">

                <div className="flex items-center gap-3">

                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-400/10">

                    <Database
                      size={17}
                      className="text-cyan-300"
                    />

                  </div>


                  <div>

                    <div className="text-sm font-medium text-slate-200">

                      Current data source

                    </div>

                    <div className="mt-1 text-xs text-slate-500">

                      {dataset
                        ? `${dataset.name} • ${dataset.type}`
                        : "No data source connected"}

                    </div>

                  </div>

                </div>

              </div>


              {/* DISCONNECT */}

              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">

                <div className="text-sm font-medium text-slate-200">

                  Data source

                </div>

                <div className="mt-1 text-xs leading-5 text-slate-500">

                  Disconnect the current source before connecting another one.

                </div>


                <button
                  type="button"
                  onClick={
                    disconnectCurrentSource
                  }
                  disabled={
                    disconnecting ||
                    (
                      !dataset &&
                      !mysqlConnected
                    )
                  }
                  className="mt-4 flex items-center gap-2 rounded-lg border border-red-400/20 px-3 py-2 text-xs font-medium text-red-300 hover:bg-red-400/5 disabled:opacity-30"
                >

                  {disconnecting && (

                    <Loader2
                      size={14}
                      className="animate-spin"
                    />

                  )}

                  {disconnecting
                    ? "Disconnecting..."
                    : "Disconnect current source"}

                </button>

              </div>


              {/* HISTORY */}

              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">

                <div className="flex items-center justify-between">

                  <div>

                    <div className="text-sm font-medium text-slate-200">

                      Recent questions

                    </div>

                    <div className="mt-1 text-xs text-slate-500">

                      {history.length}
                      {" "}
                      saved question
                      {history.length === 1
                        ? ""
                        : "s"}

                    </div>

                  </div>


                  <button
                    type="button"
                    onClick={() => {

                      setHistory([]);

                      localStorage.removeItem(
                        "quantiq_history"
                      );

                    }}
                    disabled={
                      history.length ===
                      0
                    }
                    className="rounded-lg border border-red-400/20 px-3 py-2 text-xs font-medium text-red-300 hover:bg-red-400/5 disabled:opacity-30"
                  >

                    Clear history

                  </button>

                </div>

              </div>


              {/* ABOUT */}

              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">

                <div className="text-sm font-medium text-slate-200">

                  QuantIQ

                </div>

                <div className="mt-1 text-xs leading-5 text-slate-500">

                  AI-powered data analysis using connected databases and uploaded datasets.

                </div>

              </div>

            </div>


            <div className="flex justify-end border-t border-white/10 px-6 py-4">

              <button
                onClick={() =>
                  setSettingsOpen(
                    false
                  )
                }
                className="rounded-lg bg-cyan-400 px-5 py-2 text-sm font-medium text-slate-950 hover:bg-cyan-300"
              >

                Done

              </button>

            </div>

          </div>

        </div>

      )}


      {/* ======================================================
          UPLOAD MODAL
      ====================================================== */}

      {uploadOpen && (

        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-5 backdrop-blur-sm">

          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-white/10 bg-[#0b0f18] shadow-2xl">

            <div className="flex items-center justify-between border-b border-white/10 px-6 py-5">

              <div>

                <h2 className="text-lg font-semibold">

                  Add data

                </h2>

                <p className="mt-1 text-xs text-slate-500">

                  Connect your company data to QuantIQ

                </p>

              </div>


              <button
                onClick={() =>
                  setUploadOpen(
                    false
                  )
                }
                className="rounded-lg p-2 text-slate-500 hover:bg-white/5 hover:text-white"
              >

                <X size={18} />

              </button>

            </div>


            <div className="p-6">

              <div className="mb-4 text-sm font-medium text-slate-300">

                Choose your data source

              </div>


              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">

                {DATA_TYPES.map(
                  (
                    type
                  ) => {

                    const Icon =
                      type.icon;

                    const selected =
                      selectedType ===
                      type.id;

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
                        className={`relative rounded-xl border p-4 text-left transition ${
                          selected
                            ? "border-cyan-400/50 bg-cyan-400/10"
                            : "border-white/10 bg-white/[0.02] hover:border-cyan-400/30"
                        }`}
                      >

                        {selected && (

                          <div className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-cyan-400 text-slate-950">

                            <Check
                              size={12}
                            />

                          </div>

                        )}


                        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-400/10">

                          <Icon
                            size={20}
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


              {/* FILE */}

              {(
                selectedType ===
                  "excel" ||
                selectedType ===
                  "csv"
              ) && (

                <div className="mt-6">

                  <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-white/15 bg-white/[0.02] px-6 py-8 text-center hover:border-cyan-400/40">

                    <Upload
                      size={24}
                      className="mb-3 text-cyan-300"
                    />

                    <div className="text-sm font-medium">

                      Choose{" "}
                      {selectedType ===
                      "excel"
                        ? "Excel"
                        : "CSV"}{" "}
                      files

                    </div>

                    <div className="mt-1 text-xs text-slate-500">

                      {selectedType ===
                      "excel"
                        ? "You can select multiple Excel files"
                        : "Select CSV files"}

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


                  {selectedFiles.length >
                    0 && (

                    <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-3">

                      <div className="mb-2 text-xs font-medium text-slate-400">

                        Selected files

                      </div>


                      {selectedFiles.map(
                        (
                          file,
                          index
                        ) => (

                          <div
                            key={index}
                            className="flex items-center gap-2 py-1.5 text-xs text-slate-300"
                          >

                            <FileSpreadsheet
                              size={14}
                              className="text-cyan-400"
                            />

                            <span className="truncate">

                              {file.name}

                            </span>

                          </div>

                        )
                      )}

                    </div>

                  )}

                </div>

              )}


              {/* MYSQL */}

              {selectedType ===
                "mysql" && (

                <div className="mt-6 space-y-4">

                  <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4">

                    <div className="text-sm font-medium text-cyan-200">

                      Connect to MySQL

                    </div>

                    <p className="mt-1 text-xs leading-5 text-slate-500">

                      Enter your MySQL server details.

                    </p>

                  </div>


                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">

                    <input
                      type="text"
                      value={
                        mysqlForm.host
                      }
                      onChange={(
                        event
                      ) =>
                        handleMysqlChange(
                          "host",
                          event.target.value
                        )
                      }
                      placeholder="Host"
                      className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2.5 text-sm text-white outline-none"
                    />


                    <input
                      type="number"
                      value={
                        mysqlForm.port
                      }
                      onChange={(
                        event
                      ) =>
                        handleMysqlChange(
                          "port",
                          event.target.value
                        )
                      }
                      placeholder="Port"
                      className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2.5 text-sm text-white outline-none"
                    />


                    <input
                      type="text"
                      value={
                        mysqlForm.username
                      }
                      onChange={(
                        event
                      ) =>
                        handleMysqlChange(
                          "username",
                          event.target.value
                        )
                      }
                      placeholder="Username"
                      className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2.5 text-sm text-white outline-none"
                    />


                    <input
                      type="password"
                      value={
                        mysqlForm.password
                      }
                      onChange={(
                        event
                      ) =>
                        handleMysqlChange(
                          "password",
                          event.target.value
                        )
                      }
                      placeholder="Password"
                      className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2.5 text-sm text-white outline-none"
                    />

                  </div>


                  <div>

                    <div className="mb-1.5 flex items-center justify-between">

                      <label className="text-xs text-slate-400">

                        Database

                      </label>


                      <button
                        type="button"
                        onClick={
                          loadMysqlDatabases
                        }
                        disabled={
                          mysqlLoadingDatabases
                        }
                        className="text-xs text-cyan-300"
                      >

                        {mysqlLoadingDatabases
                          ? "Loading..."
                          : "Load databases"}

                      </button>

                    </div>


                    <select
                      value={
                        mysqlForm.database
                      }
                      onChange={(
                        event
                      ) =>
                        handleMysqlChange(
                          "database",
                          event.target.value
                        )
                      }
                      className="w-full rounded-lg border border-white/10 bg-[#0b0f18] px-3 py-2.5 text-sm text-white"
                    >

                      <option value="">

                        Select a database

                      </option>


                      {mysqlDatabases.map(
                        (
                          database
                        ) => (

                          <option
                            key={
                              database
                            }
                            value={
                              database
                            }
                          >

                            {database}

                          </option>

                        )
                      )}

                    </select>

                  </div>


                  {mysqlConnected && (

                    <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/5 px-3 py-2.5 text-xs text-emerald-300">

                      MySQL connection test successful

                    </div>

                  )}


                  <button
                    type="button"
                    onClick={
                      testMysqlConnection
                    }
                    disabled={
                      mysqlTesting ||
                      uploading
                    }
                    className="w-full rounded-lg border border-cyan-400/20 bg-cyan-400/5 px-4 py-2.5 text-sm text-cyan-300"
                  >

                    {mysqlTesting
                      ? "Testing connection..."
                      : "Test MySQL connection"}

                  </button>

                </div>

              )}


              {/* SQL SERVER */}

              {selectedType ===
                "sqlserver" && (

                <div className="mt-6 rounded-xl border border-yellow-400/20 bg-yellow-400/5 p-4">

                  <div className="text-sm font-medium text-yellow-200">

                    SQL Server connection

                  </div>

                  <p className="mt-1 text-xs text-yellow-200/60">

                    SQL Server connection is not implemented yet.

                  </p>

                </div>

              )}

            </div>


            {uploadError && (

              <div className="mx-6 mb-4 rounded-xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-xs text-red-300">

                {uploadError}

              </div>

            )}


            <div className="flex justify-end gap-3 border-t border-white/10 px-6 py-4">

              <button
                onClick={() =>
                  setUploadOpen(
                    false
                  )
                }
                className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:bg-white/5"
              >

                Cancel

              </button>


              <button
                onClick={
                  connectData
                }
                disabled={
                  !selectedType ||
                  uploading ||
                  (
                    (
                      selectedType ===
                        "excel" ||
                      selectedType ===
                        "csv"
                    ) &&
                    selectedFiles.length ===
                      0
                  )
                }
                className="rounded-lg bg-cyan-400 px-5 py-2 text-sm font-medium text-slate-950 hover:bg-cyan-300 disabled:opacity-30"
              >

                {uploading
                  ? selectedType ===
                    "mysql"
                    ? "Connecting..."
                    : "Uploading..."
                  : selectedType ===
                    "mysql"
                  ? "Connect MySQL"
                  : "Connect data"}

              </button>

            </div>

          </div>

        </div>

      )}

    </div>
  );
}


export default App;