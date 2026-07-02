import { BAMS_MENU_PRESET } from "../data/bamsMenuPreset";

export default function MenuDisplay({ config = BAMS_MENU_PRESET }) {
  const menu = config || BAMS_MENU_PRESET;

  // Split categories by panel
  const categories = menu.categories || [];
  const leftCats = categories.filter(c => (c.panel || "left") === "left");
  const middleCats = categories.filter(c => (c.panel || "left") === "middle");
  const rightCats = categories.filter(c => (c.panel || "left") === "right");

  const renderCategory = (cat) => (
    <div key={cat.id || cat.name} style={{ marginBottom: "1.2em" }}>
      {/* Category header */}
      <div style={{
        fontSize: "1.1em",
        fontWeight: "bold",
        borderBottom: "2px solid #8b6f47",
        paddingBottom: "0.3em",
        marginBottom: "0.6em",
        color: "#2c1810"
      }}>
        ✦ {cat.name} ✦
      </div>

      {/* Description */}
      {cat.description && (
        <div style={{
          fontSize: "0.75em",
          fontStyle: "italic",
          marginBottom: "0.5em",
          color: "#555",
          lineHeight: "1.3"
        }}>
          {cat.description}
        </div>
      )}

      {/* Items */}
      {cat.items && cat.items.length > 0 && (
        <div>
          {cat.items.map((item) => (
            <div key={item.id || item.name} style={{ marginBottom: "0.6em" }}>
              <div style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                gap: "0.5em"
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: "0.85em",
                    fontWeight: "600",
                    color: "#1a1a1a"
                  }}>
                    {item.name}
                  </div>
                  {item.description && (
                    <div style={{
                      fontSize: "0.7em",
                      color: "#666",
                      lineHeight: "1.2"
                    }}>
                      {item.description}
                    </div>
                  )}
                </div>
                <div style={{
                  fontSize: "0.8em",
                  fontWeight: "600",
                  color: "#2c1810",
                  whiteSpace: "nowrap",
                  textAlign: "right"
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
      fontFamily: "Georgia, serif",
      backgroundColor: "#f5f1ed",
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
        boxShadow: "0 0 20px rgba(0,0,0,0.1)",
        borderRadius: "2px",
        overflow: "hidden"
      }}>
        {/* LEFT PANEL */}
        <div style={{
          borderRight: "1px solid #ddd",
          padding: "0.3in",
          overflowY: "auto",
          fontSize: "10pt",
          backgroundColor: "#fefdfb"
        }}>
          {leftCats.map(renderCategory)}
        </div>

        {/* MIDDLE PANEL */}
        <div style={{
          borderRight: "1px solid #ddd",
          padding: "0.3in",
          overflowY: "auto",
          fontSize: "10pt",
          backgroundColor: "#fefdfb"
        }}>
          {middleCats.map(renderCategory)}
        </div>

        {/* RIGHT PANEL */}
        <div style={{
          padding: "0.3in",
          overflowY: "auto",
          fontSize: "10pt",
          backgroundColor: "#fefdfb"
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
