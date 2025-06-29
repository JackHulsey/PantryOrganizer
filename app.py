import os

from flask import Flask, render_template, request, redirect, url_for
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, joinedload
from create_db import Base, Recipe, Ingredient, RecipeIngredient, ShoppingList, CabinetItem
import webbrowser
import threading


app = Flask(__name__)

# DB setup
engine = create_engine('sqlite:///shopping_list.db')
Session = sessionmaker(bind=engine)
session = Session()

@app.route('/', methods=['GET', 'POST'])
def index():
    recipes = session.query(Recipe).all()
    shopping_list = {}

    if request.method == 'POST':
        selected_ids = request.form.getlist('recipes')
        selected_recipes = session.query(Recipe).options(
            joinedload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient)
        ).filter(Recipe.id.in_(selected_ids)).all()

        shopping_list = generate_shopping_list(selected_recipes)

    return render_template('index.html', recipes=recipes, shopping_list=shopping_list)


def convert_from_cups_to_original_unit(quantity_cups, original_unit):
    """
    Converts a quantity in cups back to the original unit using conversion factors.
    Returns a tuple: (converted_quantity, original_unit)
    """
    # Normalize unit key
    unit = original_unit.lower()

    # Conversion factors TO cups (so we invert them to go FROM cups)
    UNIT_TO_CUPS = {
        'cups': 1,
        'tbsp': 1 / 16,  # 16 tbsp = 1 cup
        'tsp': 1 / 48,  # 48 tsp = 1 cup
        'ounces': 1 / 8,  # 8 oz = 1 cup
        'pint': 2,  # 1 pint = 2 cups
        'quart': 4,
        'gallon': 16,
        'milliliter': 1 / 240,  # ~240 mL = 1 cup
        'liter': 4.22675,
        'lbs': 1 / 1.89,  # ~1.89 lbs water = 1 cup
        'eggs': 1,  # 1 cup eggs ≈ 1 egg? treat 1:1 or handle specially
        'whole': 1,
        'cloves': 1
    }

    factor = UNIT_TO_CUPS.get(unit)

    if factor is None or factor == 0:
        return quantity_cups  # unknown unit: return as-is

    # Multiply by inverse to convert
    converted_quantity = round(quantity_cups / factor, 2)
    return converted_quantity


def generate_shopping_list(selected_recipes):
    shopping_list = {}

    # Step 1: Tally required ingredients in mL
    for recipe in selected_recipes:
        for ri in recipe.ingredients:
            name = ri.ingredient.name.lower().strip()
            unit = ri.ingredient.unit
            qty_cups = ri.amount_in_cups

            if name not in shopping_list:
                shopping_list[name] = {
                    'quantity_ml': 0,
                    'recipes': set(),
                    'display_unit': unit
                }

            shopping_list[name]['quantity_ml'] += qty_cups
            shopping_list[name]['recipes'].add(recipe.name)

    # Step 2: Subtract cabinet quantities in mL
    cabinet_items = session.query(CabinetItem).all()
    for c in cabinet_items:
        name = c.ingredient.name.lower().strip()
        qty_ml = c.amount_in_cups

        if name in shopping_list:
            shopping_list[name]['quantity_ml'] -= qty_ml

    # Step 3: Convert back to display units & filter
    final_list = {}
    for name, data in shopping_list.items():
        if data['quantity_ml'] > 0:
            unit = data['display_unit']
            final_qty = convert_from_cups_to_original_unit(data['quantity_ml'], unit)

            final_list[(name, unit)] = {
                'quantity': round(final_qty, 2),
                'recipes': sorted(data['recipes'])
            }

    return final_list

@app.route('/add', methods=['GET', 'POST'])
def add_recipe():
    if request.method == 'POST':
        name = request.form['name']
        ingredient_names = request.form.getlist('ingredient_name')
        ingredient_quantities = request.form.getlist('ingredient_quantity')
        ingredient_units = request.form.getlist('ingredient_unit')

        print("Names:", request.form.getlist('ingredient_name'))
        print("Quantities:", request.form.getlist('ingredient_quantity'))
        print("Units:", request.form.getlist('ingredient_unit'))

        recipe = Recipe(name=name)
        session.add(recipe)
        session.flush()

        for i in range(len(ingredient_names)):
            ing_name = ingredient_names[i].strip()
            if not ing_name:
                continue

            qty = float(ingredient_quantities[i]) if ingredient_quantities[i] else None
            unit = ingredient_units[i]

            # Get or create ingredient
            ingredient = session.query(Ingredient).filter_by(name=ing_name).first()
            if not ingredient:
                ingredient = Ingredient(name=ing_name, unit=unit)
                session.add(ingredient)
                session.flush()

            if qty is not None:
                link = RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ingredient.id,
                    quantity=qty
                )
                session.add(link)

        session.commit()
        return redirect(url_for('index'))

    return render_template('add_recipe.html')

@app.route('/delete/<int:recipe_id>', methods=['POST'])
def delete_recipe(recipe_id):
    recipe = session.query(Recipe).filter_by(id=recipe_id).first()
    if not recipe:
        # Optionally, flash a message or handle error
        return "Recipe not found", 404

    # Delete the recipe (and optionally its linked RecipeIngredient entries if cascade isn't set)
    session.delete(recipe)
    session.commit()

    return redirect(url_for('index'))  # or wherever you want to go after deletion

