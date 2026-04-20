"""
Tool: search_menu
Searches La Bella Tavola's menu by category and/or dietary filter.
Menu data sourced directly from restaurant documentation (txt files in docs/restaurant_docs/).
No external API needed — all data is local.
"""

import logging
from typing import Optional

logger = logging.getLogger("tool.menu")

# ---------------------------------------------------------------------------
# La Bella Tavola — Full Menu
# Data sourced from: 01_appetizers_menu.txt, 02_pasta_dishes.txt,
# 03_seafood_specialties.txt, 04_main_courses.txt, 05_desserts_menu.txt,
# 06_wine_list.txt, 07_cocktails_beverages.txt, 24_lunch_specials.txt,
# 28_seasonal_menus.txt, 40_non_alcoholic_beverages.txt
# ---------------------------------------------------------------------------

MENU: dict[str, list[dict]] = {

    # -----------------------------------------------------------------------
    # STARTERS / APPETIZERS (01_appetizers_menu.txt)
    # Price range: $8–$14 | Shareable 2–3 persons
    # -----------------------------------------------------------------------
    "starters": [
        # Cold Appetizers
        {
            "name":         "Carpaccio di Manzo",
            "price":        12.00,
            "description":  "Thinly sliced raw beef with olive oil, lemon, capers, fresh parmesan, arugula, and seasonal greens",
            "calories":     240,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "None",
        },
        {
            "name":         "Camarones al Limone",
            "price":        13.00,
            "description":  "Chilled shrimp marinated in fresh lemon juice, olive oil, garlic, and Italian herbs. Served with citrus segments and crispy crackers",
            "calories":     185,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Shellfish",
        },
        {
            "name":         "Burrata and Heirloom Tomatoes",
            "price":        14.00,
            "description":  "Creamy burrata from Puglia with fresh heirloom tomatoes, basil oil, and aged balsamic reduction",
            "calories":     None,
            "vegetarian":   True,
            "gluten_free":  True,
            "allergens":    "Dairy",
        },
        {
            "name":         "Marinated Olives Selection",
            "price":        8.00,
            "description":  "Curated selection of green and black Italian olives marinated with herbs, citrus, and garlic",
            "calories":     None,
            "vegetarian":   True,
            "gluten_free":  True,
            "allergens":    "None",
        },
        {
            "name":         "Prosciutto di Parma",
            "price":        12.00,
            "description":  "Premium imported prosciutto served with cantaloupe and fresh figs. Available with grissini breadsticks",
            "calories":     200,
            "vegetarian":   False,
            "gluten_free":  True,   # without breadsticks
            "allergens":    "Gluten (breadsticks optional)",
        },
        # Warm Appetizers
        {
            "name":         "Calamari Fritti",
            "price":        13.00,
            "description":  "Tender squid lightly breaded and fried until golden, served with lemon wedges and homemade marinara sauce",
            "calories":     320,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Shellfish, Gluten",
        },
        {
            "name":         "Arancini Siciliani",
            "price":        11.00,
            "description":  "Golden-fried risotto balls filled with ragù, mozzarella, and peas. Crispy exterior with creamy center",
            "calories":     280,
            "vegetarian":   True,
            "gluten_free":  False,
            "allergens":    "Dairy, Gluten",
        },
        {
            "name":         "Bruschetta al Pomodoro",
            "price":        9.00,
            "description":  "Toasted ciabatta with fresh tomatoes, garlic, basil, and extra virgin olive oil",
            "calories":     180,
            "vegetarian":   True,
            "gluten_free":  False,
            "allergens":    "Gluten",
        },
        {
            "name":         "Mushroom Pappardelle Crostini",
            "price":        10.00,
            "description":  "Wide ribbon pasta on toasted bread with sautéed mushrooms, truffle oil, and microgreens. Gluten-free available on request",
            "calories":     220,
            "vegetarian":   True,
            "gluten_free":  False,  # available on request
            "allergens":    "Gluten",
        },
        {
            "name":         "Melanzane alla Parmigiana",
            "price":        11.00,
            "description":  "Roasted eggplant layered with fresh mozzarella, basil, and marinara sauce, baked until golden",
            "calories":     310,
            "vegetarian":   True,
            "gluten_free":  False,
            "allergens":    "Dairy, Gluten",
        },
        {
            "name":         "Scallops al Forno",
            "price":        14.00,
            "description":  "Pan-seared diver scallops with garlic, white wine, and fresh herbs. Finished with brown butter",
            "calories":     240,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "Shellfish, Dairy",
        },
    ],

    # -----------------------------------------------------------------------
    # PASTA (02_pasta_dishes.txt)
    # All pasta made fresh in-house daily. GF pasta +$3.
    # -----------------------------------------------------------------------
    "pasta": [
        # Classic
        {
            "name":         "Tagliatelle al Ragù Bolognese",
            "price":        20.00,
            "description":  "Fresh egg pasta with signature meat ragù simmered 4 hours with San Marzano tomatoes. Traditional Emilia-Romagna recipe",
            "calories":     580,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Egg, Gluten",
        },
        {
            "name":         "Spaghetti ai Frutti di Mare",
            "price":        22.00,
            "description":  "Fresh spaghetti with clams, mussels, shrimp, and squid in a light white wine and tomato sauce, finished with fresh parsley",
            "calories":     420,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Shellfish, Gluten",
        },
        {
            "name":         "Fettuccine Alfredo",
            "price":        18.00,
            "description":  "Ribbon pasta in a rich cream sauce made with butter, Pecorino Romano, and fresh cracked black pepper",
            "calories":     520,
            "vegetarian":   True,
            "gluten_free":  False,
            "allergens":    "Dairy, Gluten",
        },
        {
            "name":         "Pappardelle al Cinghiale",
            "price":        22.00,
            "description":  "Wide pappardelle ribbons with wild boar ragù, rosemary, and Chianti wine reduction. A Tuscan specialty",
            "calories":     550,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Gluten",
        },
        {
            "name":         "Linguine alle Vongole",
            "price":        20.00,
            "description":  "Linguine with Manila clams in a garlic, white wine, and parsley sauce. A Roman classic",
            "calories":     380,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Shellfish, Gluten",
        },
        {
            "name":         "Rigatoni alla Matriciana",
            "price":        17.00,
            "description":  "Robust pasta tubes with guanciale (cured pork jowl), tomatoes, Pecorino Romano, and a touch of chili",
            "calories":     480,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Gluten, Dairy",
        },
        {
            "name":         "Lasagna della Nonna",
            "price":        19.00,
            "description":  "Traditional lasagna with béchamel, Bolognese ragù, and ricotta layered with fresh pasta sheets. Vegetarian option available",
            "calories":     620,
            "vegetarian":   False,  # vegetarian version available on request
            "gluten_free":  False,
            "allergens":    "Dairy, Egg, Gluten",
        },
        # Lighter Options
        {
            "name":         "Spaghetti al Pomodoro",
            "price":        14.00,
            "description":  "San Marzano tomatoes, fresh basil, garlic, and extra virgin olive oil. Simple perfection. Vegan option available",
            "calories":     320,
            "vegetarian":   True,
            "gluten_free":  False,
            "allergens":    "Gluten",
            "vegan":        True,
        },
        {
            "name":         "Orzo Risotto with Mushrooms and Truffle",
            "price":        17.00,
            "description":  "Rice-shaped pasta prepared risotto-style with porcini mushrooms, black truffle oil, and Parmesan. Earthy and indulgent",
            "calories":     420,
            "vegetarian":   True,
            "gluten_free":  False,
            "allergens":    "Gluten, Dairy",
        },
        {
            "name":         "Penne all'Arrabbiata",
            "price":        15.00,
            "description":  "Quill pasta with San Marzano tomatoes, garlic, and red chilli pepper. Bold Roman classic. Vegan option available",
            "calories":     340,
            "vegetarian":   True,
            "gluten_free":  False,
            "allergens":    "Gluten",
            "vegan":        True,
        },
        # Seafood Pasta
        {
            "name":         "Lobster Ravioli",
            "price":        28.00,
            "description":  "Large handmade ravioli filled with sweet lobster, ricotta, and herbs, in a light saffron cream sauce. Garnished with lobster roe",
            "calories":     520,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Shellfish, Dairy, Egg, Gluten",
        },
        {
            "name":         "Swordfish Pasta",
            "price":        24.00,
            "description":  "Fresh swordfish with capers, olives, and cherry tomatoes in a light lemon sauce, served over fettuccine",
            "calories":     450,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Fish, Gluten",
        },
    ],

    # -----------------------------------------------------------------------
    # SEAFOOD (03_seafood_specialties.txt)
    # -----------------------------------------------------------------------
    "seafood": [
        # Grilled
        {
            "name":         "Branzino al Forno",
            "price":        28.00,
            "description":  "Mediterranean sea bass grilled whole with fresh lemon, olive oil, and herbs. Served with seasonal vegetables and roasted potatoes",
            "calories":     420,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "Fish",
        },
        {
            "name":         "Dorado con Salsa di Limone",
            "price":        26.00,
            "description":  "Fresh dorado fillet pan-seared and finished with a silky lemon butter sauce. Accompanied by sautéed spinach and risotto",
            "calories":     450,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "Fish, Dairy",
        },
        {
            "name":         "Salmone al Pesto Siciliano",
            "price":        27.00,
            "description":  "Wild-caught salmon grilled and topped with house-made Sicilian pesto (almonds, basil, garlic). Served with roasted stone fruits",
            "calories":     480,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "Fish, Nuts",
        },
        # Shellfish
        {
            "name":         "Gamberi Giganti Sfoglia",
            "price":        29.00,
            "description":  "Jumbo prawns sautéed with white wine, garlic, fresh herbs, and a touch of cream. Served with saffron risotto",
            "calories":     400,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "Shellfish, Dairy",
        },
        {
            "name":         "Calamari Ripieno",
            "price":        24.00,
            "description":  "Whole squid stuffed with breadcrumbs, herbs, pine nuts, and local seafood, baked with tomato sauce. Italian coastal specialty",
            "calories":     380,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Shellfish, Gluten, Nuts",
        },
        {
            "name":         "Capesante al Tartufo",
            "price":        32.00,
            "description":  "Diver scallops pan-seared with black truffle, white wine, and garlic butter. Served with creamy polenta",
            "calories":     420,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "Shellfish, Dairy",
        },
        {
            "name":         "Cozze alla Marinara",
            "price":        18.00,
            "description":  "Fresh mussels steamed in white wine, garlic, and fresh herbs. Served with ciabatta. Can be prepared spicy on request",
            "calories":     280,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Shellfish, Gluten",
        },
        # Surf and Turf
        {
            "name":         "Branzino con Pancetta",
            "price":        30.00,
            "description":  "Mediterranean sea bass with crispy pancetta, braised cannellini beans, and wilted greens. Gluten-free available",
            "calories":     490,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Fish, Gluten",
        },
        {
            "name":         "Lobster Alla Vodka",
            "price":        38.00,
            "description":  "Fresh lobster tail in a vodka-tomato cream sauce with fresh herbs. Over your choice of pasta or risotto",
            "calories":     520,
            "vegetarian":   False,
            "gluten_free":  False,  # depends on side
            "allergens":    "Shellfish, Dairy",
        },
    ],

    # -----------------------------------------------------------------------
    # MAINS (04_main_courses.txt)
    # -----------------------------------------------------------------------
    "mains": [
        # Meat
        {
            "name":         "Osso Buco alla Milanese",
            "price":        34.00,
            "description":  "Braised veal shanks slow-cooked with white wine, vegetables, and broth. Served with gremolata and saffron risotto. A Milanese classic",
            "calories":     650,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "Dairy",
        },
        {
            "name":         "Saltimbocca di Vitello",
            "price":        28.00,
            "description":  "Thin veal cutlets layered with prosciutto and fresh sage, pan-seared and finished with white wine and herbs. Served with seasonal vegetables",
            "calories":     480,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "None",
        },
        {
            "name":         "Costolette di Agnello alla Griglia",
            "price":        32.00,
            "description":  "Lamb chops grilled with rosemary, garlic, and lemon. Served with roasted potatoes and seasonal greens",
            "calories":     560,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "None",
        },
        {
            "name":         "Pollo alla Parmigiana",
            "price":        24.00,
            "description":  "Breaded chicken breast layered with fresh mozzarella, tomato sauce, and Parmesan, baked until golden. Served with pasta or salad",
            "calories":     520,
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Gluten, Dairy",
        },
        {
            "name":         "Branzata di Manzo",
            "price":        30.00,
            "description":  "Slow-braised beef brisket in Barolo wine with carrots, celery, and onions. Served with creamy polenta and braised greens",
            "calories":     620,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "Dairy",
        },
        # Poultry
        {
            "name":         "Chicken Piccata",
            "price":        22.00,
            "description":  "Tender chicken breast with capers, fresh lemon, and white wine sauce. Light and bright. Served with your choice of sides",
            "calories":     420,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "None",
        },
        {
            "name":         "Duck Confit alla Toscana",
            "price":        28.00,
            "description":  "Honey and herb-glazed duck leg confit served with cannellini beans and bitter greens. Rich and satisfying",
            "calories":     540,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "None",
        },
        # Large Portions / Mixed Grill
        {
            "name":         "Grigliata Mista",
            "price":        38.00,
            "description":  "Selection of grilled meats: veal chop, lamb chop, sausage, chicken, and seafood. Served with roasted vegetables. For 2+ persons",
            "calories":     680,   # per person
            "vegetarian":   False,
            "gluten_free":  False,
            "allergens":    "Varies",
            "note":         "Serves 2–4 persons",
        },
        {
            "name":         "Bollito Misto",
            "price":        34.00,
            "description":  "Traditional mixed boiled meats with seasonal vegetables, broth, and salsa verde. Festive and hearty. Pre-order recommended",
            "calories":     550,
            "vegetarian":   False,
            "gluten_free":  True,
            "allergens":    "None",
            "note":         "For 2–4 persons. Pre-order recommended",
        },
        # Vegetarian Mains
        {
            "name":         "Eggplant Parmesan (Full Entrée)",
            "price":        20.00,
            "description":  "Full portion baked eggplant with fresh mozzarella, basil, and tomato sauce, baked golden. Gluten-free substitute available",
            "calories":     420,
            "vegetarian":   True,
            "gluten_free":  False,
            "allergens":    "Dairy, Gluten",
        },
        {
            "name":         "Wild Mushroom Wellington",
            "price":        22.00,
            "description":  "Roasted portobello and seasonal mushrooms wrapped in puff pastry with herb and nut filling. Served with mushroom cream sauce",
            "calories":     480,
            "vegetarian":   True,
            "gluten_free":  False,
            "allergens":    "Gluten, Dairy, Nuts",
        },
    ],

    # -----------------------------------------------------------------------
    # DESSERTS (05_desserts_menu.txt)
    # -----------------------------------------------------------------------
    "desserts": [
        # Traditional Italian
        {
            "name":         "Tiramisu",
            "price":        9.00,
            "description":  "Classic layers of espresso-dipped ladyfingers with mascarpone cream, cocoa powder, and a touch of liqueur",
            "calories":     420,
            "vegetarian":   True,
            "gluten_free":  False,
            "allergens":    "Dairy, Eggs, Gluten, Coffee",
        },
        {
            "name":         "Panna Cotta",
            "price":        8.00,
            "description":  "Silky smooth Italian cream custard served with berry compote and fresh mint. Light and elegant",
            "calories":     340,
            "vegetarian":   True,
            "gluten_free":  True,
            "allergens":    "Dairy",
        },
        {
            "name":         "Zabaglione con Frutti di Bosco",
            "price":        9.00,
            "description":  "Light Italian custard made with egg yolks, sugar, and Marsala wine, topped with fresh berries. Served chilled",
            "calories":     280,
            "vegetarian":   True,
            "gluten_free":  True,
            "allergens":    "Dairy, Eggs, Alcohol",
        },
        {
            "name":         "Panna Cotta al Pistachio",
            "price":        9.00,
            "description":  "Silky pistachio-infused cream custard with crushed pistachios and pistachio sauce. Nutty and luxurious",
            "calories":     380,
            "vegetarian":   True,
            "gluten_free":  True,
            "allergens":    "Dairy, Nuts",
        },
        {
            "name":         "Amaretti",
            "price":        5.00,
            "description":  "Traditional almond cookies from Saronno — delicately crispy outside, soft inside. Served with dessert wine or coffee",
            "calories":     120,   # per cookie
            "vegetarian":   True,
            "gluten_free":  True,
            "allergens":    "Nuts, Eggs",
        },
        {
            "name":         "Biscotti di Prato",
            "price":        5.00,
            "description":  "Hard almond biscotti, perfect for dunking in vin santo or coffee. Traditionally paired with Italian sweet wines",
            "calories":     140,   # per cookie
            "vegetarian":   True,
            "gluten_free":  False,
            "allergens":    "Nuts, Eggs, Gluten",
        },
        # Chocolate
        {
            "name":         "Flourless Chocolate Cake",
            "price":        9.00,
            "description":  "Rich, dense chocolate cake without flour, topped with whipped cream and fresh raspberries. Intensely chocolatey",
            "calories":     480,
            "vegetarian":   True,
            "gluten_free":  True,
            "allergens":    "Dairy, Eggs",
        },
        {
            "name":         "Chocolate Mousse Tart",
            "price":        9.00,
            "description":  "Light chocolate mousse in a crispy tart shell, topped with ganache and fresh berries",
            "calories":     420,
            "vegetarian":   True,
            "gluten_free":  False,
            "allergens":    "Dairy, Eggs, Gluten",
        },
        # Fruit & Lighter
        {
            "name":         "Grilled Peaches with Mascarpone",
            "price":        8.00,
            "description":  "Fresh peaches grilled and served warm with creamy mascarpone, honey drizzle, and mint. Seasonal availability",
            "calories":     280,
            "vegetarian":   True,
            "gluten_free":  True,
            "allergens":    "Dairy",
        },
        {
            "name":         "Mixed Berry Sorbet",
            "price":        6.00,
            "description":  "Refreshing dairy-free sorbet made from fresh berries. Perfect palate cleanser",
            "calories":     220,
            "vegetarian":   True,
            "gluten_free":  True,
            "allergens":    "None",
            "vegan":        True,
        },
        {
            "name":         "Italian Gelato Selection",
            "price":        6.00,
            "description":  "Rotating premium gelatos made in-house — typically pistachio, hazelnut, stracciatella, and seasonal fruits",
            "calories":     230,
            "vegetarian":   True,
            "gluten_free":  True,
            "allergens":    "Dairy",
        },
        {
            "name":         "Affogato al Caffè",
            "price":        8.00,
            "description":  "Single scoop of vanilla gelato with hot espresso poured over — a warm-cold dessert-beverage contrast",
            "calories":     180,
            "vegetarian":   True,
            "gluten_free":  True,
            "allergens":    "Dairy, Coffee",
        },
    ],

    # -----------------------------------------------------------------------
    # WINES (06_wine_list.txt)
    # -----------------------------------------------------------------------
    "wines": [
        # Red Wines
        {"name": "Barolo Riserva 2016",                  "price": 68.00, "description": "Traditional Piedmont nebbiolo. Bold, structured, and elegant",                        "region": "Piedmont"},
        {"name": "Barbaresco 2017",                      "price": 52.00, "description": "Similar to Barolo but slightly lighter. Complex and approachable",                     "region": "Piedmont"},
        {"name": "Barbera d'Alba 2018",                  "price": 36.00, "description": "Softer red with natural acidity. Food-friendly and versatile",                         "region": "Piedmont"},
        {"name": "Brunello di Montalcino 2014",          "price": 78.00, "description": "Prestigious Siena wine. Intense, long-aging, and exceptional",                         "region": "Tuscany"},
        {"name": "Vino Nobile di Montepulciano 2016",    "price": 48.00, "description": "Structured wine with cherry flavors and earthy notes",                                 "region": "Tuscany"},
        {"name": "Chianti Classico Riserva 2016",        "price": 44.00, "description": "Classic Tuscan blend, approachable yet sophisticated",                                  "region": "Tuscany"},
        {"name": "Chianti Classico 2018",                "price": 28.00, "description": "Everyday Tuscan red. Bright and food-friendly",                                        "region": "Tuscany"},
        {"name": "Nero d'Avola 2017",                    "price": 32.00, "description": "Sicilian warm-climate wine with dark fruit and spice",                                 "region": "Sicily"},
        {"name": "Aglianico del Vulcano 2015",           "price": 40.00, "description": "Volcanic soil imparts minerality and depth. From Campania",                            "region": "Campania"},
        # White Wines
        {"name": "Gavi di Gavi 2019",                    "price": 38.00, "description": "Delicate and crisp. Perfect with lighter dishes",                                      "region": "Piedmont"},
        {"name": "Vermentino di Sardegna 2019",          "price": 26.00, "description": "Bright and fresh. Excellent with seafood",                                             "region": "Sardinia"},
        {"name": "Greco di Tufo 2018",                   "price": 34.00, "description": "Stone fruit and herbal notes. Complex Campanian white",                                "region": "Campania"},
        {"name": "Albariño 2019",                        "price": 30.00, "description": "Spanish seafood-friendly alternative. Crisp acidity",                                  "region": "Spain"},
        {"name": "Pinot Grigio (Friuli) 2019",           "price": 24.00, "description": "Approachable with citrus and green apple notes",                                       "region": "Friuli"},
        # Sparkling
        {"name": "Prosecco di Valdobbiadene DOCG 2018",  "price": 28.00, "description": "Elegant bubbles with complexity. Superior classification",                             "region": "Veneto"},
        {"name": "Franciacorta Brut 2016",               "price": 52.00, "description": "Italy's answer to Champagne. Refined and sophisticated",                               "region": "Lombardy"},
        {"name": "Moscato d'Asti",                       "price": 22.00, "description": "Lightly sparkling, sweet, and festive. Lower alcohol",                                 "region": "Piedmont"},
        # Dessert Wines
        {"name": "Vin Santo",                            "price": 25.00, "description": "Traditional Tuscan dessert wine. Pairs perfectly with biscotti",                      "region": "Tuscany"},
        {"name": "Brachetto d'Acqui",                    "price": 26.00, "description": "Sweet and sparkling. Fruity and playful finish",                                       "region": "Piedmont"},
    ],

    # -----------------------------------------------------------------------
    # COCKTAILS & BAR (07_cocktails_beverages.txt)
    # -----------------------------------------------------------------------
    "cocktails": [
        # Classic Italian Cocktails
        {"name": "Negroni",             "price": 14.00, "description": "Campari, gin, and vermouth rosso. Garnished with orange. Italian aperitivo classic",   "abv": "28%"},
        {"name": "Americano",           "price": 12.00, "description": "Campari, vermouth rosso, and soda water. Lighter and more refreshing than a Negroni",  "abv": "12%"},
        {"name": "Aperol Spritz",       "price": 11.00, "description": "Prosecco, Aperol, and a splash of soda. The iconic Italian aperitivo",                 "abv": "11%"},
        {"name": "Bellini",             "price": 12.00, "description": "Fresh peach purée and Prosecco. A classic Venetian cocktail",                          "abv": "11%"},
        {"name": "Espresso Martini",    "price": 13.00, "description": "Vodka, Kahlua, and fresh espresso. Perfect after-dinner pick-me-up",                   "abv": "17%"},
        # House Specials
        {"name": "Il Giardiniere",      "price": 14.00, "description": "Muddled cucumber, fresh basil, white rum, lime, and agave. Refreshing herbal cocktail", "abv": "16%"},
        {"name": "Limoncello Dream",    "price": 13.00, "description": "Limoncello, vodka, fresh lemon juice, and simple syrup. Bright and citrusy",             "abv": "22%"},
        {"name": "Tuscan Sunset",       "price": 14.00, "description": "Amaretto, orange liqueur, cranberry juice, and Prosecco. Beautiful color, balanced sweetness", "abv": "15%"},
        {"name": "Mediterranean Mule",  "price": 12.00, "description": "Italian gin, fresh lime, ginger beer, and fresh herbs. A twist on the classic mule",    "abv": "16%"},
        # Mocktails
        {"name": "Virgin Aperol Spritz",     "price": 9.00,  "description": "Prosecco-style soda with citrus flavours. All the refreshment, none of the alcohol", "abv": "0%"},
        {"name": "Fresh Lemonade",           "price": 5.00,  "description": "House-made with fresh lemons and natural sweetness",                                 "abv": "0%"},
        {"name": "Virgin Limoncello Dream",  "price": 9.00,  "description": "Limoncello syrup, fresh lemon juice, and sparkling water. Bright and refreshing",   "abv": "0%"},
        # After-Dinner
        {"name": "Fernet Branca",   "price": 6.00,  "description": "Complex and digestive Italian amaro",      "abv": "39%"},
        {"name": "Nonino",          "price": 8.00,  "description": "Barolo-aged amaro. Complex and refined",   "abv": "35%"},
        {"name": "Montenegro",      "price": 6.00,  "description": "Smooth and approachable amaro",            "abv": "23%"},
        {"name": "Limoncello",      "price": 5.00,  "description": "Chilled Italian lemon liqueur",            "abv": "26%"},
        {"name": "Sambuca",         "price": 5.00,  "description": "Anise-flavoured spirit, traditionally flamed and served with coffee", "abv": "38%"},
    ],

    # -----------------------------------------------------------------------
    # NON-ALCOHOLIC BEVERAGES (07_cocktails_beverages.txt + 40_non_alcoholic_beverages.txt)
    # -----------------------------------------------------------------------
    "non_alcoholic": [
        # Coffee
        {"name": "Espresso",        "price": 3.50,  "description": "Single or double shot. Dark roast, full-bodied, with crema. Sipped immediately while hot"},
        {"name": "Americano",       "price": 4.00,  "description": "Espresso with hot water. Smooth, milder strength, similar to drip coffee"},
        {"name": "Cappuccino",      "price": 5.00,  "description": "Espresso with equal parts steamed milk and foam. Often enjoyed morning or midday"},
        {"name": "Latte",           "price": 5.00,  "description": "Espresso with abundant steamed milk. Creamier than cappuccino, smooth and velvety"},
        {"name": "Macchiato",       "price": 4.00,  "description": "Espresso 'marked' with a small amount of foam. Espresso-forward, quick afternoon pick-me-up"},
        {"name": "Affogato",        "price": 8.00,  "description": "Vanilla gelato with hot espresso poured over. Dessert and beverage combined"},
        # Teas
        {"name": "Chamomile Tea",   "price": 4.00,  "description": "Calming and soothing. Evening beverage with digestive benefits"},
        {"name": "Mint Tea",        "price": 4.00,  "description": "Refreshing and cooling. Naturally sweet with digestive benefits"},
        {"name": "Lemon Tea",       "price": 4.00,  "description": "Bright citrus flavour. Cleansing with Vitamin C boost"},
        {"name": "Ginger Tea",      "price": 4.00,  "description": "Warming and spicy. Digestive and immune support properties"},
        # Water & Soft Drinks
        {"name": "San Pellegrino (Sparkling)", "price": 3.50, "description": "Iconic Italian sparkling mineral water. Crisp and refreshing"},
        {"name": "San Benedetto (Still)",      "price": 3.00, "description": "Italian still mineral water. Clean and pure taste"},
        {"name": "Fresh Juice",                "price": 5.50, "description": "Orange, lemon, apple, or cranberry. Fresh pressed when available"},
        {"name": "Italian Soda",               "price": 5.00, "description": "Flavoured syrup with soda water. Bright, refreshing, lower sugar"},
        {"name": "Hot Chocolate",              "price": 5.00, "description": "Rich, thick Italian-style hot chocolate (Cioccolata Calda). Whipped cream optional"},
    ],

    # -----------------------------------------------------------------------
    # LUNCH SPECIALS (24_lunch_specials.txt)
    # Available: 12:00 PM – 3:30 PM daily
    # -----------------------------------------------------------------------
    "lunch_specials": [
        {
            "name":        "Light Lunch Prix Fixe",
            "price":       18.00,
            "description": "Appetizer + pasta dish + beverage. Selection from the light menu. Perfect for a quick lunch",
            "vegetarian":  False,
            "gluten_free": False,
            "note":        "Available 12:00 PM – 3:30 PM daily",
        },
        {
            "name":        "Classic Lunch Prix Fixe",
            "price":       22.00,
            "description": "Appetizer + main course + dessert or beverage. Full menu selection available",
            "vegetarian":  False,
            "gluten_free": False,
            "note":        "Available 12:00 PM – 3:30 PM daily",
        },
        {
            "name":        "Business Lunch",
            "price":       16.00,
            "description": "Sandwich or light entrée + side + beverage. Quick 45-60 minute turnaround. WiFi available",
            "vegetarian":  False,
            "gluten_free": False,
            "note":        "Mon–Thu 10% extra discount. Available 12:00 PM – 3:30 PM",
        },
        {
            "name":        "Prosciutto Panini",
            "price":       12.00,
            "description": "Prosciutto, mozzarella, tomato, and basil aioli. Pressed and warm",
            "vegetarian":  False,
            "gluten_free": False,
        },
        {
            "name":        "Grilled Chicken Sandwich",
            "price":       11.00,
            "description": "Herb-marinated chicken with arugula and roasted peppers",
            "vegetarian":  False,
            "gluten_free": False,
        },
        {
            "name":        "Caprese Panini",
            "price":       10.00,
            "description": "Tomato, mozzarella, basil, and balsamic. Vegetarian option",
            "vegetarian":  True,
            "gluten_free": False,
        },
    ],

    # -----------------------------------------------------------------------
    # SEASONAL SPECIALS (28_seasonal_menus.txt)
    # -----------------------------------------------------------------------
    "seasonal": [
        # Spring (March–May)
        {"name": "Asparagus Risotto",            "price": 18.00, "description": "Creamy risotto with fresh asparagus and Parmesan. Spring special",              "season": "Spring", "vegetarian": True},
        {"name": "Pappardelle con Piselli",       "price": 16.00, "description": "Wide pasta with spring peas and cream sauce. Spring special",                  "season": "Spring", "vegetarian": True},
        {"name": "Spring Lamb Preparations",      "price": 28.00, "description": "Tender lamb with spring vegetables and herbs. Spring special",                 "season": "Spring", "vegetarian": False},
        # Summer (June–August)
        {"name": "Grilled Peaches with Burrata",  "price": 16.00, "description": "Sweet grilled peaches with creamy burrata cheese. Summer special",             "season": "Summer", "vegetarian": True},
        {"name": "Gazpacho",                      "price": 8.00,  "description": "Chilled tomato soup with Mediterranean herbs. Summer special",                 "season": "Summer", "vegetarian": True},
        {"name": "Limoncello Desserts",           "price": 8.00,  "description": "Lemon-forward sweet preparations. Summer special",                             "season": "Summer", "vegetarian": True},
        # Autumn (September–November)
        {"name": "Mushroom Risotto",              "price": 18.00, "description": "Porcini and seasonal mushroom risotto. Autumn special",                        "season": "Autumn", "vegetarian": True},
        {"name": "Game Birds",                    "price": 26.00, "description": "Roasted pheasant or quail with seasonal accompaniments. Autumn special",        "season": "Autumn", "vegetarian": False},
        {"name": "Roasted Root Vegetables",       "price": 12.00, "description": "Seasonal squash and root vegetable preparations. Autumn special",               "season": "Autumn", "vegetarian": True},
        # Winter (December–February)
        {"name": "Osso Buco (Winter Special)",    "price": 32.00, "description": "Braised veal shanks featured all winter. Warming and hearty",                  "season": "Winter", "vegetarian": False},
        {"name": "Risotto Variations",            "price": 18.00, "description": "Multiple creamy rice dishes rotating through the winter menu",                 "season": "Winter", "vegetarian": True},
        {"name": "Christmas Panettone",           "price": 8.00,  "description": "Traditional holiday cake with dried fruits, candied citrus, and raisins. December only", "season": "Winter", "vegetarian": True},
    ],

    # -----------------------------------------------------------------------
    # SIDES (03_seafood_specialties.txt + 04_main_courses.txt)
    # -----------------------------------------------------------------------
    "sides": [
        {"name": "Sautéed Seasonal Vegetables",            "price": 6.00,  "description": "Fresh daily vegetables — zucchini, eggplant, bell peppers, asparagus",   "vegetarian": True, "gluten_free": True,  "calories": 120},
        {"name": "Roasted Fingerling Potatoes",            "price": 6.00,  "description": "Crispy potatoes with extra virgin olive oil and fresh rosemary",          "vegetarian": True, "gluten_free": True,  "calories": 180},
        {"name": "Saffron Risotto",                        "price": 8.00,  "description": "Creamy Arborio rice with saffron, white wine, butter, and Parmesan",     "vegetarian": True, "gluten_free": True,  "calories": 340},
        {"name": "Creamy Polenta",                         "price": 7.00,  "description": "Cornmeal cooked with butter, cream, and Parmesan until silky smooth",    "vegetarian": True, "gluten_free": True,  "calories": 280},
        {"name": "Cannellini Beans and Greens",            "price": 6.00,  "description": "Braised white beans with wilted greens and olive oil",                    "vegetarian": True, "gluten_free": True,  "calories": 200},
        {"name": "Pasta al Burro",                         "price": 5.00,  "description": "Simple buttered pasta. Light accompaniment",                              "vegetarian": True, "gluten_free": False, "calories": 280},
    ],
}

# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------
TOOL_SCHEMA = {
    "name":        "search_menu",
    "description": "Search La Bella Tavola's full menu by category and/or dietary preference. Returns items with name, price, description, and allergen info.",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {
                "type":        "string",
                "enum":        ["starters", "pasta", "seafood", "mains", "desserts",
                                "wines", "cocktails", "non_alcoholic", "lunch_specials",
                                "seasonal", "sides", ""],
                "description": "Menu section to return. Empty string returns all sections."
            },
            "dietary": {
                "type":        "string",
                "enum":        ["vegetarian", "vegan", "gluten_free", ""],
                "description": "Filter by dietary requirement. Empty string returns everything."
            }
        },
        "required": []
    }
}


# ---------------------------------------------------------------------------
# Category aliases — maps natural language terms to canonical keys
# ---------------------------------------------------------------------------
_CATEGORY_ALIASES: dict[str, str] = {
    # starters
    "appetizer":     "starters", "appetizers":    "starters",
    "antipasto":     "starters", "antipasti":     "starters",
    "starter":       "starters",
    # pasta
    "risotto":       "pasta",    "noodles":       "pasta",
    # seafood
    "fish":          "seafood",  "shellfish":     "seafood",
    "seafood":       "seafood",
    # mains
    "main":          "mains",    "entree":        "mains",
    "entrees":       "mains",    "meat":          "mains",
    "chicken":       "mains",    "lamb":          "mains",
    "beef":          "mains",    "veal":          "mains",
    # desserts
    "dessert":       "desserts", "sweet":         "desserts",
    "sweets":        "desserts", "gelato":        "desserts",
    # wines
    "wine":          "wines",    "vino":          "wines",
    "red wine":      "wines",    "white wine":    "wines",
    "sparkling":     "wines",    "prosecco":      "wines",
    # cocktails
    "cocktail":      "cocktails","drinks":        "cocktails",
    "drink":         "cocktails","bar":           "cocktails",
    "mocktail":      "cocktails","mocktails":     "cocktails",
    "beer":          "cocktails","beers":         "cocktails",
    # non-alcoholic
    "coffee":        "non_alcoholic", "tea":      "non_alcoholic",
    "juice":         "non_alcoholic", "water":    "non_alcoholic",
    "non alcoholic": "non_alcoholic", "nonalcoholic": "non_alcoholic",
    "soft drink":    "non_alcoholic", "beverage": "non_alcoholic",
    "beverages":     "non_alcoholic", "espresso": "non_alcoholic",
    "cappuccino":    "non_alcoholic", "latte":    "non_alcoholic",
    # lunch
    "lunch":         "lunch_specials", "lunch special": "lunch_specials",
    # seasonal
    "season":        "seasonal",  "specials":    "seasonal",
    "special":       "seasonal",  "today":       "seasonal",
    # sides
    "side":          "sides",     "side dish":   "sides",
    "side dishes":   "sides",     "accompaniment": "sides",
}


