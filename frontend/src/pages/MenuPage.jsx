import { useEffect, useState } from "react";
import {
  DndContext,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
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

let idSequence = 0;
function nextId(prefix = "m") {
  idSequence += 1;
  return `${prefix}-${Date.now().toString(36)}-${idSequence.toString(36)}`;
}

function normalizeMenu(source) {
  const menu = { ...DEFAULT_MENU, ...(source || {}) };
  const placementByName = {
    "classic subs": { layout: "classic", side: "front", panel: "left", imageCount: 1 },
    "specialty subs": { layout: "specialty", side: "front", panel: "middle", imageCount: 0 },
    "sub salads": { layout: "salads", side: "front", panel: "middle", imageCount: 0 },
    "dressings": { layout: "dressings", side: "front", panel: "right", imageCount: 3 },
    "sub combos": { layout: "combos", side: "back", panel: "left", imageCount: 1 },
    "breads": { layout: "simple", side: "back", panel: "left", imageCount: 0 },
    "desserts": { layout: "desserts", side: "back", panel: "left", imageCount: 1 },
    "soups": { layout: "soups", side: "back", panel: "middle", imageCount: 0 },
    "extras": { layout: "extras", side: "back", panel: "middle", imageCount: 0 },
    "catering": { layout: "catering", side: "back", panel: "middle", imageCount: 0 },
  };

  const categories = (menu.categories || []).map((category) => {
    const placement = placementByName[String(category.name || "").trim().toLowerCase()] || {};
    const suppliedImages = category.images || (category.image_url ? [{ url: category.image_url }] : []);
    const imageCount = Math.max(suppliedImages.length, placement.imageCount || 0);
    const images = Array.from({ length: imageCount }, (_, index) => ({
      ...(suppliedImages[index] || {}),
      id: suppliedImages[index]?.id || nextId("image"),
      url: suppliedImages[index]?.url || "",
    }));

    return {
      ...category,
      ...placement,
      id: category.id || nextId("cat"),
      size_order:
        placement.layout === "salads"
          ? category.size_order || ['12"', '6"']
          : category.size_order,
      items: (category.items || []).map((item) => ({
        ...item,
        id: item.id || nextId("item"),
      })),
      images,
    };
  });

  return {
    ...menu,
    ingredientStatement:
      menu.ingredientStatement || BAMS_MENU_PRESET.ingredientStatement,
    closingQuote:
      menu.closingQuote || menu.footer || BAMS_MENU_PRESET.closingQuote,
    address: menu.address || BAMS_MENU_PRESET.address,
    city: menu.city || BAMS_MENU_PRESET.city,
    phone: menu.phone || BAMS_MENU_PRESET.phone,
    hours: menu.hours || BAMS_MENU_PRESET.hours,
    delivery: menu.delivery || BAMS_MENU_PRESET.delivery,
    categories,
  };
}

function categorySortId(category) {
  return `cat:${category.id}`;
}

function itemSortId(category, item) {
  return `item:${category.id}:${item.id}`;
}

function MoveIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
      <path d="M12 2v20M2 12h20" />
      <path d="m8 6 4-4 4 4M8 18l4 4 4-4M6 8l-4 4 4 4M18 8l4 4-4 4" />
    </svg>
  );
}

function SortableCategory({ id, children }) {
  return children(useSortable({ id }));
}

function SortableItem({ id, children }) {
  return children(useSortable({ id }));
}

function money(value) {
  if (value === null || value === undefined || value === "") return "";
  const stringValue = String(value).trim();
  return stringValue.startsWith("$") ? stringValue : `$${stringValue}`;
}

