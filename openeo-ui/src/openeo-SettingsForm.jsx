import { useState, useEffect, useRef, useCallback } from "react";
import { buildUrl } from './utils/funcs';
import { globalCss,styles } from './utils/styles';
import { useToastContext } from "./openeo-Toast";

function initFormData(schema) {
  const data = {};
  console.log(schema);
  Object.entries(schema).forEach(([modulename, modulesettings]) => {
    modulesettings.fields.forEach(field => {
    //for (const field of fields) {
      let val =
        field.current !== undefined
          ? field.current
          : field.default !== false && field.default !== undefined
          ? field.default
          : "";
      if (field.type === "boolean") val = val === true || val === "true";
      if (field.type === "slider")
        val = typeof val === "number" ? val : field.range ? field.range[0] : 0;
      data[modulename+":"+field.name] = val;
    });
  });
  console.log(data);
  return data;
}

// ── Field Components ──────────────────────────────────────────────────────────

function TextInput({ field, value, onChange }) {
  const isPassword = field.name.toLowerCase().includes("password");
  return (
    <input
      type={isPassword ? "password" : "text"}
      name={field.name}
      value={value ?? ""}
      pattern={field.pattern}
      onChange={(e) => onChange(field.name, e.target.value)}
      style={styles.textInput}
      onFocus={(e) => (e.target.style.borderColor = "#4a7ab8")}
      onBlur={(e) => (e.target.style.borderColor = "#383e4d")}
    />
  );
}

function BooleanToggle({ field, value, onChange }) {
  return (
    <div style={styles.toggleGroup}>
      <button
        name={field.name + ":true"} 
        onClick={() => onChange(field.name, true)}
        style={{
          ...styles.toggleBtn,
          ...(value === true ? styles.toggleYesActive : {}),
        }}
      >
        Yes
      </button>
      <button
        name={field.name + ":false"} 
        onClick={() => onChange(field.name, false)}
        style={{
          ...styles.toggleBtn,
          ...(value === false ? styles.toggleNoActive : {}),
        }}
      >
        No
      </button>
    </div>
  );
}

function SliderInput({ field, value, onChange }) {
  const min = field.range?.[0] ?? 0;
  const max = field.range?.[1] ?? 100;
  const step = field.step ?? 1;
  const trackRef = useRef(null);
 
  const calcValueFromTouch = useCallback((touch) => {
    const rect = trackRef.current.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width));
    const raw = min + ratio * (max - min);
    const stepped = Math.round(raw / step) * step;
    return Math.max(min, Math.min(max, stepped));
  }, [min, max, step]);
 
  const handleTouchMove = useCallback((e) => {
    //e.preventDefault(); // stop page scroll while dragging
    onChange(field.name, calcValueFromTouch(e.touches[0]));
  }, [field.name, onChange, calcValueFromTouch]);
 
  const handleTouchStart = useCallback((e) => {
    onChange(field.name, calcValueFromTouch(e.touches[0]));
  }, [field.name, onChange, calcValueFromTouch]);
 
  // Must attach touchmove as non-passive so preventDefault works on iOS
  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    el.addEventListener("touchmove", handleTouchMove, { passive: false });
    return () => el.removeEventListener("touchmove", handleTouchMove);
  }, [handleTouchMove]);
 
  return (
    <div style={styles.sliderWrap_settings}>
      <span style={styles.sliderValue_settings}>
        {value}
        {field.value_unit ? ` ${field.value_unit}` : ""}
      </span>
      <input
        ref={trackRef}
        name={field.name}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(field.name, Number(e.target.value))}
        onTouchStart={handleTouchStart}
        style={styles.rangeInput_settings}
      />
    </div>
  );
}

