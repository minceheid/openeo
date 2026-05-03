import { useRef, useState, useEffect } from "react";

export default function Toggle({ enabled, onChange }) {
  return (
    <div
      className="relative w-40 h-20 rounded-full bg-gray-700 transition-colors cursor-pointer select-none"
      style={{ touchAction: "manipulation" }}
      onClick={() => onChange(!enabled)}
    >
      {/* Active track */}
      <div
        className={`absolute inset-0 rounded-full transition-colors ${
          enabled ? "bg-blue-500" : "bg-gray-700"
        }`}
      />

      {/* Thumb */}
      <div
        className="absolute top-3 w-15 h-15 bg-white rounded-full shadow-md transition-transform"
        style={{
          transform: enabled ? "translateX(96px)" : "translateX(12px)"
        }}
      />
    </div>
  );
}
