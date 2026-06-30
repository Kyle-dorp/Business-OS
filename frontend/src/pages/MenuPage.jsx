import { useState } from "react";
import MenuEditor from "../components/MenuEditor";

const DEFAULT_MENU = {
  title: "Menu",
  subtitle: "",
  categories: [],
};

export default function MenuPage({ config: rawConfig, businessName, onSaveConfig }) {
  const menu = rawConfig || DEFAULT_MENU;
  const [editorOpen, setEditorOpen] = useState(false);
  const columns = menu.columns || 1;
  const landscape = menu.print_landscape === true;
  const theme = menu.theme || {};

  const titleStyle = theme.title_color ? { color: theme.title_color } : {};
  const headerStyle = theme.header_color ? { color: theme.header_color } : {};
  const sheetStyle = theme.bg ? { background: theme.bg } : {};
  const categoriesStyle = columns > 1 ? { columnCount: columns, columnGap: "2rem" } : {};

  if (!menu.categories?.length) {
    return (
      <div className="page">
        <div className="page-header">
          <div><span className="eyebrow">PRINTABLE</span><h1>Menu</h1></div>
          <button className="secondary-btn compact no-print" onClick={() => window.print()}>Print</button>
        </div>
        <div className="card menu-empty">
          <p><strong>No menu items yet.</strong></p>
          <p>Tell the AI Assistant what you sell and ask it to build your menu. Example:</p>
          <blockquote className="menu-example-quote">
            "Build a 3-column landscape pamphlet menu with Classic Subs and Specialty Subs sections, 6&quot; and 12&quot; prices, add some color."
          </blockquote>
        </div>
      </div>
    );
  }

  return (
    <>
    <div className="page menu-page">
      {landscape && (
        <style>{`@media print { @page { size: letter landscape !important; } }`}</style>
      )}

      <div className="page-header menu-page-header no-print">
        <div><span className="eyebrow">PRINTABLE</span><h1>Menu</h1></div>
        <div style={{ display: "flex", gap: "8px" }}>
          <button className="secondary-btn compact" onClick={() => setEditorOpen(true)}>Edit menu</button>
          <button className="secondary-btn compact" onClick={() => window.print()}>Print / Save PDF</button>
        </div>
      </div>

      <div className="menu-sheet" style={sheetStyle}>
        <div className="menu-title-block">
          <h1 className="menu-title" style={titleStyle}>{menu.title || businessName || "Menu"}</h1>
          {menu.subtitle && <p className="menu-subtitle" style={theme.subtitle_color ? { color: theme.subtitle_color } : {}}>{menu.subtitle}</p>}
        </div>

        <div className="menu-categories" style={categoriesStyle}>
          {menu.categories.map((cat, ci) => (
            <div className="menu-category" key={ci} style={{ breakInside: "avoid" }}>
              {cat.image_url && (
                <img className="menu-cat-img" src={cat.image_url} alt={cat.name} />
              )}
              <h2 className="menu-cat-name" style={headerStyle}>
                {cat.emoji ? <span className="menu-cat-emoji">{cat.emoji}</span> : null}
                {cat.name}
              </h2>
              {cat.description && <p className="menu-cat-desc">{cat.description}</p>}
              <div className="menu-items">
                {(cat.items || []).map((item, ii) => (
                  <div className="menu-item" key={ii}>
                    <div className="menu-item-main">
                      <span className="menu-item-name">{item.name}</span>
                      {item.description && <span className="menu-item-desc">{item.description}</span>}
                    </div>
                    <div className="menu-item-prices">
                      {item.sizes
                        ? Object.entries(item.sizes).map(([sz, price]) => (
                            <span className="menu-price-pair" key={sz}>
                              <span className="menu-size">{sz}</span>
                              <span className="menu-price">{price ? `$${price}` : "—"}</span>
                            </span>
                          ))
                        : item.price
                        ? <span className="menu-price">${item.price}</span>
                        : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {menu.footer && <p className="menu-footer">{menu.footer}</p>}
      </div>
    </div>
    {editorOpen && (
      <MenuEditor
        config={rawConfig}
        onSave={onSaveConfig}
        onClose={() => setEditorOpen(false)}
      />
    )}
    </>
  );
}
