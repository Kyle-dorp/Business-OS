import { useState } from "react";

export default function MenuEditor({ config, onSave, onClose }) {
  const [menu, setMenu] = useState(() => ({
    title: "", subtitle: "", footer: "", columns: 1, print_landscape: false,
    theme: {}, categories: [],
    ...(config || {}),
  }));
  const [saving, setSaving] = useState(false);
  const [expandedCat, setExpandedCat] = useState(null);

  function setField(key, val) { setMenu((m) => ({ ...m, [key]: val })); }
  function setTheme(key, val) { setMenu((m) => ({ ...m, theme: { ...(m.theme || {}), [key]: val } })); }

  // Category helpers
  function addCategory() {
    setMenu((m) => ({ ...m, categories: [...m.categories, { name: "New Category", items: [] }] }));
    setExpandedCat(menu.categories.length);
  }
  function removeCategory(ci) {
    setMenu((m) => ({ ...m, categories: m.categories.filter((_, i) => i !== ci) }));
    setExpandedCat(null);
  }
  function moveCat(ci, dir) {
    const j = ci + dir;
    if (j < 0 || j >= menu.categories.length) return;
    setMenu((m) => {
      const next = [...m.categories];
      [next[ci], next[j]] = [next[j], next[ci]];
      return { ...m, categories: next };
    });
    setExpandedCat(j);
  }
  function setCatField(ci, key, val) {
    setMenu((m) => ({
      ...m,
      categories: m.categories.map((cat, i) => i === ci ? { ...cat, [key]: val } : cat),
    }));
  }

  // Item helpers
  function addItem(ci) {
    setMenu((m) => ({
      ...m,
      categories: m.categories.map((cat, i) => i === ci
        ? { ...cat, items: [...(cat.items || []), { name: "New Item", sizes: { '6"': "", '12"': "" } }] }
        : cat),
    }));
  }
  function removeItem(ci, ii) {
    setMenu((m) => ({
      ...m,
      categories: m.categories.map((cat, i) => i === ci
        ? { ...cat, items: cat.items.filter((_, j) => j !== ii) }
        : cat),
    }));
  }
  function moveItem(ci, ii, dir) {
    const j = ii + dir;
    setMenu((m) => ({
      ...m,
      categories: m.categories.map((cat, i) => {
        if (i !== ci) return cat;
        const items = [...cat.items];
        if (j < 0 || j >= items.length) return cat;
        [items[ii], items[j]] = [items[j], items[ii]];
        return { ...cat, items };
      }),
    }));
  }
  function setItemField(ci, ii, key, val) {
    setMenu((m) => ({
      ...m,
      categories: m.categories.map((cat, i) => i !== ci ? cat : {
        ...cat,
        items: cat.items.map((item, j) => j !== ii ? item : { ...item, [key]: val }),
      }),
    }));
  }
  function setItemSize(ci, ii, sz, val) {
    setMenu((m) => ({
      ...m,
      categories: m.categories.map((cat, i) => i !== ci ? cat : {
        ...cat,
        items: cat.items.map((item, j) => j !== ii ? item : {
          ...item,
          sizes: { ...(item.sizes || {}), [sz]: val },
          price: undefined,
        }),
      }),
    }));
  }
  function toggleSinglePrice(ci, ii, useSingle) {
    setMenu((m) => ({
      ...m,
      categories: m.categories.map((cat, i) => i !== ci ? cat : {
        ...cat,
        items: cat.items.map((item, j) => j !== ii ? item : useSingle
          ? { name: item.name, description: item.description, price: "" }
          : { name: item.name, description: item.description, sizes: { '6"': "", '12"': "" } }),
      }),
    }));
  }

  async function handleSave() {
    setSaving(true);
    await onSave(menu);
    setSaving(false);
    onClose();
  }

  const theme = menu.theme || {};

  return (
    <div className="cfe-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="cfe-panel cfe-panel-wide">
        <div className="cfe-header">
          <strong>Edit Menu</strong>
          <button className="cfe-close" onClick={onClose}>×</button>
        </div>

        <div className="cfe-body">
          {/* Basic info */}
          <div className="cfe-section">
            <div className="cfe-section-label">Menu Info</div>
            <div className="cfe-row-2">
              <label className="cfe-field"><span>Title</span><input className="edl-input" value={menu.title || ""} onChange={(e) => setField("title", e.target.value)} /></label>
              <label className="cfe-field"><span>Subtitle</span><input className="edl-input" value={menu.subtitle || ""} onChange={(e) => setField("subtitle", e.target.value)} /></label>
            </div>
            <label className="cfe-field"><span>Footer text</span><input className="edl-input" value={menu.footer || ""} onChange={(e) => setField("footer", e.target.value)} /></label>
            <div className="cfe-row-2">
              <label className="cfe-field">
                <span>Columns</span>
                <select className="edl-input" value={menu.columns || 1} onChange={(e) => setField("columns", Number(e.target.value))}>
                  <option value={1}>1 column</option>
                  <option value={2}>2 columns</option>
                  <option value={3}>3 columns (pamphlet)</option>
                </select>
              </label>
              <label className="cfe-field cfe-checkbox-field">
                <input type="checkbox" checked={!!menu.print_landscape} onChange={(e) => setField("print_landscape", e.target.checked)} />
                <span>Landscape print (for folding)</span>
              </label>
            </div>
          </div>

          {/* Theme */}
          <div className="cfe-section">
            <div className="cfe-section-label">Colors</div>
            <div className="cfe-colors-grid">
              {[
                ["title_color", "Title color"],
                ["header_color", "Category headers"],
                ["subtitle_color", "Subtitle / footer"],
                ["bg", "Background"],
              ].map(([key, label]) => (
                <label className="cfe-color-field" key={key}>
                  <input type="color" value={theme[key] || "#000000"} onChange={(e) => setTheme(key, e.target.value)} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Categories */}
          <div className="cfe-section">
            <div className="cfe-section-label">Categories & Items</div>
            {menu.categories.map((cat, ci) => (
              <div className="cfe-cat-block" key={ci}>
                <div className="cfe-cat-header" onClick={() => setExpandedCat(expandedCat === ci ? null : ci)}>
                  <div className="cfe-cat-header-left">
                    <div className="edl-arrows">
                      <button type="button" onClick={(e) => { e.stopPropagation(); moveCat(ci, -1); }} disabled={ci === 0}>↑</button>
                      <button type="button" onClick={(e) => { e.stopPropagation(); moveCat(ci, 1); }} disabled={ci === menu.categories.length - 1}>↓</button>
                    </div>
                    <span className="cfe-cat-name">{cat.emoji ? `${cat.emoji} ` : ""}{cat.name || "(unnamed)"}</span>
                    <span className="cfe-cat-count">{(cat.items || []).length} items</span>
                  </div>
                  <div className="cfe-cat-header-right">
                    <button type="button" className="edl-remove" onClick={(e) => { e.stopPropagation(); removeCategory(ci); }}>×</button>
                    <span className="cfe-cat-toggle">{expandedCat === ci ? "▲" : "▼"}</span>
                  </div>
                </div>

                {expandedCat === ci && (
                  <div className="cfe-cat-body">
                    <div className="cfe-row-3">
                      <label className="cfe-field"><span>Name</span><input className="edl-input" value={cat.name || ""} onChange={(e) => setCatField(ci, "name", e.target.value)} /></label>
                      <label className="cfe-field"><span>Emoji</span><input className="edl-input cfe-emoji" value={cat.emoji || ""} onChange={(e) => setCatField(ci, "emoji", e.target.value)} placeholder="🥖" /></label>
                      <label className="cfe-field"><span>Description</span><input className="edl-input" value={cat.description || ""} onChange={(e) => setCatField(ci, "description", e.target.value)} /></label>
                    </div>

                    <div className="cfe-items-list">
                      {(cat.items || []).map((item, ii) => (
                        <div className="cfe-item-row" key={ii}>
                          <div className="edl-arrows">
                            <button type="button" onClick={() => moveItem(ci, ii, -1)} disabled={ii === 0}>↑</button>
                            <button type="button" onClick={() => moveItem(ci, ii, 1)} disabled={ii === (cat.items.length - 1)}>↓</button>
                          </div>
                          <div className="cfe-item-fields">
                            <input className="edl-input cfe-item-name" value={item.name || ""} onChange={(e) => setItemField(ci, ii, "name", e.target.value)} placeholder="Item name" />
                            <input className="edl-input cfe-item-desc" value={item.description || ""} onChange={(e) => setItemField(ci, ii, "description", e.target.value)} placeholder="Description (optional)" />
                            {item.sizes
                              ? <div className="cfe-sizes-row">
                                  {Object.keys(item.sizes).map((sz) => (
                                    <label className="cfe-size-field" key={sz}>
                                      <span>{sz}</span>
                                      <input className="edl-input cfe-price" value={item.sizes[sz] || ""} onChange={(e) => setItemSize(ci, ii, sz, e.target.value)} placeholder="0.00" />
                                    </label>
                                  ))}
                                  <button type="button" className="cfe-toggle-price" onClick={() => toggleSinglePrice(ci, ii, true)}>Single price</button>
                                </div>
                              : <div className="cfe-sizes-row">
                                  <label className="cfe-size-field">
                                    <span>Price</span>
                                    <input className="edl-input cfe-price" value={item.price || ""} onChange={(e) => setItemField(ci, ii, "price", e.target.value)} placeholder="0.00" />
                                  </label>
                                  <button type="button" className="cfe-toggle-price" onClick={() => toggleSinglePrice(ci, ii, false)}>Add sizes</button>
                                </div>
                            }
                          </div>
                          <button type="button" className="edl-remove" onClick={() => removeItem(ci, ii)}>×</button>
                        </div>
                      ))}
                      <button type="button" className="edl-add" onClick={() => addItem(ci)}>+ Add item</button>
                    </div>
                  </div>
                )}
              </div>
            ))}
            <button type="button" className="edl-add cfe-add-cat" onClick={addCategory}>+ Add category</button>
          </div>
        </div>

        <div className="cfe-footer">
          <button className="secondary-btn" onClick={onClose}>Cancel</button>
          <button className="primary-btn" disabled={saving} onClick={handleSave}>{saving ? "Saving…" : "Save changes"}</button>
        </div>
      </div>
    </div>
  );
}
