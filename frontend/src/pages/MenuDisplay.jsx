import { BAMS_MENU_PRESET } from "../data/bamsMenuPreset";

export default function MenuDisplay({ config = BAMS_MENU_PRESET }) {
  const menu = config || BAMS_MENU_PRESET;

  // Split categories by panel
  const categories = menu.categories || [];
  const leftCats = categories.filter(c => (c.panel || "left") === "left");
  const middleCats = categories.filter(c => (c.panel || "left") === "middle");
  const rightCats = categories.filter(c => (c.panel || "left") === "right");

  const renderCategory = (cat) => (
    <div key={cat.id || cat.name} style={{ marginBottom: "1.4em" }}>
      {/* Category header - bold retro deli style */}
      <div style={{
        fontSize: "1.15em",
        fontWeight: "900",
        fontFamily: "'Arial Black', sans-serif",
        color: "white",
        backgroundColor: "#CC2222",
        border: "3px solid #000",
        padding: "0.35em 0.4em",
        marginBottom: "0.7em",
        textAlign: "center",
        letterSpacing: "0.05em",
        boxShadow: "3px 3px 0px rgba(0,0,0,0.2)",
        textShadow: "1px 1px 2px rgba(0,0,0,0.3)",
        transform: "skewX(-2deg)"
      }}>
        ★ {cat.name} ★
      </div>

      {/* Description */}
      {cat.description && (
        <div style={{
          fontSize: "0.72em",
          fontStyle: "italic",
          marginBottom: "0.6em",
          color: "#333",
          lineHeight: "1.35",
          borderLeft: "3px solid #FFD700",
          paddingLeft: "0.5em"
        }}>
          {cat.description}
        </div>
      )}

      {/* Items */}
      {cat.items && cat.items.length > 0 && (
        <div>
          {cat.items.map((item) => (
            <div key={item.id || item.name} style={{
              marginBottom: "0.7em",
              paddingBottom: "0.5em",
              borderBottom: "1px dotted #ccc"
            }}>
              <div style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                gap: "0.4em"
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: "0.88em",
                    fontWeight: "800",
                    color: "#000",
                    fontFamily: "'Arial Black', sans-serif",
                    letterSpacing: "0.02em"
                  }}>
                    {item.name}
                  </div>
                  {item.description && (
                    <div style={{
                      fontSize: "0.68em",
                      color: "#444",
                      lineHeight: "1.25",
                      marginTop: "0.2em"
                    }}>
                      {item.description}
                    </div>
                  )}
                </div>
                <div style={{
                  fontSize: "0.82em",
                  fontWeight: "800",
                  color: "#CC2222",
                  whiteSpace: "nowrap",
                  textAlign: "right",
                  fontFamily: "'Arial Black', sans-serif"
                }}>
                  {item.sizes ? (
                    <div>
                      <div>6" ${item.sizes["6\""] || "—"}</div>
                      <div>12" ${item.sizes["12\""] || "—"}</div>
                    </div>
                  ) : (
                    <div>${item.price || "—"}</div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div style={{
      fontFamily: "'Courier New', monospace",
      backgroundColor: "#f0f0f0",
      padding: "20px",
      minHeight: "100vh"
    }}>
      {/* Main menu container */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr 1fr",
        gap: "0",
        width: "11in",
        height: "8.5in",
        margin: "0 auto",
        backgroundColor: "white",
        boxShadow: "0 8px 24px rgba(0,0,0,0.15), inset 0 0 80px rgba(0,0,0,0.02)",
        border: "2px solid #333",
        overflow: "hidden",
        position: "relative"
      }}>
        {/* Grid line separators - retro style */}
        <div style={{
          position: "absolute",
          left: "33.333%",
          top: 0,
          width: "2px",
          height: "100%",
          backgroundColor: "#999",
          zIndex: 1
        }} />
        <div style={{
          position: "absolute",
          left: "66.666%",
          top: 0,
          width: "2px",
          height: "100%",
          backgroundColor: "#999",
          zIndex: 1
        }} />

        {/* LEFT PANEL */}
        <div style={{
          padding: "0.35in 0.25in",
          overflowY: "auto",
          fontSize: "9.5pt",
          backgroundColor: "white",
          position: "relative",
          zIndex: 2
        }}>
          {leftCats.map(renderCategory)}
        </div>

        {/* MIDDLE PANEL */}
        <div style={{
          padding: "0.35in 0.25in",
          overflowY: "auto",
          fontSize: "9.5pt",
          backgroundColor: "white",
          position: "relative",
          zIndex: 2
        }}>
          {middleCats.map(renderCategory)}
        </div>

        {/* RIGHT PANEL */}
        <div style={{
          padding: "0.35in 0.25in",
          overflowY: "auto",
          fontSize: "9.5pt",
          backgroundColor: "white",
          position: "relative",
          zIndex: 2
        }}>
          {rightCats.map(renderCategory)}
        </div>
      </div>

      <style>{`
        @media print {
          body, html {
            margin: 0;
            padding: 0;
            background: white;
          }
          * {
            margin: 0;
            padding: 0;
            border: 0;
          }
          @page {
            size: 11in 8.5in landscape;
            margin: 0;
          }
        }
      `}</style>
    </div>
  );
}
