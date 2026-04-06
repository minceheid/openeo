import { useState, useEffect } from "react";

const styles = `

  .floating-logo-wrapper {
    position: fixed;
    top: 16px;
    right: 16px;
    z-index: 9999;
    pointer-events: auto;
  }

  .floating-logo-link {
    display: flex;
    align-items: center;
    gap: 10px;
    text-decoration: none;
    padding: 8px 14px 8px 10px;
    border-radius: 10px;
    background: rgba(10, 10, 10, 0.75);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow:
      0 4px 24px rgba(0, 0, 0, 0.35),
      0 1px 0 rgba(255, 255, 255, 0.06) inset;
    transition: background 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease;
  }

  .floating-logo-link:hover {
    background: rgba(20, 20, 20, 0.9);
    box-shadow:
      0 6px 32px rgba(0, 0, 0, 0.5),
      0 1px 0 rgba(255, 255, 255, 0.1) inset;
    transform: translateY(-1px);
  }

  .floating-logo-link:active {
    transform: translateY(0px);
  }

  .logo-img {
    display: block;
    flex-shrink: 0;
    filter: brightness(0.95);
    transition: filter 0.2s ease;
  }

  .floating-logo-link:hover .logo-img {
    filter: brightness(1.1);
  }

  .logo-text {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: rgba(255, 255, 255, 0.92);
    white-space: nowrap;
    transition: color 0.2s ease;
  }

  .floating-logo-link:hover .logo-text {
    color: #ffffff;
  }

  /* Hide logo-text on narrow screens */
  @media (max-width: 480px) {
    .logo-text {
      display: none;
    }

    .floating-logo-link {
      padding: 8px;
      border-radius: 10px;
    }

    .logo-img {
      width: 35px;
      height: 35px;
    }
  }
`;

export default function FloatingLogo() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <>
      <style>{styles}</style>
      <div
        className="floating-logo-wrapper"
        style={{
          opacity: mounted ? 1 : 0,
          transition: "opacity 0.4s ease 0.1s",
        }}
      >
        <a
          href="https://github.com/minceheid/openeo"
          className="floating-logo-link"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="openeo on GitHub"
        >
          <span className="logo-text">openeo</span>
          <img
            src="static/openeo_vector_glyph_lightmono.svg"
            width="50"
            height="50"
            alt="openeo logo"
            className="logo-img"
          />
        </a>
      </div>
    </>
  );
}