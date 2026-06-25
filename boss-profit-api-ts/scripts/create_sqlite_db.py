import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "prisma" / "dev.db"

schema_sql = """
DROP TABLE IF EXISTS RecipeItem;
DROP TABLE IF EXISTS Ingredient;
DROP TABLE IF EXISTS Menu;

CREATE TABLE Menu (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  price INTEGER NOT NULL,
  createdAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Ingredient (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  unit TEXT NOT NULL,
  unitPrice REAL NOT NULL,
  createdAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE RecipeItem (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  menuId INTEGER NOT NULL,
  ingredientId INTEGER NOT NULL,
  quantity REAL NOT NULL,
  createdAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT RecipeItem_menuId_fkey FOREIGN KEY (menuId) REFERENCES Menu(id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT RecipeItem_ingredientId_fkey FOREIGN KEY (ingredientId) REFERENCES Ingredient(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE UNIQUE INDEX RecipeItem_menuId_ingredientId_key ON RecipeItem(menuId, ingredientId);
"""

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")
conn.executescript(schema_sql)
conn.commit()
conn.close()

print(f"SQLite database created: {DB_PATH}")