export default function MenuPage({ config: rawConfig, businessName, onSaveConfig }) {
  const canEdit = true; // Force toolbar to show for debugging
  const initialConfig = rawConfig || (!businessName ? BAMS_MENU_PRESET : DEFAULT_MENU);

  const [menu, setMenu] = useState(() => normalizeMenu(initialConfig));
  const [editMode, setEditMode] = useState(false);
  const [editingKey, setEditingKey] = useState(null);
  const [saving, setSaving] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 7 } })
  );

  useEffect(() => {
    if (!editMode) {
      setMenu(normalizeMenu(rawConfig || (!businessName ? BAMS_MENU_PRESET : DEFAULT_MENU)));
    }
  }, [rawConfig, businessName]); // eslint-disable-line react-hooks/exhaustive-deps

  const preset = menu.preset === "list" ? "list" : "pamphlet";

  function setMenuField(key, value) {
    setMenu((current) => ({ ...current, [key]: value }));
  }

  function setCategoryField(categoryIndex, key, value) {
    setMenu((current) => ({
      ...current,
      categories: current.categories.map((category, index) =>
        index === categoryIndex ? { ...category, [key]: value } : category
      ),
    }));
  }

  function setItemField(categoryIndex, itemIndex, key, value) {
    setMenu((current) => ({
      ...current,
      categories: current.categories.map((category, index) =>
        index !== categoryIndex
          ? category
          : {
              ...category,
              items: category.items.map((item, currentItemIndex) =>
                currentItemIndex === itemIndex ? { ...item, [key]: value } : item
              ),
            }
      ),
    }));
  }

  function setItemSize(categoryIndex, itemIndex, size, value) {
    setMenu((current) => ({
      ...current,
      categories: current.categories.map((category, index) =>
        index !== categoryIndex
          ? category
          : {
              ...category,
              items: category.items.map((item, currentItemIndex) =>
                currentItemIndex === itemIndex
                  ? {
                      ...item,
                      sizes: { ...(item.sizes || {}), [size]: value },
                      price: undefined,
                    }
                  : item
              ),
            }
      ),
    }));
  }

  function toggleSinglePrice(categoryIndex, itemIndex, singlePrice) {
    setMenu((current) => ({
      ...current,
      categories: current.categories.map((category, index) =>
        index !== categoryIndex
          ? category
          : {
              ...category,
              items: category.items.map((item, currentItemIndex) => {
                if (currentItemIndex !== itemIndex) return item;
                if (singlePrice) {
                  return {
                    ...item,
                    price: item.price || "",
                    sizes: undefined,
                  };
                }
                return {
                  ...item,
                  price: undefined,
                  sizes: item.sizes || { '6"': "", '12"': "" },
                };
              }),
            }
      ),
    }));
  }

  function addItem(categoryIndex) {
    const category = menu.categories[categoryIndex];
    const newItemIndex = category.items.length;
    setMenu((current) => ({
      ...current,
      categories: current.categories.map((entry, index) =>
        index !== categoryIndex
          ? entry
          : {
              ...entry,
              items: [
                ...entry.items,
                {
                  id: nextId("item"),
                  name: "New Item",
                  description: "",
                  sizes: { '6"': "", '12"': "" },
                },
              ],
            }
      ),
    }));
    setEditingKey(`item:${category.id}:${newItemIndex}`);
  }

  function removeItem(categoryIndex, itemIndex) {
    setMenu((current) => ({
      ...current,
      categories: current.categories.map((category, index) =>
        index !== categoryIndex
          ? category
          : {
              ...category,
              items: category.items.filter((_, currentItemIndex) => currentItemIndex !== itemIndex),
            }
      ),
    }));
    setEditingKey(null);
  }

  function addCategory(side, panel) {
    const id = nextId("cat");
    setMenu((current) => ({
      ...current,
      categories: [
        ...current.categories,
        {
          id,
          name: "New Category",
          description: "",
          side,
          panel,
          layout: "priced",
          items: [],
          images: [],
        },
      ],
    }));
    setEditingKey(`category:${id}`);
  }

  function removeCategory(categoryIndex) {
    if (!window.confirm("Remove this category and all of its items?")) return;
    setMenu((current) => ({
      ...current,
      categories: current.categories.filter((_, index) => index !== categoryIndex),
    }));
    setEditingKey(null);
  }

  function ensureImageSlot(category, imageIndex) {
    const images = [...(category.images || [])];
    while (images.length <= imageIndex) {
      images.push({ id: nextId("image"), url: "" });
    }
    return images;
  }

  function setCategoryImage(categoryIndex, imageIndex, url) {
    setMenu((current) => ({
      ...current,
      categories: current.categories.map((category, index) => {
        if (index !== categoryIndex) return category;
        const images = ensureImageSlot(category, imageIndex);
        images[imageIndex] = { ...images[imageIndex], url };
        return { ...category, images };
      }),
    }));
  }

  function readCategoryImage(file, categoryIndex, imageIndex) {
    if (!file || !file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = (event) => setCategoryImage(categoryIndex, imageIndex, event.target.result);
    reader.readAsDataURL(file);
  }

  function readMenuImage(file, field) {
    if (!file || !file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = (event) => setMenuField(field, event.target.result);
    reader.readAsDataURL(file);
  }

  function handleDragEnd(event) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const activeId = String(active.id);
    const overId = String(over.id);

    if (activeId.startsWith("cat:") && overId.startsWith("cat:")) {
      const activeCategoryId = activeId.slice(4);
      const overCategoryId = overId.slice(4);
      setMenu((current) => {
        const fromIndex = current.categories.findIndex((category) => category.id === activeCategoryId);
        const toIndex = current.categories.findIndex((category) => category.id === overCategoryId);
        if (fromIndex < 0 || toIndex < 0) return current;
        return { ...current, categories: arrayMove(current.categories, fromIndex, toIndex) };
      });
      return;
    }

    if (activeId.startsWith("item:") && overId.startsWith("item:")) {
      const [, activeCategoryId, activeItemId] = activeId.split(":");
      const [, overCategoryId, overItemId] = overId.split(":");
      if (activeCategoryId !== overCategoryId) return;

      setMenu((current) => ({
        ...current,
        categories: current.categories.map((category) => {
          if (category.id !== activeCategoryId) return category;
          const fromIndex = category.items.findIndex((item) => item.id === activeItemId);
          const toIndex = category.items.findIndex((item) => item.id === overItemId);
          if (fromIndex < 0 || toIndex < 0) return category;
          return { ...category, items: arrayMove(category.items, fromIndex, toIndex) };
        }),
      }));
    }
  }

  async function saveMenu() {
    if (!canEdit) return;
    setSaving(true);
    try {
      await onSaveConfig(menu);
      setEditMode(false);
      setEditingKey(null);
    } finally {
      setSaving(false);
    }
  }

  function cancelEditing() {
    setMenu(normalizeMenu(rawConfig || (!businessName ? BAMS_MENU_PRESET : DEFAULT_MENU)));
    setEditMode(false);
    setEditingKey(null);
  }

  function renderImageSlot(categoryIndex, imageIndex, className, label) {
    const category = menu.categories[categoryIndex];
    const image = category.images?.[imageIndex];
    const url = image?.url || "";

    if (!url && !editMode) return null;

    return (
      <div className={`bams-photo-slot ${className || ""}`}>
        {url ? (
          <img src={url} alt={label || category.name} className="bams-photo" />
        ) : (
          <span className="bams-photo-placeholder">{label || "Add photo"}</span>
        )}
        {editMode && (
          <div className="bams-photo-actions no-print">
            <label className="bams-photo-button">
              {url ? "Replace" : "Add photo"}
              <input
                type="file"
                accept="image/*"
                onChange={(event) => readCategoryImage(event.target.files?.[0], categoryIndex, imageIndex)}
              />
            </label>
            {url && (
              <button
                type="button"
                className="bams-photo-button bams-photo-remove"
                onClick={() => setCategoryImage(categoryIndex, imageIndex, "")}
              >
                Remove
              </button>
            )}
          </div>
        )}
      </div>
    );
  }

  function renderItem(categoryIndex, itemIndex, item, sizeOrder, simpleList = false) {
    const category = menu.categories[categoryIndex];
    const key = `item:${category.id}:${itemIndex}`;
    const isEditing = editingKey === key;
    const sortableId = itemSortId(category, item);

    return (
      <SortableItem id={sortableId} key={item.id}>
        {({ setNodeRef, attributes, listeners, transform, transition, isDragging }) => (
          <article
            ref={setNodeRef}
            className={`bams-item${simpleList ? " bams-item-simple" : ""}${editMode ? " bams-item-editable" : ""}`}
            style={{
              transform: CSS.Transform.toString(transform),
              transition,
              opacity: isDragging ? 0.45 : 1,
              zIndex: isDragging ? 4 : "auto",
            }}
          >
            {isEditing ? (
              <div className="bams-item-edit no-print">
                <input
                  className="edl-input"
                  value={item.name || ""}
                  onChange={(event) => setItemField(categoryIndex, itemIndex, "name", event.target.value)}
                  placeholder="Item name"
                  autoFocus
                />
                <textarea
                  className="edl-input"
                  value={item.description || ""}
                  onChange={(event) =>
                    setItemField(categoryIndex, itemIndex, "description", event.target.value)
                  }
                  placeholder="Description"
                  rows={2}
                />
                {item.sizes ? (
                  <div className="bams-price-edit-row">
                    {Object.keys(item.sizes).map((size) => (
                      <label key={size}>
                        <span>{size}</span>
                        <input
                          className="edl-input"
                          value={item.sizes[size] ?? ""}
                          onChange={(event) =>
                            setItemSize(categoryIndex, itemIndex, size, event.target.value)
                          }
                        />
                      </label>
                    ))}
                    <button type="button" onClick={() => toggleSinglePrice(categoryIndex, itemIndex, true)}>
                      Single price
                    </button>
                  </div>
                ) : (
                  <div className="bams-price-edit-row">
                    <label>
                      <span>Price</span>
                      <input
                        className="edl-input"
                        value={item.price ?? ""}
                        onChange={(event) =>
                          setItemField(categoryIndex, itemIndex, "price", event.target.value)
                        }
                      />
                    </label>
                    <button type="button" onClick={() => toggleSinglePrice(categoryIndex, itemIndex, false)}>
                      Add sizes
                    </button>
                  </div>
                )}
              </div>
            ) : simpleList ? (
              <>
                <strong className="bams-simple-name">{item.name}</strong>
                {item.price && <span className="bams-simple-price">{money(item.price)}</span>}
              </>
            ) : (
              <>
                <div className="bams-item-heading">
                  <strong className="bams-item-name">{item.name}</strong>
                  <span
                    className="bams-item-prices"
                    style={{
                      gridTemplateColumns: `repeat(${item.sizes ? Math.max(sizeOrder.length, 1) : 1}, 4.8cqw)`,
                      width: `${(item.sizes ? Math.max(sizeOrder.length, 1) : 1) * 4.8 + (item.sizes ? Math.max(sizeOrder.length - 1, 0) : 0) * 0.35}cqw`,
                    }}
                  >
                    {item.sizes
                      ? sizeOrder.map((size) => (
                          <span key={size} className="bams-item-price">
                            {money(item.sizes[size])}
                          </span>
                        ))
                      : item.price
                        ? <span className="bams-item-price bams-item-price-single">{money(item.price)}</span>
                        : null}
                  </span>
                </div>
                {item.description && <p className="bams-item-description">{item.description}</p>}
              </>
            )}

            {editMode && (
              <div className="bams-item-controls no-print">
                <button type="button" className="bams-icon-button" {...attributes} {...listeners} title="Drag">
                  <MoveIcon />
                </button>
                <button
                  type="button"
                  className="bams-icon-button"
                  onClick={() => setEditingKey(isEditing ? null : key)}
                  title={isEditing ? "Done" : "Edit"}
                >
                  {isEditing ? "✓" : "✎"}
                </button>
                <button
                  type="button"
                  className="bams-icon-button bams-danger"
                  onClick={() => removeItem(categoryIndex, itemIndex)}
                  title="Remove"
                >
                  ×
                </button>
              </div>
            )}
          </article>
        )}
      </SortableItem>
    );
  }

  function renderBanner(category) {
    return (
      <header className="bams-section-banner">
        <span className="bams-sunburst" aria-hidden="true" />
        <h2>{category.name}</h2>
        <span className="bams-sunburst" aria-hidden="true" />
      </header>
    );
  }

  function renderCategory(categoryIndex, options = {}) {
    const category = menu.categories[categoryIndex];
    const isEditing = editingKey === `category:${category.id}`;
    const layout = category.layout || "priced";
    const simpleList = layout === "simple";
    const sizeOrder = category.size_order?.length
      ? category.size_order
      : Array.from(
          new Set(category.items.flatMap((item) => (item.sizes ? Object.keys(item.sizes) : [])))
        );
    const sortableItems = category.items.map((item) => itemSortId(category, item));
    const sortableId = categorySortId(category);

    return (
      <SortableCategory id={sortableId} key={category.id}>
        {({ setNodeRef, attributes, listeners, transform, transition, isDragging }) => (
          <section
            ref={setNodeRef}
            className={`bams-category bams-category-${layout}${options.className ? ` ${options.className}` : ""}`}
            style={{
              transform: CSS.Transform.toString(transform),
              transition,
              opacity: isDragging ? 0.45 : 1,
              zIndex: isDragging ? 5 : "auto",
            }}
          >
            {editMode && (
              <div className="bams-category-toolbar no-print">
                <button type="button" className="bams-icon-button" {...attributes} {...listeners} title="Drag category">
                  <MoveIcon />
                </button>
                <button
                  type="button"
                  className="bams-icon-button"
                  onClick={() => setEditingKey(isEditing ? null : `category:${category.id}`)}
                >
                  {isEditing ? "✓" : "✎"}
                </button>
                <button
                  type="button"
                  className="bams-icon-button bams-danger"
                  onClick={() => removeCategory(categoryIndex)}
                >
                  ×
                </button>
              </div>
            )}

            {isEditing ? (
              <div className="bams-category-edit no-print">
                <input
                  className="edl-input"
                  value={category.name || ""}
                  onChange={(event) => setCategoryField(categoryIndex, "name", event.target.value)}
                  placeholder="Category name"
                  autoFocus
                />
                <textarea
                  className="edl-input"
                  value={category.description || ""}
                  onChange={(event) =>
                    setCategoryField(categoryIndex, "description", event.target.value)
                  }
                  placeholder="Category description"
                  rows={2}
                />
              </div>
            ) : (
              <>
                {renderBanner(category)}
                {category.description && <p className="bams-section-intro">{category.description}</p>}
              </>
            )}

            {!simpleList && sizeOrder.length > 0 && (
              <div
                className="bams-size-header"
                style={{ "--bams-price-count": Math.max(sizeOrder.length, 1) }}
              >
                <span />
                {sizeOrder.map((size) => <span key={size}>{size}</span>)}
              </div>
            )}

            <div className={`bams-items${simpleList ? " bams-simple-list" : ""}`}>
              <SortableContext items={sortableItems} strategy={verticalListSortingStrategy}>
                {category.items.map((item, itemIndex) =>
                  renderItem(categoryIndex, itemIndex, item, sizeOrder, simpleList)
                )}
              </SortableContext>
            </div>

            {editMode && (
              <button type="button" className="bams-add-button no-print" onClick={() => addItem(categoryIndex)}>
                + Add item
              </button>
            )}

            {options.afterItems?.(categoryIndex)}
          </section>
        )}
      </SortableCategory>
    );
  }

  function findCategoryIndex(layout, fallbackName) {
    const byLayout = menu.categories.findIndex((category) => category.layout === layout);
    if (byLayout >= 0) return byLayout;
    return menu.categories.findIndex(
      (category) => category.name.toLowerCase() === String(fallbackName || "").toLowerCase()
    );
  }

  function renderInsidePage() {
    const classicIndex = findCategoryIndex("classic", "Classic Subs");
    const specialtyIndex = findCategoryIndex("specialty", "Specialty Subs");
    const saladsIndex = findCategoryIndex("salads", "Sub Salads");
    const dressingsIndex = findCategoryIndex("dressings", "Dressings");

    return (
      <section className="bams-sheet bams-inside-sheet" aria-label="Inside menu">
        <div className="bams-panels">
          <div className="bams-panel bams-panel-left">
            {classicIndex >= 0 && renderCategory(classicIndex, {
              afterItems: (categoryIndex) =>
                renderImageSlot(categoryIndex, 0, "bams-photo-wide bams-classic-photo", "Classic sub photo"),
            })}
          </div>

          <div className="bams-panel bams-panel-middle">
            {specialtyIndex >= 0 && renderCategory(specialtyIndex)}
            {saladsIndex >= 0 && renderCategory(saladsIndex, { className: "bams-salads-block" })}
          </div>

          <div className="bams-panel bams-panel-right">
            {dressingsIndex >= 0 && renderCategory(dressingsIndex, {
              afterItems: (categoryIndex) => (
                <div className="bams-dressings-feature">
                  {renderImageSlot(categoryIndex, 0, "bams-photo-hero", "Featured sub photo")}

                  <div className="bams-feature-statement">
                    <span className="bams-ornament-line" />
                    <span className="bams-feature-sun" aria-hidden="true" />
                    <p>{menu.ingredientStatement || "All of our meats are top quality, paired with real cheese. Our veggies are fresh and local."}</p>
                    <span className="bams-ornament-line" />
                  </div>

                  <div className="bams-photo-pair">
                    {renderImageSlot(categoryIndex, 1, "bams-photo-small", "Sub photo")}
                    {renderImageSlot(categoryIndex, 2, "bams-photo-small", "Sub photo")}
                  </div>

                  <blockquote className="bams-closing-quote">
                    {menu.closingQuote || menu.footer || '“Our goal is to give our customers the best sub possible.”'}
                  </blockquote>
                  <div className="bams-quote-flourish" aria-hidden="true">
                    <span />
                    <i />
                    <span />
                  </div>
                </div>
              ),
            })}
          </div>
        </div>
      </section>
    );
  }

  function renderBackPanel(side, panel) {
    const indices = menu.categories
      .map((_, index) => index)
      .filter((index) => {
        const category = menu.categories[index];
        return (category.side || "front") === side && category.panel === panel;
      });

    const sortableIds = indices.map((index) => categorySortId(menu.categories[index]));

    return (
      <SortableContext items={sortableIds} strategy={verticalListSortingStrategy}>
        {indices.map((categoryIndex) => {
          const category = menu.categories[categoryIndex];
          const addPhoto = category.layout === "combos" || category.layout === "desserts";
          return renderCategory(categoryIndex, {
            afterItems: addPhoto
              ? (index) => renderImageSlot(index, 0, "bams-photo-wide bams-back-photo", `${category.name} photo`)
              : undefined,
          });
        })}
      </SortableContext>
    );
  }

  function renderCoverPanel() {
    const hours = menu.hours || {};
    const dayRows = [
      ["Monday", hours.monday],
      ["Tuesday", hours.tuesday],
      ["Wednesday", hours.wednesday],
      ["Thursday", hours.thursday],
      ["Friday", hours.friday],
      ["Saturday", hours.saturday],
      ["Sunday", hours.sunday],
    ];

    return (
      <div className="bams-cover-panel">
        <div className="bams-cover-brand">
          {menu.logo_url ? (
            <div className="bams-logo-wrap">
              <img src={menu.logo_url} alt={`${menu.title || "Bam's"} logo`} className="bams-logo" />
              {editMode && (
                <button type="button" className="bams-logo-remove no-print" onClick={() => setMenuField("logo_url", "")}>×</button>
              )}
            </div>
          ) : editMode ? (
            <label className="bams-logo-upload no-print">
              Add shop logo
              <input type="file" accept="image/*" onChange={(event) => readMenuImage(event.target.files?.[0], "logo_url")} />
            </label>
          ) : (
            <div className="bams-logo-lettering" aria-hidden="true">
              <span>Bam’s</span>
              <small>Sub Shoppe</small>
            </div>
          )}

          <h1>{menu.title || businessName || "Bam’s Sub Shoppe"}</h1>
          <p className="bams-cover-address">
            {menu.address || "203 W. Main Street"}<br />
            {menu.city || "Rangely, CO"}
          </p>
          <p className="bams-cover-phone">{menu.phone || "970-572-0136"}</p>
        </div>

        <section className="bams-hours-card">
          <h2><span />Hours<span /></h2>
          <div className="bams-hours-list">
            {dayRows.map(([day, value]) => (
              <div className="bams-hours-row" key={day}>
                <strong>{day}</strong>
                <span>{value || ""}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="bams-delivery-block">
          <h2><span />We Deliver<span /></h2>
          <p>Gas surcharge</p>
          <div className="bams-delivery-list">
            {(menu.delivery || []).map((entry, index) => (
              <div className="bams-delivery-row" key={`${entry.location}-${index}`}>
                <strong>{entry.location}</strong>
                <i aria-hidden="true" />
                <span>{entry.surcharge}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    );
  }

  function renderOutsidePage() {
    return (
      <section className="bams-sheet bams-outside-sheet" aria-label="Outside menu">
        <div className="bams-panels">
          <div className="bams-panel bams-panel-left bams-back-column">
            {renderBackPanel("back", "left")}
            {editMode && (
              <button type="button" className="bams-add-button no-print" onClick={() => addCategory("back", "left")}>+ Add section</button>
            )}
          </div>

          <div className="bams-panel bams-panel-middle bams-back-column">
            {renderBackPanel("back", "middle")}
            {editMode && (
              <button type="button" className="bams-add-button no-print" onClick={() => addCategory("back", "middle")}>+ Add section</button>
            )}
          </div>

          <div className="bams-panel bams-panel-right bams-cover-column">
            {renderCoverPanel()}
          </div>
        </div>
      </section>
    );
  }

  function renderListMode() {
    return (
      <section className="bams-sheet bams-list-sheet">
        <header className="bams-list-title">
          <h1>{menu.title || businessName || "Menu"}</h1>
          {menu.subtitle && <p>{menu.subtitle}</p>}
        </header>
        <div className="bams-list-grid">
          {menu.categories.map((_, categoryIndex) => renderCategory(categoryIndex))}
        </div>
      </section>
    );
  }

  if (!menu.categories.length && !canEdit) {
    return (
      <div className="bams-empty-state">
        <strong>No menu items yet.</strong>
        <span>Use the menu editor or AI Assistant to add categories and items.</span>
      </div>
    );
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <div className="bams-menu-root">
        <style>{`@page { size: letter landscape; margin: 0; }`}</style>

        {canEdit && (
          <div className="bams-toolbar no-print">
            <div>
              <span className="bams-toolbar-kicker">PRINTABLE TRI-FOLD</span>
              <h1>Bam’s Menu</h1>
            </div>
            <div className="bams-toolbar-actions">
              {editMode && (
                <select value={preset} onChange={(event) => setMenuField("preset", event.target.value)}>
                  <option value="pamphlet">Pamphlet</option>
                  <option value="list">Simple list</option>
                </select>
              )}
              {editMode ? (
                <>
                  <button type="button" onClick={cancelEditing}>Cancel</button>
                  <button type="button" className="bams-primary-button" disabled={saving} onClick={saveMenu}>
                    {saving ? "Saving…" : "Done editing"}
                  </button>
                </>
              ) : (
                <button type="button" onClick={() => setEditMode(true)}>✎ Edit menu</button>
              )}
              <button type="button" onClick={() => window.print()}>Print / Save PDF</button>
            </div>
          </div>
        )}

        <main className="bams-preview-stack">
          {preset === "list" ? renderListMode() : (
            <>
              {renderInsidePage()}
              {renderOutsidePage()}
            </>
          )}
        </main>
      </div>
    </DndContext>
  );
}