# ---------------------------------------------------------------------------
# Public API — logic unchanged from original
# ---------------------------------------------------------------------------

def search_menu(category: str = "", dietary: str = "") -> dict:
    """
    Returns menu items matching *category* and/or *dietary* filter.
    Always returns a dict with 'status': 'ok' or 'status': 'error'.
    """
    try:
        # --- Select categories -------------------------------------------
        if category:
            cat_key = category.lower().strip()
            # 1. Check alias map first
            resolved = _CATEGORY_ALIASES.get(cat_key, cat_key)
            # 2. Exact match on resolved key
            if resolved in MENU:
                working = {resolved: MENU[resolved]}
                note    = ""
            else:
                # 3. Fuzzy substring match as fallback
                matched = {k: v for k, v in MENU.items() if resolved in k or k in resolved}
                if matched:
                    working = matched
                    note    = ""
                else:
                    working = dict(MENU)
                    note    = f"Category '{category}' not found — returning full menu."
        else:
            working = dict(MENU)
            note    = ""

        # --- Apply dietary filter ----------------------------------------
        if dietary:
            diet = dietary.lower().strip()
            filtered: dict[str, list] = {}

            for cat, items in working.items():
                if diet == "vegetarian":
                    keep = [i for i in items if i.get("vegetarian", False)]
                elif diet == "vegan":
                    keep = [i for i in items if i.get("vegan", False)]
                elif diet in ("gluten_free", "gluten-free"):
                    keep = [i for i in items if i.get("gluten_free", False)]
                else:
                    keep = list(items)

                if keep:
                    filtered[cat] = keep
            working = filtered

        return {"status": "ok", "results": working, **({"note": note} if note else {})}

    except Exception as e:
        logger.error(f"[MENU] Unexpected error: {e}")
        return {"status": "error", "message": "Menu lookup failed. Please ask your server."}