# Edit existing recipes
@app.route('/edit', methods=['GET', 'POST'])
def choose_recipe_to_edit():
    recipes = session.query(Recipe).all()
    if request.method == 'POST':
        recipe_id = int(request.form['recipe_id'])
        return redirect(url_for('edit_recipe', recipe_id=recipe_id))
    return render_template('edit_select.html', recipes=recipes)

@app.route('/edit/<int:recipe_id>', methods=['GET', 'POST'])
def edit_recipe(recipe_id):
    recipe = session.query(Recipe).filter_by(id=recipe_id).first()
    if not recipe:
        return "Recipe not found", 404

    if request.method == 'POST':
        if 'delete' in request.form:
            # Delete the recipe and its associations
            session.delete(recipe)
            session.commit()
            return redirect(url_for('index'))

        # Now we know its just an update
        recipe.name = request.form['name']

        # Clear existing links
        session.query(RecipeIngredient).filter_by(recipe_id=recipe_id).delete()

        # Read edited ingredients
        names = request.form.getlist('ingredient_name')
        quantities = request.form.getlist('ingredient_quantity')
        units = request.form.getlist('ingredient_unit')

        for name, qty, unit in zip(names, quantities, units):
            if not name.strip():
                continue

            qty = float(qty) if qty else None
            ingredient = session.query(Ingredient).filter_by(name=name).first()
            if not ingredient:
                ingredient = Ingredient(name=name, unit=unit)
                session.add(ingredient)
                session.flush()
            else:
                ingredient.unit = unit  # update unit if needed

            if qty is not None:
                link = RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ingredient.id,
                    quantity=qty
                )
                session.add(link)

        session.commit()
        return redirect(url_for('index'))

    return render_template('edit_recipe.html', recipe=recipe)

# Cabinet functions

# Unit conversions
UNIT_CONVERSIONS_TO_ML = {
    "Cups": 240,
    "Tbsp": 15,
    "Tsp": 5,
    "Ounces": 29.5735,
    "Lbs": 453.592,  # grams, or ml if assuming water density
    "mL": 1,
    "Cloves": 1,     # leave as 1:1 or handle as special case
    "Eggs": 1,
    "Whole": 1
}

@app.route('/cabinet', methods=['GET', 'POST'])
def cabinet():
    if request.method == 'POST':
        name = request.form['ingredient_name'].strip()
        quantity = float(request.form['quantity'])
        unit = request.form['unit'].strip()

        # Get or create ingredient with unit
        ingredient = session.query(Ingredient).filter_by(name=name).first()
        if not ingredient:
            ingredient = Ingredient(name=name, unit=unit)
            session.add(ingredient)
            session.flush()
        else:
            # Optional: update unit if missing or mismatched
            if not ingredient.unit:
                ingredient.unit = unit

        # Add/update cabinet item
        existing = session.query(CabinetItem).filter_by(ingredient_id=ingredient.id).first()
        if existing:
            existing.quantity = quantity
        else:
            session.add(CabinetItem(ingredient_id=ingredient.id, quantity=quantity, unit=unit))

        session.commit()
        return redirect(url_for('cabinet'))

    cabinet_items = session.query(CabinetItem).all()
    return render_template('cabinet.html', cabinet_items=cabinet_items)

@app.route('/cabinet/delete', methods=['POST'])
def delete_from_cabinet():
    cabinet_id = request.form.get('cabinet_id')
    if cabinet_id:
        session.execute(
            text("DELETE FROM cabinet_items WHERE id = :id"),
            {'id': int(cabinet_id)}
        )
        session.commit()
    return redirect(url_for('cabinet'))

@app.route('/recipes/status')
def recipe_status():
    recipes = session.query(Recipe).options(
        joinedload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient)
    ).all()

    cabinet_items = session.query(CabinetItem).all()
    # Name -> Quantity
    cabinet_lookup = {
        item.ingredient.name.lower(): item.amount_in_cups
        for item in cabinet_items
    }

    recipe_statuses = []

    for recipe in recipes:
        status = {
            'recipe_name': recipe.name,
            'ingredients': [],
            'complete_count': 0,
            'total_count': len(recipe.ingredients),
        }

        for ri in recipe.ingredients:
            name = ri.ingredient.name.lower()
            required_qty_ml = ri.amount_in_cups
            available_qty_ml = cabinet_lookup.get(name, 0)

            if available_qty_ml >= required_qty_ml:
                status['ingredients'].append({
                    'name': name,
                    'status': '✅ Enough',
                    'needed': 0,
                    'unit': ri.ingredient.unit
                })
                status['complete_count'] += 1
            else:
                missing_ml = required_qty_ml - available_qty_ml
                missing_in_unit = convert_from_cups_to_original_unit(missing_ml, ri.ingredient.unit)
                status['ingredients'].append({
                    'name': name,
                    'status': '❌ Missing',
                    'needed': round(missing_in_unit, 2),
                    'unit': ri.ingredient.unit
                })

        # Add completion ratio for sorting
        if status['total_count'] > 0:
            status['completion_ratio'] = status['complete_count'] / status['total_count']
        else:
            status['completion_ratio'] = 0

        recipe_statuses.append(status)

    # Sort by completion ratio descending
    recipe_statuses.sort(key=lambda r: r['completion_ratio'], reverse=True)

    return render_template('recipe_status.html', recipe_statuses=recipe_statuses)


def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    print("Using database at:", os.path.abspath("shopping_list.db"))
    # Only open browser in the main process (not the reloader)
    if not os.environ.get("FLASK_RUN_FROM_CLI") and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Timer(1.0, open_browser).start()
    app.run(debug=True)
