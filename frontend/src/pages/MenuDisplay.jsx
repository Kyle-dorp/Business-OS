import { BAMS_MENU_PRESET } from "../data/bamsMenuPreset";

export default function MenuDisplay({ config = BAMS_MENU_PRESET }) {
  const menu = config || BAMS_MENU_PRESET;
  const categories = menu.categories || [];

  // Separate categories by side (front/back of pamphlet)
  const frontCats = categories.filter(c => (c.side || "front") === "front");
  const backCats = categories.filter(c => (c.side || "front") === "back");

  const renderCategory = (cat) => (
    <div key={cat.id || cat.name} style={{ marginBottom: "1.2em" }}>
      {/* Brown header with sunburst - matching original design */}
      <div style={{
        backgroundColor: "#9B6B47",
        color: "white",
        padding: "0.4em 0.5em",
        fontSize: "1.2em",
        fontWeight: "bold",
        fontStyle: "italic",
        textAlign: "center",
        marginBottom: "0.6em",
        border: "2px solid #7a5434",
        letterSpacing: "0.05em"
      }}>
        ✦ {cat.name} ✦
      </div>

      {/* Description */}
      {cat.description && (
        <div style={{
          fontSize: "0.78em",
          fontStyle: "italic",
          marginBottom: "0.5em",
          color: "#5a4a3a",
          lineHeight: "1.4"
        }}>
          {cat.description}
        </div>
      )}

      {/* Items */}
      {cat.items && cat.items.length > 0 && (
        <div>
          {cat.items.map((item) => (
            <div key={item.id || item.name} style={{ marginBottom: "0.5em" }}>
              <div style={{
                display: "flex",
                justifyContent: "space-between",
                gap: "0.5em"
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: "0.85em",
                    fontWeight: "bold",
                    color: "#1a1a1a"
                  }}>
                    {item.name}
                  </div>
                  {item.description && (
                    <div style={{
                      fontSize: "0.7em",
                      color: "#555",
                      lineHeight: "1.25"
                    }}>
                      {item.description}
                    </div>
                  )}
                </div>
                <div style={{
                  fontSize: "0.8em",
                  fontWeight: "bold",
                  color: "#1a1a1a",
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
    <div style={{ fontFamily: "Georgia, serif", backgroundColor: "#f0f0f0", padding: "20px" }}>
      {/* PAGE 1 - FRONT (inside of pamphlet) */}
      <div style={{
        width: "8.5in",
        height: "11in",
        margin: "0 auto 20px",
        padding: "0.5in",
        backgroundColor: "#FFF8F3",
        boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
        pageBreakAfter: "always",
        display: "grid",
        gridTemplateColumns: "1fr 1fr 1fr",
        gap: "0.3in",
        fontSize: "9pt",
        lineHeight: "1.4"
      }}>
        {/* LEFT COLUMN - Classic Subs, Breads, Desserts */}
        <div style={{ overflowY: "auto", paddingRight: "0.2in" }}>
          {frontCats
            .filter(c => (c.panel || "left") === "left")
            .map(renderCategory)}
        </div>

        {/* MIDDLE COLUMN - Specialty Subs, Sub Salads */}
        <div style={{ overflowY: "auto", paddingRight: "0.2in" }}>
          {frontCats
            .filter(c => (c.panel || "left") === "middle")
            .map(renderCategory)}
        </div>

        {/* RIGHT COLUMN - Dressings, Photos, Quote */}
        <div style={{ overflowY: "auto", paddingLeft: "0.2in" }}>
          {frontCats
            .filter(c => (c.panel || "left") === "right")
            .map(renderCategory)}

          {/* Quality statement */}
          {menu.ingredientStatement && (
            <div style={{
              marginTop: "1.2em",
              paddingTop: "1em",
              borderTop: "2px solid #D4A574",
              fontSize: "0.75em",
              fontStyle: "italic",
              color: "#9B6B47",
              lineHeight: "1.4",
              textAlign: "center"
            }}>
              {menu.ingredientStatement}
            </div>
          )}

          {/* Quote */}
          {menu.closingQuote && (
            <div style={{
              marginTop: "1.5em",
              padding: "0.5em",
              fontSize: "0.8em",
              fontStyle: "italic",
              color: "#9B6B47",
              textAlign: "center",
              lineHeight: "1.5"
            }}>
              "{menu.closingQuote}"
            </div>
          )}
        </div>
      </div>

      {/* PAGE 2 - BACK (outside/info page) */}
      <div style={{
        width: "8.5in",
        height: "11in",
        margin: "0 auto",
        padding: "0.5in",
        backgroundColor: "#FFF8F3",
        boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
        display: "grid",
        gridTemplateColumns: "1fr 1fr 1fr",
        gap: "0.3in",
        fontSize: "9pt",
        lineHeight: "1.4"
      }}>
        {/* LEFT COLUMN - Combos, Breads, Desserts */}
        <div style={{ overflowY: "auto", paddingRight: "0.2in" }}>
          {backCats
            .filter(c => (c.panel || "left") === "left")
            .map(renderCategory)}
        </div>

        {/* MIDDLE COLUMN - Soups, Extras, Catering */}
        <div style={{ overflowY: "auto", paddingRight: "0.2in" }}>
          {backCats
            .filter(c => (c.panel || "left") === "middle")
            .map(renderCategory)}
        </div>

        {/* RIGHT COLUMN - Business Info */}
        <div style={{ overflowY: "auto", paddingLeft: "0.2in" }}>
          {/* Hours */}
          {menu.hours && (
            <div style={{ marginBottom: "1.5em" }}>
              <div style={{
                fontSize: "1.1em",
                fontWeight: "bold",
                color: "#9B6B47",
                textAlign: "center",
                marginBottom: "0.5em"
              }}>
                Hours
              </div>
              <div style={{ fontSize: "0.8em" }}>
                {Object.entries(menu.hours).map(([day, hours]) => (
                  <div key={day} style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: "0.2em"
                  }}>
                    <span style={{ fontWeight: "bold" }}>{day.charAt(0).toUpperCase() + day.slice(1)}</span>
                    <span>{hours}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Delivery */}
          {menu.delivery && (
            <div>
              <div style={{
                fontSize: "1.1em",
                fontWeight: "bold",
                color: "#9B6B47",
                textAlign: "center",
                marginBottom: "0.5em"
              }}>
                We Deliver
              </div>
              <div style={{ fontSize: "0.8em" }}>
                {menu.delivery.map((d, i) => (
                  <div key={i} style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: "0.2em"
                  }}>
                    <span>{d.location}</span>
                    <span>{d.surcharge}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Contact info */}
          {menu.phone && (
            <div style={{ marginTop: "1.5em", textAlign: "center" }}>
              <div style={{ fontSize: "0.9em", fontWeight: "bold", marginBottom: "0.3em" }}>
                {menu.address}
              </div>
              <div style={{ fontSize: "0.8em", marginBottom: "0.5em" }}>
                {menu.city}
              </div>
              <div style={{ fontSize: "1em", fontWeight: "bold", color: "#000" }}>
                {menu.phone}
              </div>
            </div>
          )}
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
            size: letter;
            margin: 0;
          }
        }
      `}</style>
    </div>
  );
}
