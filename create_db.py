import os
import sys

from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Table, DateTime
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

# Association Table for Many-to-Many between ShoppingLists and Recipes
shopping_list_recipes = Table(
    'shopping_list_recipes', Base.metadata,
    Column('shopping_list_id', ForeignKey('shopping_lists.id'), primary_key=True),
    Column('recipe_id', ForeignKey('recipes.id'), primary_key=True)
)

class Recipe(Base):
    __tablename__ = 'recipes'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    ingredients = relationship('RecipeIngredient', back_populates='recipe')
    shopping_lists = relationship(
        'ShoppingList',
        secondary=shopping_list_recipes,
        back_populates='recipes'
    )

class Ingredient(Base):
    __tablename__ = 'ingredients'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    unit = Column(String)

    recipes = relationship('RecipeIngredient', back_populates='ingredient')

UNIT_TO_CUPS = {
    'cups': 1,
    'tbsp': 1 / 16,  # 16 tbsp = 1 cup
    'tsp': 1 / 48,    # 48 tsp = 1 cup
    'ounces': 1 / 8,        # 8 oz = 1 cup
    'pint': 2,
    'quart': 4,
    'gallon': 16,
    'milliliter': 1 / 240,  # approx.
    'liter': 4.22675,
    'cloves': 1,
    'eggs': 1,
    'whole': 1,
    'lbs': 3.6,
    'ml': 236.588,
    # Add more as needed
}

def convert_to_cups(quantity, unit):
    factor = UNIT_TO_CUPS.get(unit.lower())
    if factor is None:
        factor = 1
    return quantity * factor if factor is not None else None

class RecipeIngredient(Base):
    __tablename__ = 'recipe_ingredients'
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey('recipes.id'))
    ingredient_id = Column(Integer, ForeignKey('ingredients.id'))
    quantity = Column(Float)

    recipe = relationship('Recipe', back_populates='ingredients')
    ingredient = relationship('Ingredient', back_populates='recipes')

    @hybrid_property
    def amount_in_cups(self):
        if self.ingredient and self.ingredient.unit:
            return convert_to_cups(self.quantity, self.ingredient.unit)
        return None

class ShoppingList(Base):
    __tablename__ = 'shopping_lists'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    recipes = relationship(
        'Recipe',
        secondary=shopping_list_recipes,
        back_populates='shopping_lists'
    )
class CabinetItem(Base):
    __tablename__ = 'cabinet_items'
    id = Column(Integer, primary_key=True)
    ingredient_id = Column(Integer, ForeignKey('ingredients.id'), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String)

    ingredient = relationship("Ingredient")

    @hybrid_property
    def amount_in_cups(self):
        if self.unit:
            return convert_to_cups(self.quantity, self.unit)
        elif self.ingredient and self.ingredient.unit:
            return convert_to_cups(self.quantity, self.ingredient.unit)
        return None


def create_database():
    # Handle PyInstaller path for bundled executable
    if getattr(sys, 'frozen', False):
        BASE_DIR = os.path.dirname(sys.executable)
    else:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    DB_PATH = os.path.join(BASE_DIR, "shopping_list.db")

    engine = create_engine(f"sqlite:///{DB_PATH}", echo=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    print(f"Database and tables created at: {DB_PATH}")

if __name__ == "__main__":
    create_database()
