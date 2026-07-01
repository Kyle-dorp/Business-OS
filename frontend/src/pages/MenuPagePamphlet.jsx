import { useState, useEffect } from "react";

/**
 * VINTAGE BAM'S PAMPHLET MENU
 * Fixed 11" × 8.5" landscape tri-fold layout
 * Three explicit panels with predetermined content placement
 */

export default function MenuPagePamphlet({ config: rawConfig, businessName, onSaveConfig }) {
  const [menu, setMenu] = useState(rawConfig || {});
  const [editMode, setEditMode] = useState(false);

  const canEdit = typeof onSaveConfig === "function";

  // Parse categories by their panel assignment
  const getPanel = (panel) => {
    return (menu.categories || []).filter((c) => (c.panel || "left") === panel);
  };

  const leftPanel = getPanel("left");
  const middlePanel = getPanel("middle");
  const rightPanel = getPanel("right");

  const renderItem = (item) => (
    <div key={item.id || item.name} className="menu-item">
      <div className="menu-item-name">{item.name}</div>
      {item.description && <div className="menu-item-description">{item.description}</div>}
      {item.sizes ? (
        <>
          <div className="menu-price-6">${item.sizes["6\""] || "—"}</div>
          <div className="menu-price-12">${item.sizes["12\""] || "—"}</div>
        </>
      ) : (
        <>
          <div className="menu-price-6">{item.price ? `$${item.price}` : "—"}</div>
          <div className="menu-price-12"></div>
        </>
      )}
    </div>
  );

  const renderCategory = (category) => (
    <section key={category.id || category.name}>
      <header className="section-banner">
        <span className="sunburst" aria-hidden="true">✦</span>
        <h2>{category.name}</h2>
        <span className="sunburst" aria-hidden="true">✦</span>
      </header>

      {category.description && (
        <p className="section-intro">{category.description}</p>
      )}

      {category.items && category.items.length > 0 && (
        <>
          <div className="price-header">
            <span></span>
            <span className="price-header-6in">6"</span>
            <span className="price-header-12in">12"</span>
          </div>
          <div className="menu-items-list">
            {category.items.map(renderItem)}
          </div>
        </>
      )}

      {category.image_url && (
        <div className="photo-container">
          <img
            src={category.image_url}
            alt={category.name}
            className="large-photo"
            onError={(e) => (e.target.style.display = "none")}
          />
        </div>
      )}
    </section>
  );

  const renderDressingsCategory = (category) => (
    <section key={category.id || category.name}>
      <header className="section-banner">
        <span className="sunburst" aria-hidden="true">✦</span>
        <h2>{category.name}</h2>
        <span className="sunburst" aria-hidden="true">✦</span>
      </header>

      {category.description && (
        <p className="section-intro">{category.description}</p>
      )}

      {category.items && category.items.length > 0 && (
        <div className="dressings-list">
          {category.items.map((item) => (
            <div key={item.id || item.name} className="dressing-item">
              {item.name}
            </div>
          ))}
        </div>
      )}
    </section>
  );

  const renderSaladsTable = (category) => (
    <section key={category.id || category.name} className="sub-salads-section">
      <header className="section-banner">
        <span className="sunburst" aria-hidden="true">✦</span>
        <h2>{category.name}</h2>
        <span className="sunburst" aria-hidden="true">✦</span>
      </header>

      {category.description && (
        <p className="section-intro">{category.description}</p>
      )}

      {category.items && category.items.length > 0 && (
        <>
          <div className="salad-header">
            <span></span>
            <span className="price-header-6in">12"</span>
            <span className="price-header-12in">6"</span>
          </div>
          <div className="menu-items-list">
            {category.items.map((item) => (
              <div key={item.id || item.name} className="salad-row">
                <div>{item.name}</div>
                <div style={{ textAlign: "right" }}>
                  ${item.sizes ? item.sizes["12\""] || "—" : item.price || "—"}
                </div>
                <div style={{ textAlign: "right" }}>
                  ${item.sizes ? item.sizes["6\""] || "—" : "—"}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );

  return (
    <div className="menu-page-wrapper">
      <style>{`
        @page {
          size: letter landscape;
          margin: 0;
        }
      `}</style>

      <div className="menu-page">
        {/* LEFT PANEL: Classic Subs */}
        <div className="menu-panel">
          <div className="menu-panel-inner">
            {leftPanel.length > 0
              ? leftPanel.map(renderCategory)
              : !editMode && <p style={{ textAlign: "center", color: "#999" }}>No content</p>}
          </div>
        </div>

        {/* MIDDLE PANEL: Specialty Subs + Sub Salads */}
        <div className="menu-panel">
          <div className="menu-panel-inner">
            {middlePanel.length > 0
              ? middlePanel.map(renderCategory)
              : !editMode && <p style={{ textAlign: "center", color: "#999" }}>No content</p>}

            {/* Sub Salads - rendered from a specific category */}
            {menu.categories &&
              menu.categories
                .filter((c) => c.name === "Sub Salads")
                .map(renderSaladsTable)}
          </div>
        </div>

        {/* RIGHT PANEL: Dressings + Images + Statement + Quote */}
        <div className="menu-panel">
          <div className="menu-panel-inner">
            {rightPanel.length > 0
              ? rightPanel.map((cat) =>
                  cat.name === "Dressings" ? renderDressingsCategory(cat) : renderCategory(cat)
                )
              : !editMode && <p style={{ textAlign: "center", color: "#999" }}>No content</p>}

            {/* Large feature image (if assigned) */}
            {menu.featureImage && (
              <div className="photo-container">
                <img
                  src={menu.featureImage}
                  alt="Featured"
                  className="large-photo"
                  onError={(e) => (e.target.style.display = "none")}
                />
              </div>
            )}

            {/* Ingredient quality statement */}
            {menu.ingredientStatement && (
              <div className="ingredient-statement">
                <div className="statement-rule"></div>
                <p className="ingredient-text">{menu.ingredientStatement}</p>
                <div className="statement-rule"></div>
              </div>
            )}

            {/* Two-photo row */}
            {(menu.photo2a || menu.photo2b) && (
              <div className="two-photo-row">
                {menu.photo2a && (
                  <img
                    src={menu.photo2a}
                    alt="Photo 1"
                    className="small-photo"
                    onError={(e) => (e.target.style.display = "none")}
                  />
                )}
                {menu.photo2b && (
                  <img
                    src={menu.photo2b}
                    alt="Photo 2"
                    className="small-photo"
                    onError={(e) => (e.target.style.display = "none")}
                  />
                )}
              </div>
            )}

            {/* Closing quote */}
            {menu.closingQuote && (
              <div className="closing-quote">
                "{menu.closingQuote}"
                <div className="closing-flourish">❦</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* EDITING INTERFACE (hidden in print) */}
      {canEdit && (
        <div className="no-print" style={{ marginTop: "20px", textAlign: "center" }}>
          <button onClick={() => setEditMode(!editMode)}>
            {editMode ? "Done" : "Edit"}
          </button>
          {editMode && (
            <>
              <p>
                <strong>Assign categories to panels:</strong> left, middle, or right
              </p>
              <p>
                <strong>Special fields:</strong> featureImage, ingredientStatement,
                photo2a, photo2b, closingQuote
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
