import { useEffect, useState } from "react";
import { DndContext, closestCenter, PointerSensor, TouchSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy, useSortable, arrayMove } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { BAMS_MENU_PRESET } from "../data/bamsMenuPreset";

const DEFAULT_MENU = {
  title: "Menu",
  subtitle: "",
  footer: "",
  columns: 3,
  print_landscape: true,
  preset: "pamphlet",
  categories: [],
};

// Bam's menu preset with three-panel layout
const BAMS_DEFAULT = BAMS_MENU_PRESET;

const PANELS = [1, 2, 3];

let idSeq = 0;
function nextId() {
  idSeq += 1;
  return `m${Date.now().toString(36)}${idSeq.toString(36)}`;
}
function withIds(menu) {
  return {
    ...menu,
    categories: (menu.categories || []).map((c) => ({
      ...c,
      id: c.id || nextId(),
      items: (c.items || []).map((it) => ({ ...it, id: it.id || nextId() })),
    })),
  };
}

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


// Thin wrappers so useSortable() (a hook) lives in a real component, while the
// render-prop callback stays a plain closure that can still reach MenuPage's
// local state/handlers without prop-drilling everything through.
function SortableCategory({ sortId, children }) {
  return children(useSortable({ id: sortId }));
}
function SortableItem({ sortId, children }) {
  return children(useSortable({ id: sortId }));
}

