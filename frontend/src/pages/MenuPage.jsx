import { useState } from "react";

export default function MenuPage({ config: rawConfig, businessName, onSaveConfig }) {
  const [menu, setMenu] = useState(rawConfig || { front_image: "", back_image: "" });
  const [saving, setSaving] = useState(false);

  const canEdit = typeof onSaveConfig === "function";

  const handleImageUpload = (side, file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const newMenu = { ...menu, [side]: e.target.result };
      setMenu(newMenu);
    };
    reader.readAsDataURL(file);
  };

  const handleSave = async () => {
    if (!canEdit) return;
    setSaving(true);
    await onSaveConfig(menu);
    setSaving(false);
  };

  return (
    <div className="bams-menu-simple">
      {canEdit && (
        <div className="bams-toolbar no-print">
          <div>
            <h1>Menu</h1>
          </div>
          <div className="bams-toolbar-actions">
            <label className="bams-toolbar-btn">
              📤 Upload Front
              <input
                type="file"
                accept="image/*"
                onChange={(e) => handleImageUpload("front_image", e.target.files?.[0])}
                style={{ display: "none" }}
              />
            </label>
            <label className="bams-toolbar-btn">
              📤 Upload Back
              <input
                type="file"
                accept="image/*"
                onChange={(e) => handleImageUpload("back_image", e.target.files?.[0])}
                style={{ display: "none" }}
              />
            </label>
            <button className="primary-btn" onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </button>
            <button className="secondary-btn" onClick={() => window.print()}>
              🖨 Print
            </button>
          </div>
        </div>
      )}

      <div className="bams-menu-images no-print" style={{ display: "flex", gap: "20px", padding: "20px", flexWrap: "wrap" }}>
        {menu.front_image && (
          <div style={{ textAlign: "center" }}>
            <h3>Front</h3>
            <img src={menu.front_image} alt="Menu Front" style={{ maxWidth: "400px", border: "1px solid #ccc" }} />
          </div>
        )}
        {menu.back_image && (
          <div style={{ textAlign: "center" }}>
            <h3>Back</h3>
            <img src={menu.back_image} alt="Menu Back" style={{ maxWidth: "400px", border: "1px solid #ccc" }} />
          </div>
        )}
      </div>

      <div className="bams-menu-print" style={{ pageBreakInside: "avoid" }}>
        {menu.front_image && (
          <div style={{ pageBreakAfter: "always", textAlign: "center" }}>
            <img src={menu.front_image} alt="Menu Front" style={{ maxWidth: "100%", height: "auto" }} />
          </div>
        )}
        {menu.back_image && (
          <div style={{ textAlign: "center" }}>
            <img src={menu.back_image} alt="Menu Back" style={{ maxWidth: "100%", height: "auto" }} />
          </div>
        )}
      </div>
    </div>
  );
}
