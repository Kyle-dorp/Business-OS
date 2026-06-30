import { useEffect, useRef, useState } from "react";

const DEFAULT_MENU = {
  title: "Menu",
  subtitle: "",
  footer: "",
  columns: 3,
  print_landscape: true,
  theme: {},
  categories: [],
};

function MoveIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
      <polyline points="5 9 2 12 5 15" />
      <polyline points="9 5 12 2 15 5" />
      <polyline points="15 19 12 22 9 19" />
      <polyline points="19 9 22 12 19 15" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <line x1="12" y1="2" x2="12" y2="22" />
    </svg>
  );
}

export default function MenuPage({ config: rawConfig, businessName, onSaveConfig }) {
  const canEdit = typeof onSaveConfig === "function";
  const [menu, setMenu] = useState(() => ({ ...DEFAULT_MENU, ...(rawConfig || {}) }));
  const [editMode, setEditMode] = useState(false);
  const [editingKey, setEditingKey] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const dragInfo = useRef(null);

  useEffect(() => {
    if (!editMode) setMenu({ ...DEFAULT_MENU, ...(rawConfig || {}) });
  }, [rawConfig]); // eslint-disable-line

  const theme = menu.theme || {};
  const titleStyle = theme.title_color ? { color: theme.title_color } : {};
  const headerStyle = theme.header_color ? { color: theme.header_color } : {};
  const sheetStyle = theme.bg ? { background: theme.bg } : {};
  const columnStyle = { columnCount: 3, columnGap: "0", columnRule: "1.5px solid #d4c9b0" };

  function setField(key, val) { setMenu((m) => ({ ...m, [key]: val })); }
  function setTheme(key, val) { setMenu((m) => ({ ...m, theme: { ...(m.theme || {}), [key]: val } })); }

  function setCatField(gi, key, val) {
    setMenu((m) => ({ ...m, categories: m.categories.map((c, i) => i === gi ? { ...c, [key]: val } : c) }));
  }

  function removeCategory(gi) {
    if (!window.confirm("Remove this category and all its items?")) return;
    setMenu((m) => ({ ...m, categories: m.categories.filter((_, i) => i !== gi) }));
    setEditingKey(null);
  }

  function addCategory(side) {
    const idx = menu.categories.length;
    setMenu((m) => ({ ...m, categories: [...m.categories, { name: "New Category", emoji: "", side, items: [] }] }));
    setEditingKey(String(idx));
  }

  function moveCategory(fromGlobal, toGlobal) {
    if (fromGlobal === toGlobal) return;
    setMenu((m) => {
      const cats = [...m.categories];
      const [moved] = cats.splice(fromGlobal, 1);
      cats.splice(toGlobal > fromGlobal ? toGlobal - 1 : toGlobal, 0, moved);
      return { ...m, categories: cats };
    });
  }

  function setItemField(gi, ii, key, val) {
    setMenu((m) => ({
      ...m,
      categories: m.categories.map((c, i) => i !== gi ? c : {
        ...c, items: c.items.map((it, j) => j !== ii ? it : { ...it, [key]: val }),
      }),
    }));
  }

  function setItemSize(gi, ii, sz, val) {
    setMenu((m) => ({
      ...m,
      categories: m.categories.map((c, i) => i !== gi ? c : {
        ...c, items: c.items.map((it, j) => j !== ii ? it : { ...it, sizes: { ...(it.sizes || {}), [sz]: val }, price: undefined }),
      }),
    }));
  }

  function toggleSinglePrice(gi, ii, useSingle) {
    setMenu((m) => ({
      ...m,
      categories: m.categories.map((c, i) => i !== gi ? c : {
        ...c, items: c.items.map((it, j) => j !== ii ? it : useSingle
          ? { name: it.name, description: it.description || "", price: "" }
          : { name: it.name, description: it.description || "", sizes: { '6"': "", '12"': "" } }),
      }),
    }));
  }

  function removeItem(gi, ii) {
    setMenu((m) => ({
      ...m,
      categories: m.categories.map((c, i) => i !== gi ? c : { ...c, items: c.items.filter((_, j) => j !== ii) }),
    }));
    setEditingKey(null);
  }

  function addItem(gi) {
    const newIdx = (menu.categories[gi].items || []).length;
    setMenu((m) => ({
      ...m,
      categories: m.categories.map((c, i) => i !== gi ? c : {
        ...c, items: [...(c.items || []), { name: "New Item", sizes: { '6"': "", '12"': "" } }],
      }),
    }));
    setEditingKey(`${gi}-item-${newIdx}`);
  }

  function moveItem(gi, from, to) {
    if (from === to) return;
    setMenu((m) => {
      const cats = [...m.categories];
      const items = [...(cats[gi].items || [])];
      const [moved] = items.splice(from, 1);
      items.splice(to > from ? to - 1 : to, 0, moved);
      cats[gi] = { ...cats[gi], items };
      return { ...m, categories: cats };
    });
  }

  function readImageFile(file, gi) {
    if (!file || !file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = (ev) => setCatField(gi, "image_url", ev.target.result);
    reader.readAsDataURL(file);
  }

  async function handleSave() {
    setSaving(true);
    await onSaveConfig(menu);
    setSaving(false);
    setEditMode(false);
    setEditingKey(null);
    setSettingsOpen(false);
  }

  function handleCancel() {
    setMenu({ ...DEFAULT_MENU, ...(rawConfig || {}) });
    setEditMode(false);
    setEditingKey(null);
    setSettingsOpen(false);
  }

  function renderItem(gi, ii, item) {
    const key = `${gi}-item-${ii}`;
    const isEditing = editingKey === key;
    return (
      <div
        className={`menu-item${editMode ? " menu-item-editable" : ""}`}
        key={ii}
        draggable={editMode}
        onDragStart={(e) => {
          dragInfo.current = { type: "item", catIndex: gi, itemIndex: ii };
          e.dataTransfer.effectAllowed = "move";
          e.stopPropagation();
        }}
        onDragOver={(e) => {
          if (dragInfo.current?.type === "item" && dragInfo.current.catIndex === gi) e.preventDefault();
        }}
        onDrop={(e) => {
          const info = dragInfo.current;
          if (info?.type === "item" && info.catIndex === gi) {
            e.preventDefault();
            e.stopPropagation();
            moveItem(gi, info.itemIndex, ii);
          }
          dragInfo.current = null;
        }}
      >
        {isEditing ? (
          <div className="menu-item-edit-form no-print">
            <input
              className="edl-input"
              value={item.name || ""}
              onChange={(e) => setItemField(gi, ii, "name", e.target.value)}
              placeholder="Item name"
              autoFocus
            />
            <input
              className="edl-input"
              value={item.description || ""}
              onChange={(e) => setItemField(gi, ii, "description", e.target.value)}
              placeholder="Description (optional)"
            />
            {item.sizes ? (
              <div className="menu-price-fields">
                {Object.keys(item.sizes).map((sz) => (
                  <label className="menu-price-field" key={sz}>
                    <span>{sz}</span>
                    <input
                      className="edl-input menu-price-input"
                      value={item.sizes[sz] || ""}
                      onChange={(e) => setItemSize(gi, ii, sz, e.target.value)}
                      placeholder="0.00"
                    />
                  </label>
                ))}
                <button type="button" className="menu-toggle-price-btn" onClick={() => toggleSinglePrice(gi, ii, true)}>
                  Single price
                </button>
              </div>
            ) : (
              <div className="menu-price-fields">
                <label className="menu-price-field">
                  <span>Price</span>
                  <input
                    className="edl-input menu-price-input"
                    value={item.price || ""}
                    onChange={(e) => setItemField(gi, ii, "price", e.target.value)}
                    placeholder="0.00"
                  />
                </label>
                <button type="button" className="menu-toggle-price-btn" onClick={() => toggleSinglePrice(gi, ii, false)}>
                  + sizes
                </button>
              </div>
            )}
          </div>
        ) : (
          <>
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
                : item.price ? <span className="menu-price">${item.price}</span> : null}
            </div>
          </>
        )}
        {editMode && (
          <div className="menu-item-controls no-print">
            <span
              className="menu-drag-handle"
              draggable
              onDragStart={(e) => {
                dragInfo.current = { type: "item", catIndex: gi, itemIndex: ii };
                e.dataTransfer.effectAllowed = "move";
                e.stopPropagation();
              }}
              title="Drag to reorder"
            >
              <MoveIcon />
            </span>
            <button
              type="button"
              className="menu-edit-btn"
              onClick={() => setEditingKey(isEditing ? null : key)}
              title={isEditing ? "Done" : "Edit"}
            >
              {isEditing ? "✓" : "✎"}
            </button>
            <button type="button" className="menu-remove-btn" onClick={() => removeItem(gi, ii)} title="Remove">×</button>
          </div>
        )}
      </div>
    );
  }

  function renderCategory(gi, side) {
    const cat = menu.categories[gi];
    const catKey = String(gi);
    const isEditing = editingKey === catKey;
    return (
      <div
        className="menu-category"
        key={gi}
        style={{ breakInside: "avoid" }}
        draggable={editMode}
        onDragStart={(e) => {
          dragInfo.current = { type: "category", side, globalIndex: gi };
          e.dataTransfer.effectAllowed = "move";
        }}
        onDragOver={(e) => {
          if (dragInfo.current?.type === "category" && dragInfo.current.side === side) { e.preventDefault(); return; }
          if (editMode && e.dataTransfer.types.includes("Files")) e.preventDefault();
        }}
        onDrop={(e) => {
          e.preventDefault();
          if (e.dataTransfer.files?.length) {
            readImageFile(e.dataTransfer.files[0], gi);
            dragInfo.current = null;
            return;
          }
          const info = dragInfo.current;
          if (info?.type === "category" && info.side === side) moveCategory(info.globalIndex, gi);
          dragInfo.current = null;
        }}
      >
        {editMode && (
          <div className="menu-cat-toolbar no-print">
            <span
              className="menu-drag-handle"
              draggable
              onDragStart={(e) => {
                dragInfo.current = { type: "category", side, globalIndex: gi };
                e.dataTransfer.effectAllowed = "move";
                e.stopPropagation();
              }}
              title="Drag to reorder"
            >
              <MoveIcon />
            </span>
            <button
              type="button"
              className="menu-edit-btn"
              onClick={() => setEditingKey(isEditing ? null : catKey)}
            >
              {isEditing ? "✓" : "✎"}
            </button>
            <button
              type="button"
              className="menu-side-btn"
              onClick={() => setCatField(gi, "side", side === "front" ? "back" : "front")}
              title={`Move to ${side === "front" ? "back" : "front"} side`}
            >
              {side === "front" ? "→ back" : "← front"}
            </button>
            <button type="button" className="menu-remove-btn" onClick={() => removeCategory(gi)}>×</button>
          </div>
        )}

        {cat.image_url ? (
          <div className="menu-cat-img-wrap">
            <img className="menu-cat-img" src={cat.image_url} alt={cat.name} />
            {editMode && (
              <button type="button" className="menu-img-remove no-print" onClick={() => setCatField(gi, "image_url", "")}>×</button>
            )}
          </div>
        ) : editMode ? (
          <label
            className="menu-img-drop no-print"
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
            onDrop={(e) => { e.preventDefault(); e.stopPropagation(); readImageFile(e.dataTransfer.files[0], gi); }}
          >
            Drop photo here or click to choose
            <input type="file" accept="image/*" style={{ display: "none" }} onChange={(e) => readImageFile(e.target.files[0], gi)} />
          </label>
        ) : null}

        {isEditing ? (
          <div className="menu-cat-edit-form no-print">
            <div style={{ display: "flex", gap: "6px", marginBottom: "6px" }}>
              <input
                className="edl-input"
                style={{ width: "52px", flexShrink: 0 }}
                value={cat.emoji || ""}
                onChange={(e) => setCatField(gi, "emoji", e.target.value)}
                placeholder="🥖"
                autoFocus
              />
              <input
                className="edl-input"
                style={{ flex: 1 }}
                value={cat.name || ""}
                onChange={(e) => setCatField(gi, "name", e.target.value)}
                placeholder="Category name"
              />
            </div>
            <input
              className="edl-input"
              style={{ width: "100%" }}
              value={cat.description || ""}
              onChange={(e) => setCatField(gi, "description", e.target.value)}
              placeholder="Description (optional)"
            />
          </div>
        ) : (
          <>
            <h2 className="menu-cat-name" style={headerStyle}>
              {cat.emoji && <span className="menu-cat-emoji">{cat.emoji}</span>}
              {cat.name}
            </h2>
            {cat.description && <p className="menu-cat-desc">{cat.description}</p>}
          </>
        )}

        <div className="menu-items">
          {(cat.items || []).map((item, ii) => renderItem(gi, ii, item))}
        </div>
        {editMode && (
          <button type="button" className="menu-add-item-btn no-print" onClick={() => addItem(gi)}>
            + Add item
          </button>
        )}
      </div>
    );
  }

  const frontIndices = menu.categories.map((_, i) => i).filter((i) => (menu.categories[i].side || "front") === "front");
  const backIndices = menu.categories.map((_, i) => i).filter((i) => menu.categories[i].side === "back");
  const landscape = menu.print_landscape !== false;

  if (!menu.categories?.length && !canEdit) {
    return (
      <div className="page">
        <div className="page-header"><div><span className="eyebrow">PRINTABLE</span><h1>Menu</h1></div></div>
        <div className="card menu-empty">
          <p><strong>No menu items yet.</strong></p>
          <p>Tell the AI Assistant what you sell and ask it to build your menu.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page menu-page">
      {landscape && <style>{`@page { size: letter landscape; margin: 0.2in; }`}</style>}

      <div className="page-header menu-page-header no-print">
        <div><span className="eyebrow">PRINTABLE</span><h1>Menu</h1></div>
        {canEdit && (
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {editMode && (
              <button className="secondary-btn compact" onClick={() => setSettingsOpen((v) => !v)}>⚙ Theme</button>
            )}
            {editMode ? (
              <>
                <button className="secondary-btn compact" onClick={handleCancel}>Cancel</button>
                <button className="primary-btn compact" disabled={saving} onClick={handleSave}>
                  {saving ? "Saving…" : "Done editing"}
                </button>
              </>
            ) : (
              <button className="secondary-btn compact" onClick={() => setEditMode(true)}>✎ Edit</button>
            )}
            <button className="secondary-btn compact" onClick={() => window.print()}>Print / Save PDF</button>
          </div>
        )}
      </div>

      {settingsOpen && editMode && (
        <div className="menu-settings-panel no-print">
          <div className="menu-settings-colors">
            {[["title_color", "Title"], ["header_color", "Headers"], ["subtitle_color", "Subtitle"], ["bg", "Background"]].map(([key, label]) => (
              <label className="menu-color-field" key={key}>
                <input type="color" value={theme[key] || "#111111"} onChange={(e) => setTheme(key, e.target.value)} />
                <span>{label}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* ── FRONT PAGE ── */}
      <div className="menu-sheet menu-pamphlet menu-page-front" style={sheetStyle}>
        <div className="menu-title-block">
          {editingKey === "title" ? (
            <div className="menu-title-edit-wrap">
              <input
                className="edl-input menu-title-input"
                value={menu.title || ""}
                onChange={(e) => setField("title", e.target.value)}
                placeholder="Menu title"
                autoFocus
              />
              <input
                className="edl-input menu-subtitle-input"
                value={menu.subtitle || ""}
                onChange={(e) => setField("subtitle", e.target.value)}
                placeholder="Subtitle — address, phone…"
              />
            </div>
          ) : (
            <>
              <h1 className="menu-title" style={titleStyle}>{menu.title || businessName || "Menu"}</h1>
              {menu.subtitle && (
                <p className="menu-subtitle" style={theme.subtitle_color ? { color: theme.subtitle_color } : {}}>
                  {menu.subtitle}
                </p>
              )}
            </>
          )}
          {editMode && (
            <button
              type="button"
              className="menu-edit-btn no-print"
              style={{ marginTop: "8px" }}
              onClick={() => setEditingKey(editingKey === "title" ? null : "title")}
            >
              {editingKey === "title" ? "✓ Done" : "✎ Edit title & subtitle"}
            </button>
          )}
        </div>

        <div className="menu-categories" style={columnStyle}>
          {frontIndices.map((gi) => renderCategory(gi, "front"))}
        </div>

        {editMode && (
          <button type="button" className="menu-add-cat-btn no-print" onClick={() => addCategory("front")}>
            + Add category to front
          </button>
        )}
      </div>

      {/* ── BACK PAGE ── */}
      <div className="menu-sheet menu-pamphlet menu-page-back" style={sheetStyle}>
        {editMode && (
          <div className="menu-back-label no-print">Back side — prints on page 2</div>
        )}

        {backIndices.length === 0 && editMode && (
          <p className="menu-back-empty no-print">
            Use "→ back" on any category above to move it here.
          </p>
        )}

        <div className="menu-categories" style={columnStyle}>
          {backIndices.map((gi) => renderCategory(gi, "back"))}
        </div>

        {editMode && (
          <button type="button" className="menu-add-cat-btn no-print" onClick={() => addCategory("back")}>
            + Add category to back
          </button>
        )}

        {editingKey === "footer" ? (
          <input
            className="edl-input menu-footer-input no-print"
            value={menu.footer || ""}
            onChange={(e) => setField("footer", e.target.value)}
            placeholder="Footer text…"
          />
        ) : menu.footer ? (
          <p className="menu-footer">{menu.footer}</p>
        ) : null}
        {editMode && (
          <button
            type="button"
            className="menu-edit-btn no-print"
            style={{ display: "block", margin: "6px auto 0" }}
            onClick={() => setEditingKey(editingKey === "footer" ? null : "footer")}
          >
            {editingKey === "footer" ? "✓ Done" : "✎ footer"}
          </button>
        )}
      </div>
    </div>
  );
}
