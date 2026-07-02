import { useState } from "react";

export default function MenuDisplay({ config }) {
  const [frontImage, setFrontImage] = useState(config?.front_image || "");
  const [backImage, setBackImage] = useState(config?.back_image || "");

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

  return (
    <div style={{ padding: "20px", backgroundColor: "#f5f5f5", minHeight: "100vh" }}>
      {/* Upload controls - hidden on print */}
      <div className="no-print" style={{
        marginBottom: "20px",
        display: "flex",
        gap: "12px",
        justifyContent: "center",
        flexWrap: "wrap"
      }}>
        <label style={{
          padding: "10px 16px",
          backgroundColor: "#2f6fed",
          color: "white",
          border: "none",
          borderRadius: "6px",
          cursor: "pointer",
          fontWeight: "600",
          fontSize: "14px"
        }}>
          📤 Upload Front
          <input type="file" accept="image/*" onChange={(e) => handleUploadFront(e.target.files?.[0])} style={{ display: "none" }} />
        </label>

        <label style={{
          padding: "10px 16px",
          backgroundColor: "#2f6fed",
          color: "white",
          border: "none",
          borderRadius: "6px",
          cursor: "pointer",
          fontWeight: "600",
          fontSize: "14px"
        }}>
          📤 Upload Back
          <input type="file" accept="image/*" onChange={(e) => handleUploadBack(e.target.files?.[0])} style={{ display: "none" }} />
        </label>

        <button onClick={() => window.print()} style={{
          padding: "10px 16px",
          backgroundColor: "#fff",
          color: "#333",
          border: "1px solid #ccc",
          borderRadius: "6px",
          cursor: "pointer",
          fontWeight: "600",
          fontSize: "14px"
        }}>
          🖨️ Print
        </button>
      </div>

      {/* Images - shown on screen and in print */}
      {frontImage && (
        <div style={{
          width: "8.5in",
          height: "11in",
          margin: "0 auto 20px",
          pageBreakAfter: "always"
        }}>
          <img src={frontImage} alt="Front" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
        </div>
      )}

      {backImage && (
        <div style={{
          width: "8.5in",
          height: "11in",
          margin: "0 auto"
        }}>
          <img src={backImage} alt="Back" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
        </div>
      )}

      {!frontImage && !backImage && (
        <div style={{
          textAlign: "center",
          padding: "40px",
          backgroundColor: "white",
          borderRadius: "8px",
          maxWidth: "600px",
          margin: "0 auto"
        }}>
          <p style={{ fontSize: "18px", color: "#666", marginBottom: "20px" }}>
            Upload your menu images above to display and print!
          </p>
        </div>
      )}

      <style>{`
        @media print {
          * { margin: 0; padding: 0; border: 0; }
          html, body { width: 100%; height: 100%; background: white; }
          .no-print { display: none !important; }
          @page { size: letter; margin: 0; }
          body { background: white; }
        }
      `}</style>
    </div>
  );
}
