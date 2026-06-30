/**
 * Bam's Sub Shoppe — full menu seed
 *
 * HOW TO USE:
 * 1. Log in to your Business OS app in the browser
 * 2. Open Developer Tools (F12 or right-click → Inspect)
 * 3. Click the "Console" tab
 * 4. Paste everything below and press Enter
 * 5. You should see "✅ Menu saved!" — then refresh the page
 */
(async () => {
  const token = localStorage.getItem("scheduler.auth.token");
  const businessId = localStorage.getItem("business-os.active-business");
  if (!token) { alert("Not logged in — please log in first."); return; }

  const menu = {
    title: "Bam's Sub Shoppe",
    subtitle: "203 W. Main Street · Rangely, CO · (970) 572-0136",
    footer: "Our goal is to give our customers the best sub possible.",
    columns: 3,
    print_landscape: true,
    theme: {
      title_color: "#7a2e0e",
      header_color: "#7a2e0e",
      subtitle_color: "#5c4033",
      bg: "#fffdf8"
    },
    categories: [
      {
        name: "Classic Subs",
        emoji: "🥖",
        description: "All of our meats are top quality with real cheese and fresh local veggies.",
        items: [
          {
            name: "Turkey Club",
            description: "Turkey, Ham, Swiss Cheese, Lettuce, Tomato, Onion, Honey Mustard, Mayo — Toasted",
            sizes: { '6"': "11.50", '12"': "16.49" }
          },
          {
            name: "American Club",
            description: "Ham, Turkey, Bacon, American Cheese, Lettuce, Tomato, Onion, Cucumber, Mayo",
            sizes: { '6"': "12.50", '12"': "18.49" }
          },
          {
            name: "Turkey Bacon Ranch",
            description: "Turkey, Bacon, Swiss, Lettuce, Tomato, Onion, Pickle, Ranch Dressing",
            sizes: { '6"': "11.50", '12"': "16.49" }
          },
          {
            name: "Italian",
            description: "Ham, Genoa Salami, Pepperoni, Hard Salami, Provolone, Lettuce, Tomato, Onion, Parmesan, Banana Peppers, Italian Dressing",
            sizes: { '6"': "15.50", '12"': "19.99" }
          },
          {
            name: "Spicy Italian",
            description: "Genoa Salami, Pepperoni, Hard Salami, Provolone, Lettuce, Tomato, Onion, Parmesan, Banana Peppers, Italian Dressing",
            sizes: { '6"': "13.50", '12"': "18.49" }
          },
          {
            name: "B.L.T.",
            description: "Bacon, Lettuce, Tomato, Mayo",
            sizes: { '6"': "9.50", '12"': "16.49" }
          },
          {
            name: "Turkey Sub",
            description: "Turkey, Cheese, Lettuce, Tomato, Bell Peppers, Mayo",
            sizes: { '6"': "8.50", '12"': "14.49" }
          },
          {
            name: "Ham N' Cheese",
            description: "Ham, American Cheese, Lettuce, Spinach, Tomato, Onion, Bell Peppers, Ranch Dressing",
            sizes: { '6"': "8.50", '12"': "14.49" }
          },
          {
            name: "Loaded Veggie",
            description: "Lettuce, Spinach, Tomato, Onion, Olives, Cucumber, Bell Peppers, Mayo",
            sizes: { '6"': "7.00", '12"': "12.99" }
          }
        ]
      },
      {
        name: "Specialty Subs",
        emoji: "⭐",
        description: "House creations — each one a flavor experience.",
        items: [
          {
            name: "Meatball Sub",
            description: "Meatballs, Onion, Olives, Bell Pepper, Mozzarella — Toasted",
            sizes: { '6"': "10.99", '12"': "18.25" }
          },
          {
            name: '"Miss Pauline"',
            description: "Roast Beef, Mushrooms, Onion, Provolone, Homemade Ajou — Toasted",
            sizes: { '6"': "12.50", '12"': "17.49" }
          },
          {
            name: '"Bam\'s"',
            description: "Roast Beef, Swiss, Horseradish, Lettuce, Tomato, Onion",
            sizes: { '6"': "11.50", '12"': "16.49" }
          },
          {
            name: "Popeye",
            description: "Ham, Pepper Jack, Spinach, Tomato, Onion, Black Olives, Jalapeños, Chipotle Mayo",
            sizes: { '6"': "8.50", '12"': "14.49" }
          },
          {
            name: "Mesquite Chicken Melt",
            description: "Mesquite Chicken, Swiss, Lettuce, Spinach, Bell Peppers, Onion, Mayo — Toasted",
            sizes: { '6"': "12.50", '12"': "17.49" }
          },
          {
            name: "The Bomb",
            description: "Roast Beef, Turkey, Ham, Hard Salami, Swiss, Lettuce, Spinach, Tomato, Onion, Bell Peppers, Cucumber, Mayo, Italian Dressing",
            sizes: { '6"': "16.50", '12"': "20.99" }
          },
          {
            name: '"Dagwood" Sub',
            description: "Turkey, Roast Beef, Bacon, Ham, Genoa Salami, Pepperoni, Hard Salami, American & Provolone Cheese, Choice of Veggies, Mayo, Italian Dressing",
            sizes: { '6"': "18.25", '12"': "27.25" }
          },
          {
            name: "Roast Beef Sub",
            description: "Roast Beef with your choice of toppings",
            sizes: { '6"': "8.50", '12"': "14.49" }
          },
          {
            name: "Deluxe Grilled Cheese",
            description: "Toasted on your choice of bread with premium cheese",
            sizes: { '6"': "12.50", '12"': "17.49" }
          },
          {
            name: "Pulled Pork",
            description: "Slow-roasted pulled pork with your choice of toppings",
            sizes: { '6"': "12.50", '12"': "17.50" }
          }
        ]
      },
      {
        name: "Sub Salads",
        emoji: "🥗",
        description: "Specialty salads made fresh — available daily upon request.",
        items: [
          {
            name: "Tuna Salad",
            sizes: { '6"': "9.49", '12"': "14.49" }
          },
          {
            name: "Chicken Salad",
            sizes: { '6"': "9.49", '12"': "14.49" }
          },
          {
            name: "Egg Salad",
            sizes: { '6"': "10.00", '12"': "15.00" }
          },
          {
            name: "Seafood Salad",
            sizes: { '6"': "10.49", '12"': "15.49" }
          }
        ]
      },
      {
        name: "Dressings",
        emoji: "🫙",
        description: "Available on any sub.",
        items: [
          { name: "Mayo" },
          { name: "Ranch" },
          { name: "Chipotle Mayo" },
          { name: "Mustard" },
          { name: "Honey Mustard" },
          { name: "Horseradish" },
          { name: "Italian" },
          { name: "Oil" },
          { name: "Vinegar" },
          { name: "Ketchup" }
        ]
      },
      {
        name: "Sub Combos",
        emoji: "🥤",
        side: "back",
        description: "Complete your sub with a meal deal — combo, chips & a soda.",
        items: [
          { name: "Combo Meal", description: "Chips & a soda", price: "2.75" }
        ]
      },
      {
        name: "Breads",
        emoji: "🍞",
        side: "back",
        description: "Baked fresh daily. Try different flavors to enhance your meal!",
        items: [
          { name: "Italian" },
          { name: "Herb & Cheese" },
          { name: "Jalapeño" },
          { name: "White" }
        ]
      },
      {
        name: "Extras",
        emoji: "➕",
        side: "back",
        items: [
          { name: "Extra Cheese", description: "Per type", sizes: { '6"': "1.50", '12"': "2.50" } },
          { name: "Extra Meat", sizes: { '6"': "2.50", '12"': "4.50" } },
          { name: "Specialty Bread", price: "1.50" }
        ]
      },
      {
        name: "Soups",
        emoji: "🍲",
        side: "back",
        description: "Homemade from fresh ingredients. Ask which soups are available today!",
        items: [
          { name: "12 oz Cup of Soup", price: "4.10" }
        ]
      },
      {
        name: "Desserts",
        emoji: "🍫",
        side: "back",
        description: "Tastes like homemade.",
        items: [
          { name: "Brownies (2 pack)", price: "1.50" },
          { name: "Chips" },
          { name: "Soda" },
          { name: "Water" }
        ]
      },
      {
        name: "Hours",
        emoji: "🕐",
        side: "back",
        description: "203 W. Main Street, Rangely, CO · (970) 572-0136",
        items: [
          { name: "Monday",    description: "11:00 am – 7:00 pm" },
          { name: "Tuesday",   description: "11:00 am – 7:00 pm" },
          { name: "Wednesday", description: "CLOSED" },
          { name: "Thursday",  description: "11:00 am – 7:00 pm" },
          { name: "Friday",    description: "11:00 am – 7:00 pm" },
          { name: "Saturday",  description: "11:00 am – 7:00 pm" },
          { name: "Sunday",    description: "CLOSED" }
        ]
      },
      {
        name: "Delivery",
        emoji: "🚗",
        side: "back",
        description: "We deliver! Gas surcharge applies.",
        items: [
          { name: "Rangely",        price: "2.50" },
          { name: "Dinosaur",       price: "10.00" },
          { name: "Deserado Mine",  price: "10.00" }
        ]
      },
      {
        name: "Catering",
        emoji: "🎉",
        side: "back",
        description: "Sporting events, meetings, parties & events. Contact Bam for pricing: (970) 572-0136",
        items: []
      }
    ]
  };

  try {
    const res = await fetch("/platform/ui-config", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
        ...(businessId ? { "X-Business-Id": businessId } : {})
      },
      body: JSON.stringify({ patch: { menu } })
    });
    const data = await res.json();
    if (res.ok) {
      console.log("✅ Menu saved!", data);
      alert("✅ Menu saved! Refresh the page to see it (or navigate away and back to Menu).");
    } else {
      console.error("❌ Error:", data);
      alert("❌ Error: " + JSON.stringify(data));
    }
  } catch (err) {
    console.error("❌ Network error:", err);
    alert("❌ Network error: " + err.message);
  }
})();
