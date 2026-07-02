import { useState } from "react";
import MenuPagePamphlet from "./MenuPagePamphlet";
import MenuEditor from "../components/MenuEditor";
import { BAMS_MENU_PRESET } from "../data/bamsMenuPreset";

export default function MenuPage({ config: rawConfig, businessName, onSaveConfig }) {
  const [menuConfig, setMenuConfig] = useState(rawConfig || BAMS_MENU_PRESET);
  const [editMode, setEditMode] = useState(false);
  const [saving, setSaving] = useState(false);

  const canEdit = typeof onSaveConfig === "function";

  const handleSaveMenu = async (updatedMenu) => {
    setSaving(true);
    setMenuConfig(updatedMenu);
    if (canEdit) {
      await onSaveConfig(updatedMenu);
    }
    setSaving(false);
  };

  return (
    <>
      <style>{`
        @media print {
          * { margin: 0; padding: 0; border: 0; }
          html, body { width: 100%; height: 100%; }
          .no-print { display: none !important; }
          @page { size: letter landscape; margin: 0; }
        }
        .menu-toolbar {
          padding: 16px;
          border-bottom: 1px solid #ddd;
          display: flex;
          gap: 12px;
          align-items: center;
          justify-content: space-between;
          background-color: #f9f9f9;
        }
        .menu-toolbar h2 {
          margin: 0;
          font-size: 18px;
        }
        .menu-toolbar-actions {
          display: flex;
          gap: 12px;
          align-items: center;
        }
        .menu-toolbar button {
          padding: 8px 16px;
          background-color: #2f6fed;
          color: #fff;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-weight: 600;
          font-size: 14px;
        }
        .menu-toolbar button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        .menu-toolbar button.secondary {
          background-color: #fff;
          color: #333;
          border: 1px solid #ccc;
        }
      `}</style>

      {/* Editing toolbar - hidden on print */}
      {canEdit && (
        <div className="no-print menu-toolbar">
          <h2>Menu</h2>
          <div className="menu-toolbar-actions">
            <button className="secondary" onClick={() => setEditMode(!editMode)}>
              {editMode ? "Done Editing" : "✏️ Edit Menu"}
            </button>
            <button className="secondary" onClick={() => window.print()}>
              🖨️ Print
            </button>
          </div>
        </div>
      )}

      {/* Edit mode */}
      {editMode && canEdit && (
        <MenuEditor
          config={menuConfig}
          onSave={handleSaveMenu}
          onClose={() => setEditMode(false)}
        />
      )}

      {/* Menu display */}
      {!editMode && (
        <MenuPagePamphlet
          config={menuConfig}
          businessName={businessName}
          onSaveConfig={canEdit ? handleSaveMenu : undefined}
        />
      )}
    </>
  );
}
