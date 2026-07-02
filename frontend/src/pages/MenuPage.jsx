import { useState } from "react";

export default function MenuPage({ config: rawConfig, businessName, onSaveConfig }) {
  const [frontImage, setFrontImage] = useState(rawConfig?.front_image || "");
  const [backImage, setBackImage] = useState(rawConfig?.back_image || "");
  const [saving, setSaving] = useState(false);

  const canEdit = typeof onSaveConfig === "function";

  const handleUploadFront = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => setFrontImage(e.target.result);
    reader.readAsDataURL(file);
  };

  const handleUploadBack = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => setBackImage(e.target.result);
    reader.readAsDataURL(file);
  };

  const handleSave = async () => {
    if (!canEdit) return;
    setSaving(true);
    await onSaveConfig({ front_image: frontImage, back_image: backImage });
    setSaving(false);
  };

  return (
    <>
      <style>{`
        @media print {
          * { margin: 0; padding: 0; border: 0; }
          html, body { width: 100%; height: 100%; }
          .no-print { display: none !important; }
          @page { size: letter; margin: 0; }
          img { width: 100%; height: 100%; object-fit: contain; display: block; }
        }
      `}</style>

      {/* Editing toolbar - hidden on print */}
      {canEdit && (
        <div className="no-print" style={{ padding: "16px", borderBottom: "1px solid #ddd", display: "flex", gap: "12px", alignItems: "center", justifyContent: "space-between", backgroundColor: "#f9f9f9" }}>
          <h2 style={{ margin: 0 }}>Menu</h2>
          <div style={{ display: "flex", gap: "12px" }}>
            <label style={{ cursor: "pointer", padding: "8px 12px", border: "1px solid #ccc", borderRadius: "6px", backgroundColor: "#fff", fontSize: "14px", fontWeight: "600" }}>
              📤 Upload Front
              <input type="file" accept="image/*" onChange={(e) => handleUploadFront(e.target.files?.[0])} style={{ display: "none" }} />
            </label>
            <label style={{ cursor: "pointer", padding: "8px 12px", border: "1px solid #ccc", borderRadius: "6px", backgroundColor: "#fff", fontSize: "14px", fontWeight: "600" }}>
              📤 Upload Back
              <input type="file" accept="image/*" onChange={(e) => handleUploadBack(e.target.files?.[0])} style={{ display: "none" }} />
            </label>
            <button onClick={handleSave} disabled={saving} style={{ padding: "8px 16px", backgroundColor: "#2f6fed", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "600" }}>
              {saving ? "Saving..." : "Save"}
            </button>
            <button onClick={() => window.print()} style={{ padding: "8px 16px", backgroundColor: "#fff", border: "1px solid #ccc", borderRadius: "6px", cursor: "pointer", fontWeight: "600" }}>
              🖨 Print
            </button>
          </div>
        </div>
      )}

      {/* Preview - hidden on print */}
      <div className="no-print" style={{ padding: "20px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
          {frontImage && (
            <div>
              <h3>Front</h3>
              <img src={frontImage} alt="Front" style={{ width: "100%", border: "1px solid #ddd" }} />
            </div>
          )}
          {backImage && (
            <div>
              <h3>Back</h3>
              <img src={backImage} alt="Back" style={{ width: "100%", border: "1px solid #ddd" }} />
            </div>
          )}
        </div>
      </div>

      {/* PRINT ONLY - Page 1: Front */}
      {frontImage && (
        <div style={{ width: "8.5in", height: "11in", pageBreakAfter: "always", display: "block" }}>
          <img src={frontImage} alt="Front" />
        </div>
      )}

      {/* PRINT ONLY - Page 2: Back */}
      {backImage && (
        <div style={{ width: "8.5in", height: "11in", display: "block" }}>
          <img src={backImage} alt="Back" />
        </div>
      )}
    </>
  );
}
