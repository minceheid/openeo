import { useState, useEffect, useRef, useCallback } from "react";
import { buildUrl } from './utils/funcs';
import { globalCss, styles } from './utils/styles';
import { useToastContext } from "./openeo-Toast";

const SOURCES = [
  { id: "app",     label: "App Events" },
  { id: "journal", label: "Service Journal" },
];
const LINE_OPTIONS = [200, 500, 1000, 5000];
const REFRESH_MS = 5000;
// The shared toggle and input styles are compact; give every toolbar control the Btn height so the row lines up
const CONTROL = { height: "38px", boxSizing: "border-box" };
// ...and the Btn lettering, so the tabs, toggle and selector read like the Refresh/Download buttons
const LABEL = { fontSize: styles.Btn.fontSize, letterSpacing: styles.Btn.letterSpacing, textTransform: styles.Btn.textTransform };
// One gap for every box in the toolbar, including between the source tabs
const TOOLBAR_GAP = "12px";

export default function LogViewer() {
  const addToast = useToastContext();

  const [source, setSource] = useState("app");
  const [lines, setLines] = useState(500);
  const [filter, setFilter] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [content, setContent] = useState("");
  const [loadedKey, setLoadedKey] = useState(null);
  const outputRef = useRef(null);
  const followRef = useRef(true);

  // The spinner shows until the content matches the selected source and line count
  const queryKey = `${source}:${lines}`;
  const loading = loadedKey !== queryKey;

  const fetchLogs = useCallback(() => {
    fetch(buildUrl(`getlogs?source=${source}&lines=${lines}`))
      .then((r) => r.json())
      .then((data) => {
        setContent(data["content"] ?? "");
        setLoadedKey(`${source}:${lines}`);
      })
      .catch((err) => {
        console.log("Error fetching logs:", err);
        addToast({ type: "error", title: "Logs", message: "Unable to fetch logs" });
      });
  }, [source, lines, addToast]);

  // Refetch whenever the source or line count changes
  useEffect(() => {
    followRef.current = true;
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(fetchLogs, REFRESH_MS);
    return () => clearInterval(timer);
  }, [autoRefresh, fetchLogs]);

  const needle = filter.trim().toLowerCase();
  const visible = needle
    ? content.split("\n").filter((line) => line.toLowerCase().includes(needle)).join("\n")
    : content;

  // Tail-follow: stay pinned to the bottom unless the user has scrolled up
  useEffect(() => {
    if (outputRef.current && followRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [visible]);

  const onScroll = (e) => {
    const el = e.target;
    followRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 20;
  };

  const download = () => {
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const url = URL.createObjectURL(new Blob([visible], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `openeo-${source}-${stamp}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const lineCount = visible ? visible.split("\n").filter(Boolean).length : 0;

  return (
    <div style={styles.page}>
      <style>{globalCss}</style>
      <div style={styles.pageTitle}>// System Logs</div>

      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: TOOLBAR_GAP, marginBottom: "12px" }}>
        <div style={{ ...styles.toggleGroup, gap: TOOLBAR_GAP }}>
          {SOURCES.map((s) => (
            <button
              key={s.id}
              style={{ ...styles.toggleBtn, ...CONTROL, ...LABEL, ...(source === s.id && styles.toggleYesActive) }}
              onClick={() => setSource(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>

        <select
          style={{ ...styles.textInput, ...CONTROL, ...LABEL }}
          value={lines}
          onChange={(e) => setLines(Number(e.target.value))}
          aria-label="Number of lines"
        >
          {LINE_OPTIONS.map((n) => (
            <option key={n} value={n}>{n} lines</option>
          ))}
        </select>

        <input
          type="text"
          style={{ ...styles.textInput, ...CONTROL, flex: 1, minWidth: "160px" }}
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter log lines"
        />

        <button
          style={{ ...styles.toggleBtn, ...CONTROL, ...LABEL, ...(autoRefresh && styles.toggleYesActive) }}
          onClick={() => {
            // Fetch straight away when switching on, rather than waiting for the first interval
            if (!autoRefresh) fetchLogs();
            setAutoRefresh((v) => !v);
          }}
          aria-pressed={autoRefresh}
        >
          Auto-refresh
        </button>
        <button style={styles.Btn} onClick={download} disabled={!visible}>Download</button>
      </div>

      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          {loading && <span className="spinner" />}
          {SOURCES.find((s) => s.id === source)?.label} · {lineCount} lines{needle && " (filtered)"}
        </div>
        <textarea
          ref={outputRef}
          className="update-log"
          readOnly
          value={visible}
          onScroll={onScroll}
          spellCheck={false}
          style={{ height: '70vh', width: '100%', boxSizing: 'border-box', fontFamily: 'monospace', whiteSpace: 'pre', overflowWrap: 'normal' }}
        />
      </div>
    </div>
  );
}
