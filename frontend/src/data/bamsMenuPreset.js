/**
 * Bam's Sub Shoppe printable tri-fold preset.
 *
 * Page 1 (inside): Classic Subs | Specialty Subs + Sub Salads | Dressings + photos/quote
 * Page 2 (outside): Combos/Breads/Desserts | Soups/Extras/Catering | shop cover
 *
 * All menu copy remains normal editable data. Empty image slots only appear while editing
 * and collapse completely in the printed/read-only menu until a real image is added.
 */
export const BAMS_MENU_PRESET = {
  title: "Bam's Sub Shoppe",
  subtitle: "203 W. Main Street · Rangely, CO · (970) 572-0136",
  footer: '“Our goal is to give our customers the best sub possible.”',
  closingQuote: '“Our goal is to give our customers the best sub possible.”',
  ingredientStatement:
    "All of our meats are top quality, paired with real cheese. Our veggies are from a fresh local vendor to top off any sub.",
  print_landscape: true,
  preset: "pamphlet",
  logo_url: "",

  categories: [
    {
      id: "cat-classic",
      name: "Classic Subs",
      side: "front",
      panel: "left",
      layout: "classic",
      description: "All of our meats are top quality with real cheese and fresh local veggies.",
      images: [{ id: "classic-main-photo", url: "" }],
      items: [
        {
          id: "item-turkey-club",
          name: "Turkey Club",
          description: "Turkey, Ham, Swiss Cheese, Lettuce, Tomato, Onion, Honey Mustard, Mayo — Toasted",
          sizes: { '6"': "11.50", '12"': "16.49" },
        },
        {
          id: "item-american",
          name: "American Club",
          description: "Ham, Turkey, Bacon, American Cheese, Lettuce, Tomato, Onion, Cucumber, Mayo",
          sizes: { '6"': "12.50", '12"': "18.49" },
        },
        {
          id: "item-bacon-ranch",
          name: "Turkey Bacon Ranch",
          description: "Turkey, Bacon, Swiss, Lettuce, Tomato, Onion, Pickle, Ranch Dressing",
          sizes: { '6"': "11.50", '12"': "16.49" },
        },
        {
          id: "item-italian",
          name: "Italian",
          description: "Ham, Genoa Salami, Pepperoni, Hard Salami, Provolone, Lettuce, Tomato, Onion, Parmesan, Banana Peppers, Italian Dressing",
          sizes: { '6"': "15.50", '12"': "19.99" },
        },
        {
          id: "item-spicy-italian",
          name: "Spicy Italian",
          description: "Genoa Salami, Pepperoni, Hard Salami, Provolone, Lettuce, Tomato, Onion, Parmesan, Banana Peppers, Italian Dressing",
          sizes: { '6"': "13.50", '12"': "18.49" },
        },
        {
          id: "item-blt",
          name: "B.L.T.",
          description: "Bacon, Lettuce, Tomato, Mayo",
          sizes: { '6"': "9.50", '12"': "16.49" },
        },
        {
          id: "item-turkey-sub",
          name: "Turkey Sub",
          description: "Turkey, Cheese, Lettuce, Tomato, Bell Peppers, Mayo",
          sizes: { '6"': "8.50", '12"': "14.49" },
        },
        {
          id: "item-ham-cheese",
          name: "Ham N' Cheese",
          description: "Ham, American Cheese, Lettuce, Spinach, Tomato, Onion, Bell Peppers, Ranch Dressing",
          sizes: { '6"': "8.50", '12"': "14.49" },
        },
        {
          id: "item-veggie",
          name: "Loaded Veggie",
          description: "Lettuce, Spinach, Tomato, Onion, Olives, Cucumber, Bell Peppers, Mayo",
          sizes: { '6"': "7.00", '12"': "12.99" },
        },
      ],
    },

    {
      id: "cat-specialty",
      name: "Specialty Subs",
      side: "front",
      panel: "middle",
      layout: "specialty",
      description: "House creations — each one a flavor experience.",
      items: [
        {
          id: "item-meatball",
          name: "Meatball Sub",
          description: "Meatballs, Onion, Olives, Bell Pepper, Mozzarella — Toasted",
          sizes: { '6"': "10.99", '12"': "18.25" },
        },
        {
          id: "item-miss-pauline",
          name: '“Miss Pauline”',
          description: "Roast Beef, Mushrooms, Onion, Provolone, Homemade Aju — Toasted",
          sizes: { '6"': "12.50", '12"': "17.49" },
        },
        {
          id: "item-bams",
          name: '“Bam\'s”',
          description: "Roast Beef, Swiss, Horseradish, Lettuce, Tomato, Onion",
          sizes: { '6"': "11.50", '12"': "16.49" },
        },
        {
          id: "item-popeye",
          name: "Popeye",
          description: "Ham, Pepper Jack, Spinach, Tomato, Onion, Black Olives, Jalapeños, Chipotle Mayo",
          sizes: { '6"': "8.50", '12"': "14.49" },
        },
        {
          id: "item-mesquite",
          name: "Mesquite Chicken Melt",
          description: "Mesquite Chicken, Swiss, Lettuce, Spinach, Bell Peppers, Onion, Mayo — Toasted",
          sizes: { '6"': "12.50", '12"': "17.49" },
        },
        {
          id: "item-bomb",
          name: "The Bomb",
          description: "Roast Beef, Turkey, Ham, Hard Salami, Swiss, Lettuce, Spinach, Tomato, Onion, Bell Peppers, Cucumber, Mayo, Italian Dressing",
          sizes: { '6"': "16.50", '12"': "20.99" },
        },
        {
          id: "item-dagwood",
          name: '“Dagwood” Sub',
          description: "Turkey, Roast Beef, Bacon, Ham, Genoa Salami, Pepperoni, Hard Salami, American & Provolone Cheese, Choice of Veggies, Mayo, Italian Dressing",
          sizes: { '6"': "18.25", '12"': "27.25" },
        },
        {
          id: "item-roast-beef",
          name: "Roast Beef Sub",
          description: "Roast Beef with your choice of toppings",
          sizes: { '6"': "8.50", '12"': "14.49" },
        },
        {
          id: "item-grilled-cheese",
          name: "Deluxe Grilled Cheese",
          description: "Toasted on your choice of bread with premium cheese",
          sizes: { '6"': "12.50", '12"': "17.49" },
        },
        {
          id: "item-pulled-pork",
          name: "Pulled Pork",
          description: "Slow-roasted pulled pork with your choice of toppings",
          sizes: { '6"': "12.50", '12"': "17.50" },
        },
      ],
    },

    {
      id: "cat-salads",
      name: "Sub Salads",
      side: "front",
      panel: "middle",
      layout: "salads",
      size_order: ['12"', '6"'],
      description: "A specialty sub salad made daily each week upon availability.",
      items: [
        { id: "item-tuna", name: "Tuna", sizes: { '12"': "14.49", '6"': "9.49" } },
        { id: "item-chicken", name: "Chicken", sizes: { '12"': "14.49", '6"': "9.49" } },
        { id: "item-egg", name: "Egg", sizes: { '12"': "15.00", '6"': "10.00" } },
        { id: "item-seafood", name: "Seafood", sizes: { '12"': "15.49", '6"': "10.49" } },
      ],
    },

    {
      id: "cat-dressings",
      name: "Dressings",
      side: "front",
      panel: "right",
      layout: "dressings",
      description: "Available on any sub.",
      images: [
        { id: "dressings-hero", url: "" },
        { id: "dressings-small-left", url: "" },
        { id: "dressings-small-right", url: "" },
      ],
      items: [
        { id: "d-mayo", name: "Mayo" },
        { id: "d-ranch", name: "Ranch" },
        { id: "d-chipotle", name: "Chipotle Mayo" },
        { id: "d-mustard", name: "Mustard" },
        { id: "d-honey-mustard", name: "Honey Mustard" },
        { id: "d-horseradish", name: "Horseradish" },
        { id: "d-italian", name: "Italian" },
        { id: "d-oil", name: "Oil" },
        { id: "d-vinegar", name: "Vinegar" },
        { id: "d-ketchup", name: "Ketchup" },
      ],
    },

    {
      id: "cat-combos",
      name: "Sub Combos",
      side: "back",
      panel: "left",
      layout: "combos",
      description: "Complete your sub with a meal deal — combo, chips & a soda.",
      images: [{ id: "combo-photo", url: "" }],
      items: [
        { id: "item-combo-meal", name: "Combo Meal", description: "Chips & a soda", price: "2.75" },
      ],
    },

    {
      id: "cat-breads",
      name: "Breads",
      side: "back",
      panel: "left",
      layout: "simple",
      description: "Our breads are baked daily. Try a different flavor each time you visit!",
      items: [
        { id: "b-italian", name: "Italian" },
        { id: "b-herb-cheese", name: "Herb & Cheese" },
        { id: "b-jalapeno", name: "Jalapeño" },
        { id: "b-white", name: "White" },
      ],
    },

    {
      id: "cat-desserts",
      name: "Desserts",
      side: "back",
      panel: "left",
      layout: "desserts",
      description: "Tastes like homemade.",
      images: [{ id: "dessert-photo", url: "" }],
      items: [
        { id: "des-brownies", name: "Brownies (2 pack)", price: "1.50" },
        { id: "des-chips", name: "Chips" },
        { id: "des-soda", name: "Soda" },
        { id: "des-water", name: "Water" },
      ],
    },

    {
      id: "cat-soups",
      name: "Soups",
      side: "back",
      panel: "middle",
      layout: "soups",
      description: "Our specialty soups are homemade fresh from the kitchen. Ask which soup we have on special this week!",
      items: [{ id: "item-soup", name: "12 oz Cup of Soup", price: "4.10" }],
    },

    {
      id: "cat-extras",
      name: "Extras",
      side: "back",
      panel: "middle",
      layout: "extras",
      items: [
        { id: "item-extra-cheese", name: "Extra Cheese", description: "Per type", sizes: { '6"': "1.50", '12"': "2.50" } },
        { id: "item-extra-meat", name: "Extra Meat", sizes: { '6"': "2.50", '12"': "4.50" } },
        { id: "item-specialty-bread", name: "Specialty Bread", price: "1.50" },
      ],
    },

    {
      id: "cat-catering",
      name: "Catering",
      side: "back",
      panel: "middle",
      layout: "catering",
      description: "Sporting events\nMeetings\nParties\nEvents\n\nContact Bam for pricing\n970-572-0136",
      items: [],
    },
  ],

  hours: {
    monday: "11am – 7pm",
    tuesday: "11am – 7pm",
    wednesday: "CLOSED",
    thursday: "11am – 7pm",
    friday: "11am – 7pm",
    saturday: "11am – 7pm",
    sunday: "CLOSED",
  },

  delivery: [
    { location: "Rangely", surcharge: "$2.50" },
    { location: "Dinosaur", surcharge: "$10.00" },
    { location: "Deserado Mine", surcharge: "$10.00" },
  ],

  address: "203 W. Main Street",
  city: "Rangely, CO",
  phone: "970-572-0136",
};
