"""Idempotently seed the catalog using the Flask application's configured database."""

from decimal import Decimal
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from app import app
from extensions import db
from models import Category, Product
from services.product_service import set_product_stock


CATEGORIES = (
    ("Eggs", "Fresh farm eggs for everyday meals and baking."),
    ("Whole Chicken", "Whole dressed chicken, chilled or frozen."),
    ("Chicken Cuts", "Fresh chicken portions prepared for convenient cooking."),
)

PRODUCTS = (
    {
        "name": "Free-Range Brown Eggs (6-Pack)",
        "description": "Six clean, farm-fresh brown eggs from free-range hens.",
        "price": "108.00",
        "stock": 40,
        "image_url": "https://placehold.co/600x400/png?text=Free-Range+Eggs",
        "category": "Eggs",
    },
    {
        "name": "Large White Eggs (12-Pack)",
        "description": "A dozen large white eggs, carefully sorted and packed.",
        "price": "168.00",
        "stock": 60,
        "image_url": "https://placehold.co/600x400/png?text=White+Eggs",
        "category": "Eggs",
    },
    {
        "name": "Farm-Fresh Brown Eggs (12-Pack)",
        "description": "Twelve richly flavored brown eggs from local farms.",
        "price": "192.00",
        "stock": 45,
        "image_url": "https://placehold.co/600x400/png?text=Brown+Eggs",
        "category": "Eggs",
    },
    {
        "name": "Organic Duck Eggs (6-Pack)",
        "description": "Six hearty duck eggs, ideal for rich baking and savory dishes.",
        "price": "210.00",
        "stock": 20,
        "image_url": "https://placehold.co/600x400/png?text=Duck+Eggs",
        "category": "Eggs",
    },
    {
        "name": "Whole Native Chicken (1 kg)",
        "description": "A locally raised native chicken, cleaned and ready to cook.",
        "price": "285.00",
        "stock": 18,
        "image_url": "https://placehold.co/600x400/png?text=Native+Chicken",
        "category": "Whole Chicken",
    },
    {
        "name": "Whole Broiler Chicken (1.2 kg)",
        "description": "Fresh, dressed broiler chicken suitable for roasting or stew.",
        "price": "330.00",
        "stock": 24,
        "image_url": "https://placehold.co/600x400/png?text=Whole+Broiler",
        "category": "Whole Chicken",
    },
    {
        "name": "Free-Range Whole Chicken (1.5 kg)",
        "description": "A larger free-range whole chicken with firm, flavorful meat.",
        "price": "495.00",
        "stock": 12,
        "image_url": "https://placehold.co/600x400/png?text=Free-Range+Chicken",
        "category": "Whole Chicken",
    },
    {
        "name": "Frozen Whole Chicken (1 kg)",
        "description": "Individually packed frozen whole chicken for convenient storage.",
        "price": "245.00",
        "stock": 30,
        "image_url": "https://placehold.co/600x400/png?text=Frozen+Chicken",
        "category": "Whole Chicken",
    },
    {
        "name": "Chicken Breast Fillet (500 g)",
        "description": "Boneless, skinless breast fillet, trimmed and ready to cook.",
        "price": "190.00",
        "stock": 35,
        "image_url": "https://placehold.co/600x400/png?text=Chicken+Breast",
        "category": "Chicken Cuts",
    },
    {
        "name": "Chicken Thighs (500 g)",
        "description": "Juicy bone-in chicken thighs, packed fresh in a 500 g tray.",
        "price": "155.00",
        "stock": 32,
        "image_url": "https://placehold.co/600x400/png?text=Chicken+Thighs",
        "category": "Chicken Cuts",
    },
    {
        "name": "Chicken Wings (500 g)",
        "description": "Fresh chicken wings, perfect for grilling, frying, or baking.",
        "price": "145.00",
        "stock": 28,
        "image_url": "https://placehold.co/600x400/png?text=Chicken+Wings",
        "category": "Chicken Cuts",
    },
    {
        "name": "Chicken Drumsticks (500 g)",
        "description": "Meaty chicken drumsticks, prepared for family-sized meals.",
        "price": "135.00",
        "stock": 30,
        "image_url": "https://placehold.co/600x400/png?text=Chicken+Drumsticks",
        "category": "Chicken Cuts",
    },
    {
        "name": "Chicken Leg Quarters (500 g)",
        "description": "Convenient leg quarters combining thigh and drumstick portions.",
        "price": "125.00",
        "stock": 26,
        "image_url": "https://placehold.co/600x400/png?text=Chicken+Leg+Quarters",
        "category": "Chicken Cuts",
    },
)


