import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, useSearchParams } from "react-router-dom";

import ScheduleCarousel from "./openeo-ui";
import AppMenu from "./openeo-AppMenu";
import SettingsForm from "./openeo-SettingsForm";
import Statistics from "./openeo-Statistics";
import StatisticsOS from "./openeo-StatisticsOS";
import Calibration from "./openeo-Calibration";
import ChargerSession from "./openeo-ChargerSession";
import Update from "./openeo-Update";
import { ToastProvider } from "./openeo-Toast";
import FloatingLogo from "./openeo-Logo";


import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(<App />);

function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </ToastProvider>
  );
}

function AppContent() {
  const [searchParams] = useSearchParams();
  const r = searchParams.get("r");

  const isActive = (href) => {
    const param = new URLSearchParams(href.startsWith("?") ? href.slice(1) : "").get("r");
    return r === param;
  };

  const renderPage = () => {
    switch (r) {
      case "settings":     return <SettingsForm />;
      case "statistics":   return <Statistics />;
      case "statistics_os":return <StatisticsOS />;
      case "calibration":  return <Calibration />;
      case "chargersession": return <ChargerSession />;
      case "update":       return <Update />;
      default:             return <ScheduleCarousel />;
    }
  };

  return (
    <>
      <FloatingLogo />
      <AppMenu
        links={[
          { label: "Dashboard",           href: "?r=main"                },
          { label: "Settings",            href: "?r=settings"      },
          { label: "Charging Statistics", href: "?r=statistics"    },
          { label: "Charger Statistics",  href: "?r=statistics_os" },
          { label: "CT Calibration",      href: "?r=calibration"   },
          { label: "Charging Log",        href: "?r=chargersession"},
          { label: "Update OpenEO",       href: "?r=update"        },
        ]}
        isActive={isActive}
      />
      <Routes>
        <Route path="*" element={renderPage()} />
      </Routes>
    </>
  );
}