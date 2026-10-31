from extensions import db
from models import Category, Inventory, Product
from seed import PRODUCTS, seed_initial_data


def test_seed_is_idempotent_and_catalog_endpoints_expose_seeded_records(client, app):
    with app.app_context():
        first = seed_initial_data()
        second = seed_initial_data()

        assert first["categories_inserted"] == 3
        assert first["products_inserted"] == len(PRODUCTS)
        assert second["categories_inserted"] == 0
        assert second["products_inserted"] == 0
        assert Category.query.count() == 3
        assert Product.query.count() == len(PRODUCTS)
        assert all(product.category_id is not None for product in Product.query.all())
        assert Inventory.query.count() == len(PRODUCTS)
        sample_product_id = Product.query.order_by(Product.id).first().id

    categories_response = client.get("/api/v1/categories")
    products_response = client.get("/api/v1/products")
    product_response = client.get(f"/api/v1/products/{sample_product_id}")

    assert categories_response.status_code == 200
    assert {category["name"] for category in categories_response.get_json()["data"]["categories"]} == {
        "Eggs",
        "Whole Chicken",
        "Chicken Cuts",
    }
    assert products_response.status_code == 200
    seeded_products = products_response.get_json()["data"]["products"]
    assert len(seeded_products) == len(PRODUCTS)
    assert product_response.status_code == 200
    assert product_response.get_json()["data"]["product"]["id"] == sample_product_id


def test_seed_preserves_existing_category_and_product(app):
    with app.app_context():
        category = Category(name="Eggs", description="Existing category")
        db.session.add(category)
        db.session.flush()
        product = Product(
            name=PRODUCTS[0]["name"],
            description="Existing product",
            price="1.00",
            stock=3,
            category_id=category.id,
        )
        db.session.add(product)
        db.session.commit()
        category_id = category.id
        product_id = product.id

        result = seed_initial_data()

        assert Category.query.filter_by(name="Eggs").one().description == "Existing category"
        assert db.session.get(Category, category_id) is not None
        stored_product = db.session.get(Product, product_id)
        assert stored_product.description == "Existing product"
        assert stored_product.price == 1
        assert result["products_inserted"] == len(PRODUCTS) - 1
        assert Inventory.query.count() == len(PRODUCTS) - 1