function FieldRow({ field, value, onChange }) {
  const [hovered, setHovered] = useState(false);
  let control = null;
  if (field.type === "textinput")
    control = <TextInput field={field} value={value} onChange={onChange} />;
  else if (field.type === "boolean")
    control = <BooleanToggle field={field} value={value} onChange={onChange} />;
  else if (field.type === "slider")
    control = <SliderInput field={field} value={value} onChange={onChange} />;

  return (
    <div
      style={{
        ...styles.fieldRow,
        ...(hovered ? styles.fieldRowHover : {}),
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div style={styles.fieldLabel}>
        <span>{field.label}</span>
        {field.note && <div style={styles.fieldNote}>{field.note}</div>}
      </div>
    <div
      id="controldiv"
      style={{
        display: "flex",
        justifyContent: "center",  // horizontal centering
        alignItems: "center",      // vertical centering (optional)
        flex: 1,  
      }}>        
        <div style={styles.fieldControl}>{control}</div>
      </div>
    </div>
  );
}

function Section({ sectionKey, sectionName, fields, formData, onChange }) {
  const label = sectionName || sectionKey;
  const updatedFields = fields.map(item => ({ ...item, name: sectionKey+":"+item.name }));
  return (
    <div style={styles.section}>
      <div style={styles.sectionHeader}>{label}</div>
      {updatedFields.map((field) => (
        <FieldRow
          key={field.name}
          field={field}
          value={formData[field.name]}
          onChange={onChange}
        />
      ))}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function SettingsForm() {
  const addToast = useToastContext();

  const [schema, setSchema] = useState(null);
  const [formData, setFormData] = useState({});
  const [status, setStatus] = useState("loading"); // loading | ready | error

  useEffect(() => {
    fetch(buildUrl("get_user_settings"), { method: "GET" })
      .then((res) => {
        if (!res.ok) throw new Error("Network error");
        return res.json();
      })
      .then((data) => {
        setSchema(data);
        setFormData(initFormData(data));
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  function handleChange(name, value) {
    setFormData((prev) => ({ ...prev, [name]: value }));
  }

  function handleSave() {
    const response = fetch(buildUrl("setsettings"),
      {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams(formData).toString(),
      })
      .then(response => {  
        console.log(response);
        if (!response.ok) {
          addToast({type: "error", title: "Saving", message: "An error occurred (HTTP "+response.status+") - settings may have not been saved: "});
          throw new Error(`Response status: ${response.status}`);
        } else {
          addToast({ type: "success", title: "Saving", message: "Settings have been saved" });
        }
      })
  }
  function handleRestart() {
    fetch(buildUrl("restart")).then(() => {});
    addToast({ type: "success", title: "Restarting", message: "Waiting for openeo to restart..." });
    window.setTimeout(() => { location.reload();}, 7000); // 7 seconds, by experimenting, is enough.
  }

  return (
    <div style={styles.page}>
      <style>{globalCss}</style>
      <div style={styles.pageTitle}>// Device Configuration</div>

      {status === "loading" && (
        <div style={styles.statusBox}>
          <span className="spinner" /> Loading settings…
        </div>
      )}

      {status === "error" && (
        <div style={{ ...styles.statusBox, ...styles.statusError }}>
          ⚠ Failed to load settings from /get_user_settings
        </div>
      )}

      {status === "ready" && schema && (
        <>
          {Object.entries(schema).map(([key, section]) => (
            <Section
              key={key}
              sectionKey={key}
              sectionName={section.name}
              fields={section.fields}
              formData={formData}
              onChange={handleChange}
            />
          ))}
          <div style={styles.buttonRow}>
            <button style={styles.Btn} onClick={handleSave}
              onMouseEnter={(e) => {
                e.target.style.background = "#254870";
                e.target.style.borderColor = "#7ab8f0";
              }}
              onMouseLeave={(e) => {
                e.target.style.background = "#1e3a5f";
                e.target.style.borderColor = "#4a7ab8";
              }}
            >
              Save Settings
            </button>

            <button style={styles.Btn} onClick={handleRestart}
              onMouseEnter={(e) => {
                e.target.style.background = "#254870";
                e.target.style.borderColor = "#7ab8f0";
              }}
              onMouseLeave={(e) => {
                e.target.style.background = "#1e3a5f";
                e.target.style.borderColor = "#4a7ab8";
              }}
            >
              Restart OpenEO
            </button>
          </div>
        </>
      )}
    </div>
  );
}