export default function MenuPage({ config: rawConfig, businessName, onSaveConfig }) {
  const canEdit = typeof onSaveConfig === "function";

  // Use Bam's preset if no config provided, otherwise use provided config
  const initialConfig = rawConfig || (!rawConfig && !businessName ? BAMS_DEFAULT : DEFAULT_MENU);

  const [menu, setMenu] = useState(() => withIds({ ...DEFAULT_MENU, ...initialConfig }));
  const [editMode, setEditMode] = useState(false);
  const [editingKey, setEditingKey] = useState(null);
  const [saving, setSaving] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 6 } })
  );

  useEffect(() => {
    if (!editMode) {
      const config = rawConfig || (!rawConfig && !businessName ? BAMS_DEFAULT : DEFAULT_MENU);
      setMenu(withIds({ ...DEFAULT_MENU, ...config }));
    }
  }, [rawConfig, businessName]); // eslint-disable-line

  const preset = menu.preset === "list" ? "list" : "pamphlet";

  function setField(key, val) { setMenu((m) => ({ ...m, [key]: val })); }

  function setCatField(gi, key, val) {
    setMenu((m) => ({ ...m, categories: m.categories.map((c, i) => i === gi ? { ...c, [key]: val } : c) }));
  }

  function removeCategory(gi) {
    if (!window.confirm("Remove this category and all its items?")) return;
    setMenu((m) => ({ ...m, categories: m.categories.filter((_, i) => i !== gi) }));
    setEditingKey(null);
  }

  function addCategory(side, panel) {
    const idx = menu.categories.length;
    setMenu((m) => ({ ...m, categories: [...m.categories, { id: nextId(), name: "New Category", emoji: "", side, panel, items: [] }] }));
    setEditingKey(String(idx));
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
          ? { id: it.id, name: it.name, description: it.description || "", price: "" }
          : { id: it.id, name: it.name, description: it.description || "", sizes: { '6"': "", '12"': "" } }),
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
        ...c, items: [...(c.items || []), { id: nextId(), name: "New Item", sizes: { '6"': "", '12"': "" } }],
      }),
    }));
    setEditingKey(`${gi}-item-${newIdx}`);
  }

  function readImageFile(file, gi) {
    if (!file || !file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = (ev) => setCatField(gi, "image_url", ev.target.result);
    reader.readAsDataURL(file);
  }

  function handleDragEnd(event) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const activeId = String(active.id);
    const overId = String(over.id);

    if (activeId.startsWith("cat-") && overId.startsWith("cat-")) {
      const activeCatId = activeId.slice(4);
      const overCatId = overId.slice(4);
      setMenu((m) => {
        const cats = [...m.categories];
        const fromIdx = cats.findIndex((c) => c.id === activeCatId);
        const toIdx = cats.findIndex((c) => c.id === overCatId);
        if (fromIdx === -1 || toIdx === -1) return m;
        return { ...m, categories: arrayMove(cats, fromIdx, toIdx) };
      });
    } else if (activeId.startsWith("item-") && overId.startsWith("item-")) {
      const [, activeCatId, activeItemId] = activeId.split("-");
      const [, overCatId, overItemId] = overId.split("-");
      if (activeCatId !== overCatId) return;
      setMenu((m) => {
        const cats = [...m.categories];
        const ci = cats.findIndex((c) => c.id === activeCatId);
        if (ci === -1) return m;
        const items = [...(cats[ci].items || [])];
        const fromIdx = items.findIndex((it) => it.id === activeItemId);
        const toIdx = items.findIndex((it) => it.id === overItemId);
        if (fromIdx === -1 || toIdx === -1) return m;
        cats[ci] = { ...cats[ci], items: arrayMove(items, fromIdx, toIdx) };
        return { ...m, categories: cats };
      });
    }
  }

  async function handleSave() {
    setSaving(true);
    await onSaveConfig(menu);
    setSaving(false);
    setEditMode(false);
    setEditingKey(null);
  }

  function handleCancel() {
    setMenu(withIds({ ...DEFAULT_MENU, ...(rawConfig || {}) }));
    setEditMode(false);
    setEditingKey(null);
  }

  function renderItem(gi, ii, item, sizeKeys, leaderStyle) {
    const cat = menu.categories[gi];
    const key = `${gi}-item-${ii}`;
    const isEditing = editingKey === key;
    const sortId = `item-${cat.id}-${item.id}`;

    return (
      <SortableItem sortId={sortId} key={item.id}>
        {({ setNodeRef, attributes, listeners, transform, transition, isDragging }) => (
          <div
            ref={setNodeRef}
            className={`menu-item${leaderStyle ? " menu-item-leader" : ""}${editMode ? " menu-item-editable" : ""}`}
            style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1, zIndex: isDragging ? 5 : "auto", position: "relative" }}
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
            ) : preset === "pamphlet" ? (
              <>
                <span className="menu-item-name">{item.name}</span>
                {item.sizes && (
                  <>
                    <span className="menu-price-6">${item.sizes["6\""] || "—"}</span>
                    <span className="menu-price-12">${item.sizes["12\""] || "—"}</span>
                  </>
                )}
                {item.price && !item.sizes && (
                  <>
                    <span className="menu-price-6">${item.price}</span>
                    <span className="menu-price-12"></span>
                  </>
                )}
                {item.description && <span className="menu-item-description">{item.description}</span>}
              </>
            ) : (
              <>
                <div className="menu-item-main">
                  <span className="menu-item-name">{item.name}</span>
                  {item.description && <span className="menu-item-desc">{item.description}</span>}
                </div>
                {leaderStyle && <span className="menu-item-leader-fill" aria-hidden="true" />}
                <div className="menu-item-prices">
                  {item.sizes
                    ? sizeKeys.map((sz) => (
                        <span className="menu-price-col" key={sz}>
                          {item.sizes[sz] ? `$${item.sizes[sz]}` : "—"}
                        </span>
                      ))
                    : item.price ? <span className="menu-price">${item.price}</span> : null}
                </div>
              </>
            )}
            {editMode && (
              <div className="menu-item-controls no-print">
                <span className="menu-drag-handle" {...attributes} {...listeners} title="Drag to reorder">
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
        )}
      </SortableItem>
    );
  }

  function renderCategory(gi, side, panel) {
    const cat = menu.categories[gi];
    const catKey = String(gi);
    const isEditing = editingKey === catKey;
    const sizeKeys = Array.from(new Set((cat.items || []).flatMap((it) => it.sizes ? Object.keys(it.sizes) : [])));
    const sortId = `cat-${cat.id}`;
    const itemSortIds = (cat.items || []).map((it) => `item-${cat.id}-${it.id}`);
    const leaderStyle = (cat.items || []).length > 0 && (cat.items || []).every((it) => !it.description);

    // In pamphlet mode, use panel names instead of numbers
    const panelDisplay = preset === "pamphlet" ? panel : panel;
    const panelOptions = preset === "pamphlet" ? ["left", "middle", "right"] : PANELS;

    return (
      <SortableCategory sortId={sortId} key={cat.id}>
        {({ setNodeRef, attributes, listeners, transform, transition, isDragging }) => (
          <div
            ref={setNodeRef}
            className="menu-category"
            style={{ breakInside: "avoid", transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1, zIndex: isDragging ? 10 : "auto", position: "relative" }}
            onDragOver={(e) => { if (editMode && e.dataTransfer.types.includes("Files")) e.preventDefault(); }}
            onDrop={(e) => {
              if (e.dataTransfer.files?.length) {
                e.preventDefault();
                readImageFile(e.dataTransfer.files[0], gi);
              }
            }}
          >
            {editMode && (
              <div className="menu-cat-toolbar no-print">
                <span className="menu-drag-handle" {...attributes} {...listeners} title={preset === "list" ? "Drag to reorder" : "Drag to reorder within this panel"}>
                  <MoveIcon />
                </span>
                <button
                  type="button"
                  className="menu-edit-btn"
                  onClick={() => setEditingKey(isEditing ? null : catKey)}
                >
                  {isEditing ? "✓" : "✎"}
                </button>
                {preset === "pamphlet" && (
                  <span className="menu-panel-picker" title={`Which panel: ${panelOptions.join(", ")}`}>
                    {panelOptions.map((p) => (
                      <button
                        key={p}
                        type="button"
                        className={`menu-panel-btn${panelDisplay === p ? " active" : ""}`}
                        onClick={() => setCatField(gi, "panel", p)}
                      >
                        {p}
                      </button>
                    ))}
                  </span>
                )}
                <button
                  type="button"
                  className={`menu-plain-btn${cat.plain ? " active" : ""}`}
                  onClick={() => setCatField(gi, "plain", !cat.plain)}
                  title="Toggle between banner header and plain header"
                >
                  {cat.plain ? "banner" : "plain"}
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
            ) : preset === "pamphlet" ? (
              <>
                <header className={cat.plain ? "menu-cat-name-plain" : "section-banner"}>
                  {!cat.plain && <span className="sunburst" aria-hidden="true">✦</span>}
                  <h2>{cat.name}</h2>
                  {!cat.plain && <span className="sunburst" aria-hidden="true">✦</span>}
                </header>
                {cat.description && <p className="section-intro">{cat.description}</p>}
              </>
            ) : (
              <>
                <h2 className={cat.plain ? "menu-cat-name-plain" : "menu-cat-name"}>
                  {cat.name}
                </h2>
                {cat.description && <p className="menu-cat-desc">{cat.description}</p>}
              </>
            )}

            <div className={cat.plain ? "menu-items menu-items-boxed" : preset === "pamphlet" && !cat.plain ? "menu-items-list" : "menu-items"}>
              {sizeKeys.length > 0 && (
                <div className={preset === "pamphlet" && !cat.plain ? "price-header" : "menu-size-header"}>
                  {preset === "pamphlet" && !cat.plain ? (
                    <>
                      <span></span>
                      {sizeKeys.map((sz) => <span key={sz} className="price-header-6in">{sz}</span>)}
                    </>
                  ) : (
                    <span className="menu-size-header-cols">
                      {sizeKeys.map((sz) => <span className="menu-size-col" key={sz}>{sz}</span>)}
                    </span>
                  )}
                </div>
              )}
              <SortableContext items={itemSortIds} strategy={verticalListSortingStrategy}>
                {(cat.items || []).map((item, ii) => renderItem(gi, ii, item, sizeKeys, leaderStyle))}
              </SortableContext>
            </div>
            {editMode && (
              <button type="button" className="menu-add-item-btn no-print" onClick={() => addItem(gi)}>
                + Add item
              </button>
            )}
          </div>
        )}
      </SortableCategory>
    );
  }

  function renderPanels(side) {
    // For pamphlet mode, render as three vertical fixed panels
    if (preset === "pamphlet") {
      return (
        <div className="menu-panels">
          {["left", "middle", "right"].map((panelName) => {
            const indices = menu.categories
              .map((_, i) => i)
              .filter((i) => (menu.categories[i].panel || "left") === panelName);
            const catSortIds = indices.map((gi) => `cat-${menu.categories[gi].id}`);
            return (
              <div className="menu-panel" key={panelName}>
                <div className="menu-panel-inner">
                  <SortableContext items={catSortIds} strategy={verticalListSortingStrategy}>
                    {indices.map((gi) => renderCategory(gi, side, panelName))}
                  </SortableContext>
                  {editMode && (
                    <button
                      type="button"
                      className="menu-add-cat-btn no-print"
                      onClick={() => addCategory(side, panelName)}
                    >
                      + Add to {panelName} panel
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    // Original list mode behavior
    return (
      <div className="menu-panels">
        {PANELS.map((p) => {
          const indices = menu.categories
            .map((_, i) => i)
            .filter((i) => {
              const c = menu.categories[i];
              return (c.side || "front") === side && (c.panel || 1) === p;
            });
          const catSortIds = indices.map((gi) => `cat-${menu.categories[gi].id}`);
          return (
            <div className="menu-panel" key={p}>
              {side === "front" && (
                <div className="menu-panel-title">{menu.title || businessName || "Menu"}</div>
              )}
              <SortableContext items={catSortIds} strategy={verticalListSortingStrategy}>
                {indices.map((gi) => renderCategory(gi, side, p))}
              </SortableContext>
              {editMode && (
                <button type="button" className="menu-add-cat-btn no-print" onClick={() => addCategory(side, p)}>
                  + Add to panel {p}
                </button>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  function renderTitleBlock() {
    return (
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
            <h1 className="menu-title">{menu.title || businessName || "Menu"}</h1>
            {menu.subtitle && <p className="menu-subtitle">{menu.subtitle}</p>}
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
    );
  }

  function renderFooterBlock() {
    return (
      <>
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
      </>
    );
  }

  const hasFront = menu.categories.some((c) => (c.side || "front") === "front");
  const hasBack = menu.categories.some((c) => c.side === "back");
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
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <div className="page menu-page">
        {preset === "pamphlet"
          ? (landscape && <style>{`@page { size: letter landscape; margin: 0.2in; }`}</style>)
          : <style>{`@page { size: letter portrait; margin: 0.4in; }`}</style>}

        <div className="page-header menu-page-header no-print">
          <div><span className="eyebrow">PRINTABLE</span><h1>Menu</h1></div>
          {canEdit && (
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              {editMode && (
                <select
                  className="menu-preset-select"
                  value={preset}
                  onChange={(e) => setField("preset", e.target.value)}
                  title="Menu layout preset"
                >
                  <option value="pamphlet">Pamphlet (fold, front/back)</option>
                  <option value="list">Simple list (one page)</option>
                </select>
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

        {preset === "list" ? (
          <div className="menu-sheet menu-list-sheet">
            {renderTitleBlock()}

            <div className="menu-list-categories">
              <SortableContext items={menu.categories.map((c) => `cat-${c.id}`)} strategy={verticalListSortingStrategy}>
                {menu.categories.map((_, gi) => renderCategory(gi, "list", 1))}
              </SortableContext>
            </div>

            {editMode && (
              <button type="button" className="menu-add-cat-btn no-print" onClick={() => addCategory("list", 1)}>
                + Add category
              </button>
            )}

            {renderFooterBlock()}
          </div>
        ) : (
          <>
            {/* ── FRONT PAGE ── */}
            {(hasFront || editMode) && (
              <div className="menu-sheet menu-pamphlet menu-page-front">
                {renderTitleBlock()}
                {renderPanels("front")}
              </div>
            )}

            {/* ── BACK PAGE ── */}
            {(hasBack || editMode) && (
              <div className="menu-sheet menu-pamphlet menu-page-back">
                {editMode && (
                  <div className="menu-back-label no-print">Back side — prints on page 2 · panels = fold columns left to right</div>
                )}
                {renderPanels("back")}
                {renderFooterBlock()}
              </div>
            )}
          </>
        )}
      </div>
    </DndContext>
  );
}
