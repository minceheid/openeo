import { useRef, useState } from "react";

export default function AmpSlider({ value, min = 0, max = 32, onChange, onCommit,active }) {
  const trackRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const activePointer = useRef(null); // tracks active touch/mouse
  const startPos = useRef(null);      // tracks start position for horizontal intent

  // compute slider percent
  const percent = ((value - min) / (max - min)) * 100;

  // convert clientX to slider value
  const updateValueFromX = (clientX) => {
    const rect = trackRef.current.getBoundingClientRect();
    const x = Math.min(Math.max(clientX - rect.left, 0), rect.width);
    const ratio = x / rect.width;
    const newValue = Math.round(min + ratio * (max - min));
    onChange(newValue);
  };

  // start drag
  const startDrag = (clientX, clientY, pointerId) => {
    activePointer.current = pointerId;
    startPos.current = { x: clientX, y: clientY };
    setDragging(true);
    updateValueFromX(clientX);
  };

  // move drag
  const moveDrag = (clientX, clientY, pointerId) => {
    if (!dragging || activePointer.current !== pointerId) return;

    // horizontal intent check
    const dx = Math.abs(clientX - startPos.current.x);
    const dy = Math.abs(clientY - startPos.current.y);
    if (dy > dx && dx < 5) return; // ignore mostly vertical gestures

    updateValueFromX(clientX);
  };

  // end drag
  const endDrag = (pointerId) => {
    if (activePointer.current !== pointerId) return;
    setDragging(false);
    activePointer.current = null;
    startPos.current = null;
    onCommit?.();
  };

  return (
  <div id="AmpSlider" className="w-full select-none">
      {/* Gesture Area */}
<div
  ref={trackRef}
  className={`relative h-10 flex items-center justify-center ${!active ? "cursor-not-allowed" : "cursor-pointer"}`}
  style={{ touchAction: "none" }}
  {...(active
    ? {
        onTouchStart: (e) => startDrag(e.touches[0].clientX, e.touches[0].clientY, e.touches[0].identifier),
        onTouchMove: (e) => moveDrag(e.touches[0].clientX, e.touches[0].clientY, e.touches[0].identifier),
        onTouchEnd: (e) => endDrag(e.changedTouches[0].identifier),
        onMouseDown: (e) => startDrag(e.clientX, e.clientY, "mouse"),
        onMouseMove: (e) => moveDrag(e.clientX, e.clientY, "mouse"),
        onMouseUp: (e) => endDrag("mouse"),
      }
    : {})}
>

        {/* Track */}
        <div className="absolute left-0 right-0 h-2 rounded-full bg-white/20" />

        {/* Active Track */}
        <div
          className="absolute left-0 h-2 rounded-full bg-white"
          style={{ width: `${percent}%` }}
        />

        {/* Thumb */}
        <div
          className="absolute top-1/2 w-10 h-10 bg-white rounded-full shadow-lg"
          style={{
            left: `calc(${percent}% - 20px)`,
            transform: "translateY(-50%)"
          }}
        />
      </div>

      {/* Value display */}
      <div className="w-full max-width container text-center text-white text-3xl font-semibold mt-0">
        {value}A
      </div>
    </div>
  );
}