def verify_database_ready():
    inspector = db.inspect(db.engine)
    tables = set(inspector.get_table_names())
    missing_tables = {"categories", "products", "inventory"} - tables
    if missing_tables:
        raise RuntimeError(
            "Database tables are missing: "
            + ", ".join(sorted(missing_tables))
            + ". For a new empty database, run `python init_db.py` and "
            "`python -m flask --app app db stamp head`; for an existing "
            "database, run `python -m flask --app app db upgrade`."
        )

    product_columns = {column["name"] for column in inspector.get_columns("products")}
    if "is_active" not in product_columns:
        raise RuntimeError(
            "The products table is missing the migrated is_active column. "
            "Run `python -m flask --app app db upgrade` before seeding."
        )

    migration_directory = Path(__file__).resolve().parent / "migrations"
    script_directory = ScriptDirectory(str(migration_directory))
    expected_heads = set(script_directory.get_heads())
    with db.engine.connect() as connection:
        current_heads = set(MigrationContext.configure(connection).get_current_heads())
    if current_heads != expected_heads:
        raise RuntimeError(
            f"Database migrations are not current (current: {sorted(current_heads)}, "
            f"expected: {sorted(expected_heads)}). Run "
            "`python -m flask --app app db upgrade` before seeding."
        )


def seed_initial_data():
    """Insert catalog entries only when their category/name keys are absent."""
    categories_inserted = 0
    products_inserted = 0
    try:
        category_by_name = {
            category.name.strip().casefold(): category
            for category in Category.query.all()
        }
        for name, description in CATEGORIES:
            key = name.casefold()
            if key not in category_by_name:
                category = Category()
                category.name = name
                category.description = description
                db.session.add(category)
                db.session.flush()
                category_by_name[key] = category
                categories_inserted += 1

        existing_products = {
            (product.name.strip().casefold(), product.category_id)
            for product in Product.query.all()
        }
        for details in PRODUCTS:
            category = category_by_name[details["category"].casefold()]
            key = (details["name"].casefold(), category.id)
            if key in existing_products:
                continue
            product = Product()
            product.name = details["name"]
            product.description = details["description"]
            product.price = Decimal(details["price"])
            product.stock = details["stock"]
            product.image_url = details["image_url"]
            product.category_id = category.id
            db.session.add(product)
            db.session.flush()
            set_product_stock(product, details["stock"])
            existing_products.add(key)
            products_inserted += 1

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return {
        "categories_inserted": categories_inserted,
        "categories_present": Category.query.count() - categories_inserted,
        "products_inserted": products_inserted,
        "products_present": Product.query.count() - products_inserted,
        "categories_total": Category.query.count(),
        "products_total": Product.query.count(),
    }


if __name__ == "__main__":
    with app.app_context():
        verify_database_ready()
        result = seed_initial_data()
        print(
            "Categories: "
            f"{result['categories_inserted']} inserted, "
            f"{result['categories_present']} already present "
            f"({result['categories_total']} total)."
        )
        print(
            "Products: "
            f"{result['products_inserted']} inserted, "
            f"{result['products_present']} already present "
            f"({result['products_total']} total)."
        )
