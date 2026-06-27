const DEFAULT_MENU = {
  title: "Menu",
  subtitle: "",
  categories: [],
};

export default function MenuPage({ config: rawConfig, businessName }) {
  const menu = rawConfig || DEFAULT_MENU;

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
            "Add a menu category called 'Subs' with Dagwoods (6" $8.99 / 12" $13.99) and Bomb (6" $8.49 / 12" $13.49). Add a 'Soups' category with Chicken Noodle at $3.99."
          </blockquote>
        </div>
      </div>
    );
  }

  return (
    <div className="page menu-page">
      <div className="page-header menu-page-header no-print">
        <div><span className="eyebrow">PRINTABLE</span><h1>Menu</h1></div>
        <button className="secondary-btn compact" onClick={() => window.print()}>Print / Save PDF</button>
      </div>

      <div className="menu-sheet">
        <div className="menu-title-block">
          <h1 className="menu-title">{menu.title || businessName || "Menu"}</h1>
          {menu.subtitle && <p className="menu-subtitle">{menu.subtitle}</p>}
        </div>

        <div className="menu-categories">
          {menu.categories.map((cat, ci) => (
            <div className="menu-category" key={ci}>
              <h2 className="menu-cat-name">{cat.name}</h2>
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
                              <span className="menu-price">${price}</span>
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
  );
}
