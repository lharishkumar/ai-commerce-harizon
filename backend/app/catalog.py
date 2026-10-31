from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from .models import Product

SEED_PRODUCTS = [
    dict(id="aura-buds-pro", name="Aura Buds Pro", category="Audio", brand="SONIQ", tagline="Quiet the noise. Find your rhythm.", description="Adaptive noise cancellation and rich, balanced sound for every part of your day.", price=8999, compare_at=10999, rating=4.8, review_count=324, image_key="buds", color="#e6e0ff", featured=True, specs={"Noise cancellation":"Adaptive ANC", "Battery":"32 hours with case", "Connectivity":"Bluetooth 5.3", "Water resistance":"IPX4"}),
    dict(id="pulse-watch-4", name="Pulse Watch 4", category="Wearables", brand="NORTHSTAR", tagline="A little more in tune.", description="A thoughtfully designed smart watch with daily health insights and a week of battery life.", price=14999, compare_at=17999, rating=4.7, review_count=218, image_key="watch", color="#dcebe3", featured=True, specs={"Display":"1.9 inch AMOLED", "Battery":"7 days", "Water resistance":"5 ATM", "Compatibility":"iOS and Android"}),
    dict(id="halo-speaker", name="Halo Smart Speaker", category="Smart home", brand="SONIQ", tagline="Room-filling sound. Smaller footprint.", description="A compact wireless speaker with clear vocals, rich bass and hands-free controls.", price=6999, compare_at=None, rating=4.6, review_count=143, image_key="speaker", color="#f3dfd2", featured=True, specs={"Audio":"360 degree", "Connectivity":"Wi-Fi, Bluetooth", "Voice assistant":"Built in", "Power":"USB-C"}),
    dict(id="beam-projector", name="Beam Mini Projector", category="Smart home", brand="LUMA", tagline="Bring the big screen anywhere.", description="Portable full HD projection with auto keystone and instant wireless casting.", price=24999, compare_at=28999, rating=4.5, review_count=97, image_key="projector", color="#e2e7f7", featured=True, specs={"Resolution":"1080p Full HD", "Brightness":"700 ANSI lumens", "Projection":"Up to 120 inches", "Connectivity":"Wi-Fi 6, HDMI"}),
    dict(id="orbit-keyboard", name="Orbit Mechanical Keyboard", category="Accessories", brand="NORTHSTAR", tagline="A better feel for every keystroke.", description="A compact wireless mechanical keyboard with quiet tactile switches and multi-device pairing.", price=5999, compare_at=6999, rating=4.4, review_count=86, image_key="keyboard", color="#f4e8d8", specs={"Layout":"75% compact", "Switches":"Silent tactile", "Battery":"Up to 60 days", "Connectivity":"Bluetooth, USB-C"}),
    dict(id="drift-mouse", name="Drift Wireless Mouse", category="Accessories", brand="NORTHSTAR", tagline="Precision without the fuss.", description="Ergonomic wireless tracking with silent clicks and a rechargeable battery.", price=2499, compare_at=None, rating=4.5, review_count=132, image_key="mouse", color="#e0e7ee", specs={"DPI":"Up to 4000", "Battery":"Rechargeable USB-C", "Connectivity":"Bluetooth, 2.4 GHz", "Weight":"92 g"}),
    dict(id="frame-camera", name="Frame 4K Webcam", category="Accessories", brand="LUMA", tagline="Show up in your best light.", description="Sharp 4K video with automatic light correction and a private lens shutter.", price=7999, compare_at=9499, rating=4.6, review_count=74, image_key="camera", color="#e9e1da", specs={"Resolution":"4K UHD", "Field of view":"90 degrees", "Microphone":"Dual noise reduction", "Privacy":"Physical shutter"}),
    dict(id="nova-powerbank", name="Nova 20K Power Bank", category="Accessories", brand="VOLT", tagline="Power for the long way round.", description="A high-capacity fast-charging power bank with two USB-C ports and a clear status display.", price=3999, compare_at=4499, rating=4.7, review_count=251, image_key="powerbank", color="#dce8f4", specs={"Capacity":"20,000 mAh", "Output":"65 W USB-C PD", "Ports":"2 USB-C, 1 USB-A", "Weight":"410 g"}),
    dict(id="arc-charger", name="Arc 3-in-1 Charger", category="Smart home", brand="VOLT", tagline="One place for the everyday essentials.", description="A foldable magnetic charging stand for your phone, watch and earbuds.", price=4999, compare_at=None, rating=4.3, review_count=62, image_key="charger", color="#f1e2df", specs={"Phone output":"15 W wireless", "Watch output":"5 W", "Earbuds output":"5 W", "Foldable":"Yes"}),
    dict(id="echo-ring", name="Echo Smart Ring", category="Wearables", brand="NORTHSTAR", tagline="Wellness, quietly understood.", description="A lightweight wellness ring that tracks sleep, activity and recovery without a screen.", price=19999, compare_at=22999, rating=4.5, review_count=53, image_key="ring", color="#e8e1d2", specs={"Battery":"Up to 6 days", "Water resistance":"100 m", "Sensors":"Heart rate, temperature", "Sizes":"6 to 13"}),
    dict(id="terra-lamp", name="Terra Ambient Lamp", category="Smart home", brand="LUMA", tagline="Set the tone for the room.", description="Warm, adjustable lighting with schedules and app-based scene controls.", price=5499, compare_at=None, rating=4.4, review_count=91, image_key="lamp", color="#eee6d4", specs={"Brightness":"800 lumens", "Color temperature":"2200–6500 K", "Connectivity":"Wi-Fi", "Control":"App and touch"}),
    dict(id="soniq-max", name="SONIQ Max Headphones", category="Audio", brand="SONIQ", tagline="Your own little listening room.", description="Over-ear comfort, detailed sound and long-lasting adaptive noise cancellation.", price=12999, compare_at=15999, rating=4.8, review_count=189, image_key="headphones", color="#dce6f1", specs={"Noise cancellation":"Adaptive ANC", "Battery":"48 hours", "Connectivity":"Bluetooth 5.3", "Weight":"248 g"}),
]


def seed_products(db: Session):
    if db.scalar(select(Product.id).limit(1)):
        return
    for row in SEED_PRODUCTS:
        db.add(Product(**row, stock=25))
    db.commit()


def list_products(db: Session, q="", category="", sort="featured"):
    stmt = select(Product).where(Product.active.is_(True))
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where(or_(Product.name.ilike(term), Product.brand.ilike(term), Product.category.ilike(term), Product.description.ilike(term)))
    if category and category != "All products":
        stmt = stmt.where(Product.category == category)
    if sort == "price-low": stmt = stmt.order_by(Product.price.asc())
    elif sort == "price-high": stmt = stmt.order_by(Product.price.desc())
    elif sort == "top-rated": stmt = stmt.order_by(Product.rating.desc())
    else: stmt = stmt.order_by(Product.featured.desc(), Product.name.asc())
    return list(db.scalars(stmt))
