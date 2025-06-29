from sqlalchemy.orm import sessionmaker
from create_db import Base, Recipe, Ingredient, RecipeIngredient
from sqlalchemy import create_engine

# Connect to DB
engine = create_engine('sqlite:///shopping_list.db')
Session = sessionmaker(bind=engine)
session = Session()

# Utility: Get or create ingredient
def get_or_create_ingredient(name, unit):
    ingredient = session.query(Ingredient).filter_by(name=name).first()
    if not ingredient:
        ingredient = Ingredient(name=name, unit=unit)
        session.add(ingredient)
        session.flush()  # ensures the ingredient gets an ID before using
    return ingredient

# Create new recipe
recipe = Recipe(
    name="Broccoli Basil Pasta",
    description="Pasta with broccoli, basil pesto, and Parmesan."
)
session.add(recipe)
session.flush()

# Ingredients data (name, quantity, unit)
ingredients_data = [
    ("broccoli florets", 4, "cups"),
    ("pasta", 1, "pound"),
    ("basil leaves", 2, "cups"),
    ("garlic cloves", 2, "cloves"),
    ("pine nuts", 0.25, "cups"),
    ("extra-virgin olive oil", 1, "cup"),
    ("sea salt", 0.5, "teaspoon"),
    ("Parmesan", 1, "cup"),
    ("red pepper flakes", None, None),  # optional, no quantity
]

# Add ingredients and recipe links
for name, qty, unit in ingredients_data:
    ingredient = get_or_create_ingredient(name, unit)
    if qty is not None:
        link = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=ingredient.id,
            quantity=qty
        )
        session.add(link)

# Commit all changes
session.commit()
print("Recipe and ingredients seeded successfully.")
