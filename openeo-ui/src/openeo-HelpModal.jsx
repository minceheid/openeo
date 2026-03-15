import React, { useState } from "react";

export default function HelpModal({ title = "Help", children }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Help icon button */}
      <button
        onClick={() => setOpen(true)}
        className="absolute top-3 right-3 w-7 h-7 flex items-center justify-center
        rounded-full bg-white/10 hover:bg-white/20 text-white font-bold
        backdrop-blur transition"
      >
        ?
      </button>

      {/* Modal overlay */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          
          {/* Modal window */}
          <div className="relative w-[90%] max-w-lg bg-gray-900 text-white rounded-2xl shadow-2xl p-6">

            {/* Close button */}
            <button
              onClick={() => setOpen(false)}
              className="absolute top-3 right-3 text-white/70 hover:text-white text-xl"
            >
              ✕
            </button>

            {/* Title */}
            <h2 className="text-2xl font-semibold mb-4">
              {title}
            </h2>

            {/* Content */}
            <div className="text-white/80 leading-relaxed space-y-3">
              {children}
            </div>

          </div>
        </div>
      )}
    </>
  );
}