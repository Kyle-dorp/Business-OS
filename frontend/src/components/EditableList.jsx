export function EditableList({ items, onChange, placeholder = "New item" }) {
  function rename(i, val) {
    const next = [...items];
    next[i] = val;
    onChange(next);
  }
  function remove(i) { onChange(items.filter((_, idx) => idx !== i)); }
  function move(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= items.length) return;
    const next = [...items];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  }
  function add() { onChange([...items, placeholder]); }

  return (
    <div className="edl-list">
      {items.map((item, i) => (
        <div className="edl-row" key={i}>
          <div className="edl-arrows">
            <button type="button" onClick={() => move(i, -1)} disabled={i === 0}>↑</button>
            <button type="button" onClick={() => move(i, 1)} disabled={i === items.length - 1}>↓</button>
          </div>
          <input className="edl-input" value={item} onChange={(e) => rename(i, e.target.value)} />
          <button type="button" className="edl-remove" onClick={() => remove(i)}>×</button>
        </div>
      ))}
      <button type="button" className="edl-add" onClick={add}>+ Add</button>
    </div>
  );
}
