"""Словарь марок и моделей автомобилей для детекции в юридических документах.

Содержит написание на русском и латинице. Все данные статические, офлайн.
Источник: реестр ГИБДД, статистика авторынка РФ.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Марки автомобилей — кириллица + латиница + сокращения
# ---------------------------------------------------------------------------
VEHICLE_BRANDS: frozenset[str] = frozenset({
    # Российские / советские
    "Lada", "LADA", "Лада",
    "ВАЗ", "VAZ",
    "ГАЗ", "GAZ", "Газ",
    "УАЗ", "UAZ", "Уаз",
    "КАМАЗ", "Kamaz", "КамАЗ",
    "ЗИЛ", "ZIL",
    "ЗАЗ", "ZAZ",
    "Москвич", "MOSKVICH", "АЗЛК",
    "ИЖ", "Иж",
    "ПАЗ", "ЛиАЗ", "МАЗ", "КрАЗ", "НефАЗ",
    "ГАЗель", "Газель",
    "Буханка",

    # Японские
    "Toyota", "TOYOTA", "Тойота",
    "Honda", "HONDA", "Хонда",
    "Nissan", "NISSAN", "Ниссан",
    "Mazda", "MAZDA", "Мазда",
    "Mitsubishi", "MITSUBISHI", "Мицубиси", "Мицубиши",
    "Subaru", "SUBARU", "Субару",
    "Suzuki", "SUZUKI", "Сузуки",
    "Lexus", "LEXUS", "Лексус",
    "Infiniti", "INFINITI", "Инфинити",
    "Acura", "ACURA", "Акура",
    "Isuzu", "ISUZU", "Исузу",
    "Daihatsu", "DAIHATSU",
    "Datsun", "DATSUN",

    # Корейские
    "Hyundai", "HYUNDAI", "Хёндэ", "Хендай", "Хундай",
    "Kia", "KIA", "Киа",
    "SsangYong", "SSANGYONG", "СсангЙонг", "Ссанг Йонг",
    "Genesis", "GENESIS", "Генезис",
    "Daewoo", "DAEWOO", "Дэу", "Деу",
    "Chevrolet Aveo",

    # Немецкие
    "BMW", "БМВ",
    "Mercedes-Benz", "Mercedes", "MERCEDES", "Мерседес", "Мерседес-Бенц",
    "Audi", "AUDI", "Ауди",
    "Volkswagen", "VOLKSWAGEN", "Фольксваген", "ВВ", "VW",
    "Porsche", "PORSCHE", "Порше",
    "Opel", "OPEL", "Опель",

    # Французские
    "Renault", "RENAULT", "Рено",
    "Peugeot", "PEUGEOT", "Пежо",
    "Citroën", "Citroen", "CITROEN", "Ситроен",
    "Dacia", "DACIA",

    # Американские
    "Ford", "FORD", "Форд",
    "Chevrolet", "CHEVROLET", "Шевроле",
    "Jeep", "JEEP", "Джип",
    "Cadillac", "CADILLAC", "Кадиллак",
    "Dodge", "DODGE", "Додж",
    "Tesla", "TESLA", "Тесла",
    "Chrysler", "CHRYSLER", "Крайслер",
    "GMC",
    "Lincoln", "LINCOLN", "Линкольн",

    # Китайские
    "Chery", "CHERY", "Чери",
    "Haval", "HAVAL", "Хавал",
    "Geely", "GEELY", "Джили",
    "Changan", "CHANGAN", "Чанган",
    "Great Wall", "GREAT WALL", "Грейт Вол",
    "BYD",
    "Omoda", "OMODA",
    "Exeed", "EXEED",
    "Jetour", "JETOUR",
    "Tank", "TANK",
    "Hongqi", "HONGQI",
    "Dongfeng", "DONGFENG",
    "JAC",
    "FAW",
    "Foton", "FOTON",
    "Lifan", "LIFAN", "Лифан",
    "Brilliance", "BRILLIANCE",
    "BAIC",
    "Bestune", "BESTUNE",
    "Voyah", "VOYAH",
    "Li Auto", "LI AUTO",
    "Avatr", "AVATR",
    "Nio", "NIO",
    "Xpeng", "XPENG",
    "Ora", "ORA",
    "AITO",

    # Итальянские
    "Fiat", "FIAT", "Фиат",
    "Alfa Romeo", "ALFA ROMEO", "Альфа Ромео",
    "Ferrari", "FERRARI", "Феррари",
    "Lamborghini", "LAMBORGHINI", "Ламборгини",
    "Maserati", "MASERATI", "Мазерати",

    # Чешские
    "Škoda", "Skoda", "SKODA", "Шкода",

    # Шведские
    "Volvo", "VOLVO", "Вольво",

    # Британские
    "Land Rover", "LAND ROVER", "Ленд Ровер",
    "Range Rover", "RANGE ROVER", "Рэндж Ровер",
    "Jaguar", "JAGUAR", "Ягуар",
    "Mini", "MINI", "Мини",
    "Bentley", "BENTLEY", "Бентли",
    "Rolls-Royce", "Rolls Royce", "ROLLS-ROYCE", "Роллс-Ройс",
    "Aston Martin", "ASTON MARTIN",

    # Румынские
    "Дачиа",

    # Малайзийские
    "Proton", "PROTON",
    "Perodua", "PERODUA",

    # Иранские
    "Iran Khodro", "IRAN KHODRO", "Иран Ходро",
    "SAIPA",
})

# ---------------------------------------------------------------------------
# Модели автомобилей — кириллица + латиница
# ---------------------------------------------------------------------------
VEHICLE_MODELS: frozenset[str] = frozenset({
    # Toyota
    "Camry", "Камри",
    "Corolla", "Королла",
    "RAV4", "РАВ4", "РАВ 4",
    "Land Cruiser", "Land Cruiser Prado", "Ленд Крузер", "Ленд Крузер Прадо",
    "Prius", "Приус",
    "Yaris", "Ярис",
    "Highlander", "Хайлендер",
    "Fortuner", "Фортунер",
    "Hilux", "Хайлюкс",
    "Supra", "Супра",
    "Avalon", "Авалон",
    "Venza", "Венза",
    "Alphard", "Алфард",
    "Vellfire",
    "4Runner",
    "FJ Cruiser",
    "C-HR",
    "Rush",
    "Raize",
    "Veloz",

    # Honda
    "Civic", "Цивик",
    "Accord", "Аккорд",
    "CR-V", "CRV",
    "HR-V", "HRV",
    "Pilot", "Пилот",
    "Jazz",
    "Fit", "Фит",
    "Odyssey", "Одиссей",
    "Passport",
    "Ridgeline",

    # Nissan
    "Qashqai", "Кашкай",
    "X-Trail", "Икстрейл",
    "Juke", "Джук",
    "Murano", "Мурано",
    "Pathfinder", "Патфайндер",
    "Patrol", "Патруль",
    "Navara",
    "Almera", "Альмера",
    "Tiida", "Тиида",
    "Note", "Ноут",
    "Sunny",
    "Sentra",
    "Teana", "Тиана",
    "GT-R",

    # Mazda
    "CX-5", "СХ5",
    "CX-7", "CX-9",
    "CX-30",
    "Mazda 3", "Mazda3",
    "Mazda 6", "Mazda6",
    "MX-5",
    "BT-50",

    # Mitsubishi
    "Outlander", "Аутлендер",
    "Pajero", "Паджеро",
    "ASX",
    "Eclipse Cross",
    "Galant", "Галант",
    "Lancer", "Лансер",
    "Colt",
    "L200",

    # Subaru
    "Forester", "Форестер",
    "Outback", "Аутбэк",
    "Impreza", "Импреза",
    "Legacy", "Легаси",
    "XV",
    "WRX",
    "BRZ",
    "Crosstrek",

    # BMW
    "X5", "Х5",
    "X3", "Х3",
    "X6", "Х6",
    "X1", "Х1",
    "X7", "Х7",
    "520", "523", "525", "528", "530", "535",
    "320", "323", "325", "328", "330", "335",
    "520i", "523i", "525i", "528i", "530i", "535i",
    "320i", "323i", "325i", "328i", "330i", "335i",
    "730", "740", "750",
    "1 Series", "2 Series", "3 Series", "4 Series", "5 Series", "6 Series", "7 Series", "8 Series",
    "M3", "M5", "M6",
    "iX", "i3", "i4", "i7",
    "Z4",

    # Mercedes-Benz
    "C-класс", "C-Class",
    "E-класс", "E-Class",
    "S-класс", "S-Class",
    "A-класс", "A-Class",
    "B-класс", "B-Class",
    "GLC", "GLE", "GLS", "GLA", "GLB", "G-класс", "G-Class", "Гелендваген",
    "C180", "C200", "C220", "C250", "C300",
    "E200", "E220", "E250", "E300", "E350",
    "S320", "S350", "S400", "S500", "S600",
    "ML", "GL",
    "Vito", "Спринтер", "Sprinter",
    "AMG",

    # Audi
    "A3", "A4", "A5", "A6", "A7", "A8",
    "Q3", "Q5", "Q7", "Q8",
    "TT", "R8",
    "e-tron",
    "Allroad",

    # Volkswagen
    "Polo", "Поло",
    "Golf", "Гольф",
    "Passat", "Пассат",
    "Tiguan", "Тигуан",
    "Touareg", "Туарег",
    "Touran", "Туран",
    "Jetta", "Джетта",
    "Phaeton",
    "Sharan",
    "Transporter", "Транспортер",
    "Multivan",
    "Caddy",

    # Skoda
    "Octavia", "Октавия",
    "Superb", "Суперб",
    "Fabia", "Фабия",
    "Yeti", "Йети",
    "Kodiaq", "Кодиак",
    "Karoq", "Карок",
    "Rapid", "Рапид",

    # Ford
    "Focus", "Фокус",
    "Mondeo", "Мондео",
    "Kuga", "Куга",
    "Explorer", "Эксплорер",
    "F-150",
    "Ranger", "Рейнджер",
    "Transit", "Транзит",
    "Fiesta", "Фиеста",
    "Edge",
    "Escape",
    "Bronco",
    "Maverick",

    # Chevrolet
    "Cruze", "Круз",
    "Captiva", "Каптива",
    "Aveo", "Авео",
    "Lacetti", "Лачетти",
    "Cobalt", "Кобальт",
    "Equinox",
    "Traverse",
    "Silverado",
    "Colorado",
    "Tahoe",
    "Suburban",
    "Blazer",

    # Hyundai
    "Solaris", "Солярис",
    "Tucson", "Туссан",
    "Creta", "Крета",
    "Santa Fe", "Санта Фе",
    "Sonata", "Соната",
    "Elantra", "Элантра",
    "ix35",
    "Accent", "Акцент",
    "Getz", "Гетц",
    "i10", "i20", "i30", "i40",
    "Palisade",
    "Venue",
    "Kona",
    "IONIQ",

    # Kia
    "Rio", "Рио",
    "Sportage", "Спортейдж",
    "Cerato", "Серато",
    "Sorento", "Соренто",
    "Optima", "Оптима",
    "Stinger", "Стингер",
    "Soul", "Соул",
    "Picanto", "Пиканто",
    "Carnival",
    "Telluride",
    "EV6",
    "Seltos",

    # Renault
    "Logan", "Логан",
    "Sandero", "Сандеро",
    "Duster", "Дастер",
    "Kaptur", "Каптур",
    "Megane", "Меган",
    "Clio", "Клио",
    "Fluence", "Флюэнс",
    "Koleos", "Колеос",
    "Arkana", "Аркана",
    "Symbol",

    # Lada / ВАЗ
    "Granta", "Гранта",
    "Vesta", "Веста",
    "XRAY", "Иксрей",
    "Largus", "Ларгус",
    "Niva", "Нива",
    "Niva Legend", "Нива Легенд",
    "Niva Travel", "Нива Трэвел",
    "2101", "2102", "2103", "2104", "2105", "2106", "2107", "2108", "2109",
    "21099", "2110", "2111", "2112", "2113", "2114", "2115",
    "Priora", "Приора",
    "Kalina", "Калина",
    "Samara", "Самара",

    # УАЗ
    "Patriot", "Патриот",
    "Hunter", "Хантер",
    "Пикап",

    # ГАЗ
    "3110", "31105",
    "Gazelle", "Газель",
    "Volga", "Волга",
    "Next",
    "Соболь",

    # Haval
    "F7", "H6", "H9", "Jolion", "Джолион",
    "Dargo",

    # Chery
    "Tiggo", "Тигго",
    "Arrizo",
    "QQ",
    "Omoda C5",

    # Geely
    "Atlas", "Атлас",
    "Coolray", "Кулрей",
    "Tugella",
    "Monjaro",

    # Jeep
    "Wrangler", "Вранглер",
    "Cherokee", "Чероки",
    "Grand Cherokee", "Гранд Чероки",
    "Compass", "Компас",
    "Renegade",
    "Gladiator",

    # Land Rover / Range Rover
    "Defender", "Дефендер",
    "Discovery", "Дискавери",
    "Freelander", "Фрилендер",
    "Sport",
    "Evoque", "Эвок",
    "Velar",

    # Lexus
    "RX", "RX350", "RX400h",
    "LX", "LX570",
    "GX", "GX460",
    "ES", "ES350",
    "LS",
    "NX",
    "UX",

    # Infiniti
    "QX60", "QX80", "QX56",
    "FX35", "FX37", "FX50",
    "G35", "G37",
    "Q50", "Q60",

    # Peugeot
    "206", "207", "208",
    "307", "308",
    "407", "408",
    "3008", "5008",
    "2008", "4008",
    "Partner", "Партнер",
    "Expert",

    # Citroën
    "C3", "C4", "C5",
    "Berlingo", "Берлинго",
    "Jumper", "Джампер",
    "C-Crosser",

    # SsangYong
    "Rexton", "Рекстон",
    "Actyon", "Актион",
    "Kyron", "Кайрон",
    "Korando",
    "Tivoli", "Тиволи",

    # Tesla
    "Model 3", "Model S", "Model X", "Model Y",
    "Cybertruck",

    # Volvo
    "XC60", "XC90", "XC40",
    "S60", "S80", "S90",
    "V40", "V60", "V90",

    # Porsche
    "Cayenne", "Каен",
    "Macan", "Макан",
    "Panamera", "Панамера",
    "911", "Boxster",

    # Suzuki
    "Vitara", "Витара",
    "Grand Vitara", "Гранд Витара",
    "Jimny", "Джимни",
    "Swift", "Свифт",
    "SX4",
    "Liana", "Лиана",

    # Daewoo
    "Nexia", "Нексия",
    "Matiz", "Матиз",
    "Lanos", "Ланос",
    "Gentra", "Джентра",

    # BYD
    "Han", "Tang", "Song",
    "Seal", "Atto 3", "Dolphin",

    # Омода / Exeed
})

# ---------------------------------------------------------------------------
# Контекстные слова, рядом с которыми марка/модель — это ТС, а не что-то другое
# ---------------------------------------------------------------------------
VEHICLE_CONTEXT_WORDS: frozenset[str] = frozenset({
    "автомобиль", "автомобиля", "автомобилем", "автомобилю", "автомобилях",
    "машина", "машины", "машине", "машину", "машиной",
    "транспортное средство", "транспортного средства", "тс", "т/с",
    "а/м", "авто",
    "автомобильный", "автотранспортный",
    "водитель", "водителя", "водителем",
    "управлял", "управляла", "управляло",
    "госномер", "гос. номер", "регистрационный знак",
    "vin", "вин", "птс", "стс", "осаго", "каско",
    "дтп", "столкновение", "наезд",
    "ремонт", "техосмотр",
    "пассажир", "пассажира", "пассажирский",
    "грузовой", "легковой", "внедорожник",
    "мотоцикл", "прицеп", "полуприцеп",
})
