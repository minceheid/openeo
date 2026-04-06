
  // ── Styles ────────────────────────────────────────────────────────────────────

export const globalCss = `
  * { box-sizing: border-box; }
  body { margin: 0; background: #1a1d23; }

  input[type="range"] {
    -webkit-appearance: none;
    width: 160px;
    height: 4px;
    background: #383e4d;
    border-radius: 2px;
    outline: none;
    cursor: pointer;
  }
  input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 14px; height: 14px;
    border-radius: 50%;
    background: #4a7ab8;
    cursor: pointer;
    border: 2px solid #7ab8f0;
  }
  input[type="range"]::-moz-range-thumb {
    width: 14px; height: 14px;
    border-radius: 50%;
    background: #4a7ab8;
    cursor: pointer;
    border: 2px solid #7ab8f0;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .spinner {
    display: inline-block;
    width: 14px; height: 14px;
    border: 2px solid #383e4d;
    border-top-color: #4a7ab8;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    margin-right: 8px;
    vertical-align: middle;
  }
`;

export const styles = {
  page: {
    background: "#1a1d23",
    color: "#c8cdd6",
    padding: "24px",
    fontSize: "14px",
    margin: "0 auto",
    width: "100vw",
    },
  pageTitle: {
    fontSize: "11px",
    letterSpacing: "0.15em",
    textTransform: "uppercase",
    color: "#5a8fcc",
    marginLeft: "48px",
    marginBottom: "24px",
    paddingBottom: "12px",
    borderBottom: "1px solid #2a2f3a",
    width: "100vw-48px",

  },
  section: {
    flex: 1,
    background: "#22262f",
    border: "1px solid #2e3340",
    borderRadius: "6px",
    marginBottom: "16px",
    width: "100%",
    /*overflow: "hidden",*/
  },
  sectionHeader: {
    background: "#1e2229",
    borderBottom: "1px solid #2e3340",
    padding: "10px 20px",
    fontSize: "11px",
    letterSpacing: "0.12em",
    textTransform: "uppercase",
    color: "#8899bb",
    fontWeight: 500,
  },
  fieldRow: {
    display: "flex",
    alignItems: "center",
    padding: "0 5px",
    minHeight: "52px",
    borderBottom: "1px solid #2a2f3a",
    transition: "background 0.15s",
  },
  fieldRowHover: {
    background: "#252930",
  },
  fieldLabel: {
    fontWeight: 400,
    color: "#b0b8c8",
    fontSize: "13.5px",
    //border: "1px solid #15f315",
    maxWidth: "calc(100vw - 230px)",
    width:    "calc(100vw - 230px)",
    minWidth: "calc(100vw - 230px)",

  },
  fieldNote: {
    fontSize: "11px",
    color: "#5a6275",
    marginTop: "2px",
    fontStyle: "italic",
    //border: "1px solid #eaebef",

  },
  fieldControl: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flexShrink: 0,
  },
  textInput: {
    background: "#1a1d23",
    border: "1px solid #383e4d",
    borderRadius: "4px",
    color: "#c8cdd6",
    fontSize: "12px",
    padding: "5px 10px",
    minWidth: "115px",
    outline: "none",
    transition: "border-color 0.15s",
  },
  toggleGroup: {
    display: "flex",
    gap: "4px",
  },
  toggleBtn: {
    background: "#1a1d23",
    border: "1px solid #383e4d",
    borderRadius: "3px",
    color: "#5a6275",
    cursor: "pointer",
    fontSize: "11px",
    padding: "4px 12px",
    transition: "all 0.15s",
    letterSpacing: "0.05em",
  },
  toggleYesActive: {
    background: "#1e3a5f",
    borderColor: "#4a7ab8",
    color: "#7ab8f0",
  },
  toggleNoActive: {
    background: "#3a1e1e",
    borderColor: "#884444",
    color: "#cc7777",
  },
  sliderWrap_calibration: {
    justifyContent: "initial",
    display: "flex",
    flexDirection: 'column',   
    alignItems: "center",
    gap: "10px",
//    maxWidth: "125px",
//    width: "70px",
    paddingLeft: "10px",
    paddingRight: "10px",
    paddingBottom: "10px",

  },
  sliderValue_calibration: {
    fontSize: "12px",
    color: "#7ab8f0",
  //  minWidth: "55px",
    textAlign: "center",
    
  },
  rangeInput_calibration: {
    cursor: "pointer",
    width: "100%",
  },
  ////////////////////////////////////

  sliderWrap_settings: {
    justifyContent: "initial",
    display: "flex",
    flexDirection: 'column',   
    alignItems: 'center',      
    gap: "10px",
  },
  sliderValue_settings: {
    fontSize: "12px",
    color: "#7ab8f0",
    minWidth: "55px",
    textAlign: "center",   
  },
  rangeInput_settings: {
    cursor: "pointer",
  },
  statusBox: {
    background: "#22262f",
    border: "1px solid #2e3340",
    borderRadius: "6px",
    padding: "40px",
    textAlign: "center",
    color: "#5a6275",
    fontSize: "12px",
  },
  statusError: {
    color: "#cc7777",
    borderColor: "#553333",
  },
  buttonRow: {
    display: "flex",
    justifyContent: "flex-end",
    padding: "20px 0 8px",
    flexDirection: 'row',
    gap: '16px',    
  },
  Btn: {
    background: "#1e3a5f",
    border: "1px solid #4a7ab8",
    borderRadius: "4px",
    color: "#7ab8f0",
    cursor: "pointer",
    fontSize: "12px",
    letterSpacing: "0.08em",
    padding: "9px 14px",
    textTransform: "uppercase",
    transition: "all 0.15s",
  },
};