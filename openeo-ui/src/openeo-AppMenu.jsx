import React, { useState, useEffect } from "react";

export default function AppMenu({ links = [] }) {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") setMenuOpen(false);
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <>
      {/* Burger button */}
      <button
        onClick={() => setMenuOpen(true)}
        className="absolute top-4 left-4 z-50 w-11 h-11 rounded-xl bg-white/10 hover:bg-white/20 flex flex-col justify-center items-center gap-1"
        aria-label="Open menu"
      >
        <span className="w-5 h-0.5 bg-white"></span>
        <span className="w-5 h-0.5 bg-white"></span>
        <span className="w-5 h-0.5 bg-white"></span>
      </button>

      {/* Background overlay */}
      <div
        onClick={() => setMenuOpen(false)}
        className={`fixed inset-0 bg-black/40 backdrop-blur-sm z-40 transition-opacity duration-300 ${
          menuOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
      />

      {/* Drawer */}
      <div
        className={`fixed top-0 left-0 h-full w-64 bg-[#2b3139] shadow-2xl z-50 transform transition-transform duration-300 ${
          menuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="p-6 border-b border-white/10 flex justify-between items-center">
          <span className="font-semibold text-lg">Menu</span>

          <button
            onClick={() => setMenuOpen(false)}
            className="text-white/70 hover:text-white"
          >
            ✕
          </button>
        </div>

        <nav className="flex flex-col">
          {links.map((link, i) => (
            <a
              key={i}
              href={link.href}
              className="px-6 py-4 hover:bg-white/10 transition"
              onClick={() => setMenuOpen(false)}
            >
              {link.label}
            </a>
          ))}
        </nav>
      </div>
    </>
  );
}