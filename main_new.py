from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Text, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from typing import Optional, List

# ==================== CREATE APP ====================
app = FastAPI(title="Flower Shop API New", version="2.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả origin
    allow_credentials=True,
    allow_methods=["*"],  # Cho phép tất cả method (GET, POST, PUT, DELETE...)
    allow_headers=["*"],  # Cho phép tất cả headers
)

# ==================== CONNECT TO THE NEW DATABASE ====================

SQLALCHEMY_DATABASE_URL = "postgresql://postgres:123456@localhost:5432/flower_shop_new"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==================== MODELS ====================
class Unit(Base):
    __tablename__ = "units"
    id_unit = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    short_name = Column(String(20), nullable=False)
    is_integer_only = Column(Boolean, default=False)

class Category(Base):
    __tablename__ = "categories"
    id_category = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id_category", ondelete="CASCADE"))
    order_num = Column(Integer, default=0)
    base_unit_id = Column(Integer, ForeignKey("units.id_unit"))
    children = relationship("Category", backref="parent", remote_side=[id_category])

class Product(Base):
    __tablename__ = "products"
    id_product = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id_category", ondelete="CASCADE"))
    unit_id = Column(Integer, ForeignKey("units.id_unit"))
    price = Column(Integer, nullable=False)

class Parameter(Base):
    __tablename__ = "parameters"
    id_parameter = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    short_name = Column(String(50), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    id_param_type = Column(Integer, ForeignKey("param_type.id_param_type"))
    min_value = Column(Numeric, nullable=True)   
    max_value = Column(Numeric, nullable=True)   
    base_unit_id = Column(Integer, ForeignKey("units.id_unit"), nullable=True)  # 🔥 THÊM DÒNG NÀY

class EnumValue(Base):
    __tablename__ = "enum_values"
    id_enum_value = Column(Integer, primary_key=True, index=True)
    parameter_id = Column(Integer, ForeignKey("parameters.id_parameter", ondelete="CASCADE"))
    value_name = Column(String(100), nullable=False)
    value_code = Column(String(50))

class CategoryParameter(Base):
    __tablename__ = "category_parameters"
    id_category = Column(Integer, ForeignKey("categories.id_category", ondelete="CASCADE"), primary_key=True)
    id_parameter = Column(Integer, ForeignKey("parameters.id_parameter", ondelete="CASCADE"), primary_key=True)
    is_mandatory = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)

class ProductParameterValue(Base):
    __tablename__ = "product_parameter_values"
    id_product = Column(Integer, ForeignKey("products.id_product", ondelete="CASCADE"), primary_key=True)
    id_parameter = Column(Integer, ForeignKey("parameters.id_parameter", ondelete="CASCADE"), primary_key=True)
    value_string = Column(Text)
    value_integer = Column(Integer)
    value_enum = Column(Integer, ForeignKey("enum_values.id_enum_value"))

class Enum(Base):
    __tablename__ = "enums"
    id_enum = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    param_id = Column(Integer, ForeignKey("parameters.id_parameter"), nullable=True)  # 🔥 THÊM DÒNG NÀY

class EnumItem(Base):
    __tablename__ = "enum_items"
    id_item = Column(Integer, primary_key=True, index=True)
    id_enum = Column(Integer, ForeignKey("enums.id_enum", ondelete="CASCADE"))
    item_name = Column(String(100), nullable=False)
    item_code = Column(String(50))
    order_num = Column(Integer, default=0)

class ParamType(Base):
    __tablename__ = "param_type"
    id_param_type = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    sys_code = Column(String(20), unique=True, nullable=False)

# ==================== API UNITS ====================
@app.get("/units")
def get_units(db: Session = Depends(get_db)):
    return db.query(Unit).all()

@app.post("/units")
def create_unit(name: str, short_name: str, is_integer_only: bool = False, db: Session = Depends(get_db)):
    unit = Unit(name=name, short_name=short_name, is_integer_only=is_integer_only)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit

@app.put("/units/{id}")
def update_unit(
    id: int, 
    name: str, 
    short_name: str,
    is_integer_only: Optional[bool] = None,  
    db: Session = Depends(get_db)
):
    unit = db.query(Unit).filter(Unit.id_unit == id).first()
    if not unit:
        raise HTTPException(404, "Unit not found")
    
    unit.name = name
    unit.short_name = short_name
    

    if is_integer_only is not None:
        unit.is_integer_only = is_integer_only
    
    db.commit()
    return unit

@app.delete("/units/{id}")
def delete_unit(id: int, db: Session = Depends(get_db)):
    unit = db.query(Unit).filter(Unit.id_unit == id).first()
    if not unit:
        raise HTTPException(404, "Unit not found")
    used_in_categories = db.query(Category).filter(Category.base_unit_id == id).count()
    used_in_products = db.query(Product).filter(Product.unit_id == id).count()
    if used_in_categories > 0 or used_in_products > 0:
        raise HTTPException(400, "Cannot delete unit: it is in use")
    db.delete(unit)
    db.commit()
    return {"ok": True}

# ==================== API CATEGORIES ====================
@app.get("/categories/tree")
def get_category_tree(db: Session = Depends(get_db)):
    def build_tree(parent_id=None):
        cats = db.query(Category).filter(Category.parent_id == parent_id).order_by(Category.order_num).all()
        return [{
            "id": c.id_category,
            "name": c.name,
            "code": c.code,
            "children": build_tree(c.id_category)
        } for c in cats]
    return build_tree()

@app.post("/categories")
def create_category(name: str, code: str, parent_id: Optional[int] = None, base_unit_id: Optional[int] = None, db: Session = Depends(get_db)):
    existing = db.query(Category).filter(Category.code == code).first()
    if existing:
        raise HTTPException(400, "Code already exists")
    cat = Category(name=name, code=code, parent_id=parent_id, base_unit_id=base_unit_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat

@app.put("/categories/{id}")
def update_category(
    id: int,
    name: str,
    code: str,
    parent_id: Optional[int] = None,
    base_unit_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    category = db.query(Category).filter(Category.id_category == id).first()
    if not category:
        raise HTTPException(404, "Category not found")
    
    category.name = name
    category.code = code
    if parent_id is not None:
        category.parent_id = parent_id
    if base_unit_id is not None:
        category.base_unit_id = base_unit_id
    
    db.commit()
    db.refresh(category)
    return category

@app.delete("/categories/{id}")
def delete_category(id: int, db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id_category == id).first()
    if not cat:
        raise HTTPException(404, "Category not found")
    db.delete(cat)
    db.commit()
    return {"ok": True}

@app.put("/categories/{id}/up")
def move_category_up(id: int, db: Session = Depends(get_db)):
    """Di chuyển danh mục lên trên"""
    category = db.query(Category).filter(Category.id_category == id).first()
    if not category:
        raise HTTPException(404, "Category not found")
    
    # Tìm danh mục phía trên (cùng parent_id, order_num nhỏ hơn)
    prev = db.query(Category).filter(
        Category.parent_id == category.parent_id,
        Category.order_num < category.order_num
    ).order_by(Category.order_num.desc()).first()
    
    if not prev:
        raise HTTPException(400, "Already at first position")
    
    # Đổi order_num
    prev.order_num, category.order_num = category.order_num, prev.order_num
    db.commit()
    return {"ok": True}

@app.put("/categories/{id}/down")
def move_category_down(id: int, db: Session = Depends(get_db)):
    """Di chuyển danh mục xuống dưới"""
    category = db.query(Category).filter(Category.id_category == id).first()
    if not category:
        raise HTTPException(404, "Category not found")
    
    # Tìm danh mục phía dưới (cùng parent_id, order_num lớn hơn)
    next_cat = db.query(Category).filter(
        Category.parent_id == category.parent_id,
        Category.order_num > category.order_num
    ).order_by(Category.order_num.asc()).first()
    
    if not next_cat:
        raise HTTPException(400, "Already at last position")
    
    # Đổi order_num
    next_cat.order_num, category.order_num = category.order_num, next_cat.order_num
    db.commit()
    return {"ok": True}

# ==================== API CATEGORY PRODUCTS & PARAMETERS ====================
@app.get("/categories/{id}/products")
def get_products_by_category(id: int, db: Session = Depends(get_db)):
    def get_all_child_ids(parent_id):
        ids = [parent_id]
        children = db.query(Category).filter(Category.parent_id == parent_id).all()
        for child in children:
            ids.extend(get_all_child_ids(child.id_category))
        return ids
    all_cat_ids = get_all_child_ids(id)
    products = db.query(Product).filter(Product.category_id.in_(all_cat_ids)).all()
    result = []
    for p in products:
        unit = db.query(Unit).filter(Unit.id_unit == p.unit_id).first()
        result.append({
            "id_product": p.id_product,
            "name": p.name,
            "code": p.code,
            "price": p.price,
            "unit_name": unit.short_name if unit else "",
            "unit_is_integer_only": unit.is_integer_only if unit else False
        })
    return {"items": result}

@app.get("/categories/{id}/parameters")

def get_category_parameters(id: int, db: Session = Depends(get_db)):
    params = db.query(CategoryParameter).filter(CategoryParameter.id_category == id).order_by(CategoryParameter.display_order).all()
    result = []
    for cp in params:
        param = db.query(Parameter).filter(Parameter.id_parameter == cp.id_parameter).first()
        if param:
            param_type = db.query(ParamType).filter(ParamType.id_param_type == param.id_param_type).first()
            result.append({
                "id_parameter": param.id_parameter,
                "name": param.name,
                "code": param.code,
                "param_type_code": param_type.sys_code if param_type else None,
                "is_mandatory": cp.is_mandatory,
                "display_order": cp.display_order,
                "min_value": param.min_value,
                "max_value": param.max_value,
                "base_unit_id": param.base_unit_id  # 🔥 THÊM DÒNG NÀY
            })
    return result

# ==================== API PRODUCTS ====================
@app.post("/products")
def create_product(name: str, code: str, category_id: int, unit_id: int, price: float, db: Session = Depends(get_db)):
    existing = db.query(Product).filter(Product.code == code).first()
    if existing:
        raise HTTPException(400, "Product code already exists")
    product = Product(name=name, code=code, category_id=category_id, unit_id=unit_id, price=price)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

@app.put("/products/{id}")
def update_product(
    id: int, 
    name: str, 
    price: float,
    code: Optional[str] = None,
    unit_id: Optional[int] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id_product == id).first()
    if not product:
        raise HTTPException(404, "Product not found")
    

    

    product.name = name
    product.price = price
    
    if code is not None:

        existing = db.query(Product).filter(Product.code == code, Product.id_product != id).first()
        if existing:
            raise HTTPException(400, "Product code already exists")
        product.code = code
    
    if unit_id is not None:
        product.unit_id = unit_id
    
    if category_id is not None:
        product.category_id = category_id
    
    db.commit()
    db.refresh(product)
    
    return product

@app.delete("/products/{id}")
def delete_product(id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id_product == id).first()
    if not product:
        raise HTTPException(404, "Product not found")
    db.delete(product)
    db.commit()
    return {"ok": True}

@app.get("/products/filter")
def filter_products(
    category_id: Optional[int] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    theme: Optional[int] = None,
    color: Optional[int] = None,
    height_min: Optional[float] = None,
    height_max: Optional[float] = None,
    diam_min: Optional[float] = None,
    diam_max: Optional[float] = None,
    # 🔥 THÊM 4 DÒNG NÀY 🔥
    length_min: Optional[float] = None,
    length_max: Optional[float] = None,
    width_min: Optional[float] = None,
    width_max: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Lọc sản phẩm theo danh mục, giá, và các đặc tính (enum, số)"""
    
    query = db.query(Product)
    
    # Lọc theo danh mục (bao gồm danh mục con)
    if category_id:
        def get_all_child_ids(parent_id):
            ids = [parent_id]
            children = db.query(Category).filter(Category.parent_id == parent_id).all()
            for child in children:
                ids.extend(get_all_child_ids(child.id_category))
            return ids
        all_cat_ids = get_all_child_ids(category_id)
        query = query.filter(Product.category_id.in_(all_cat_ids))
    
    # Lọc theo giá
    if price_min is not None:
        query = query.filter(Product.price >= price_min)
    if price_max is not None:
        query = query.filter(Product.price <= price_max)
    
    # Lọc theo Тема (parameter id=1)
    if theme is not None:
        query = query.filter(
            Product.id_product.in_(
                db.query(ProductParameterValue.id_product).filter(
                    ProductParameterValue.id_parameter == 1,
                    ProductParameterValue.value_enum == theme
                )
            )
        )
    
    # Lọc theo Цвет (parameter id=2)
    if color is not None:
        query = query.filter(
            Product.id_product.in_(
                db.query(ProductParameterValue.id_product).filter(
                    ProductParameterValue.id_parameter == 2,
                    ProductParameterValue.value_enum == color
                )
            )
        )
    
    # Lọc theo Высота (parameter id=4)
    if height_min is not None:
        query = query.filter(
            Product.id_product.in_(
                db.query(ProductParameterValue.id_product).filter(
                    ProductParameterValue.id_parameter == 4,
                    ProductParameterValue.value_integer >= height_min
                )
            )
        )
    if height_max is not None:
        query = query.filter(
            Product.id_product.in_(
                db.query(ProductParameterValue.id_product).filter(
                    ProductParameterValue.id_parameter == 4,
                    ProductParameterValue.value_integer <= height_max
                )
            )
        )
    
    # Lọc theo Диаметр (parameter id=3)
    if diam_min is not None:
        query = query.filter(
            Product.id_product.in_(
                db.query(ProductParameterValue.id_product).filter(
                    ProductParameterValue.id_parameter == 3,
                    ProductParameterValue.value_integer >= diam_min
                )
            )
        )
    if diam_max is not None:
        query = query.filter(
            Product.id_product.in_(
                db.query(ProductParameterValue.id_product).filter(
                    ProductParameterValue.id_parameter == 3,
                    ProductParameterValue.value_integer <= diam_max
                )
            )
        )
    
    # 🔥 THÊM LỌC THEO ДЛИНА (LENGTH) 🔥
    if length_min is not None or length_max is not None:
        param = db.query(Parameter).filter(Parameter.code == 'LENGTH').first()
        if param:
            subquery = db.query(ProductParameterValue.id_product).filter(
                ProductParameterValue.id_parameter == param.id_parameter
            )
            if length_min is not None:
                subquery = subquery.filter(ProductParameterValue.value_integer >= length_min)
            if length_max is not None:
                subquery = subquery.filter(ProductParameterValue.value_integer <= length_max)
            query = query.filter(Product.id_product.in_(subquery))
    
    # 🔥 THÊM LỌC THEO ШИРИНА (WIDTH) 🔥
    if width_min is not None or width_max is not None:
        param = db.query(Parameter).filter(Parameter.code == 'WIDTH').first()
        if param:
            subquery = db.query(ProductParameterValue.id_product).filter(
                ProductParameterValue.id_parameter == param.id_parameter
            )
            if width_min is not None:
                subquery = subquery.filter(ProductParameterValue.value_integer >= width_min)
            if width_max is not None:
                subquery = subquery.filter(ProductParameterValue.value_integer <= width_max)
            query = query.filter(Product.id_product.in_(subquery))
    
    # Thực thi query
    products = query.all()
    
    # Thêm thông tin unit
    result = []
    for p in products:
        unit = db.query(Unit).filter(Unit.id_unit == p.unit_id).first()
        result.append({
            "id_product": p.id_product,
            "name": p.name,
            "code": p.code,
            "price": p.price,
            "unit_name": unit.short_name if unit else "",
            "unit_is_integer_only": unit.is_integer_only if unit else False,
            "category_id": p.category_id
        })
    
    return {"items": result}

@app.get("/products/{id}")
def get_product(id: int, db: Session = Depends(get_db)):
    """Get basic product information (for editing)"""
    product = db.query(Product).filter(Product.id_product == id).first()
    if not product:
        raise HTTPException(404, "Product not found")
    
    return {
        "id_product": product.id_product,
        "name": product.name,
        "code": product.code,
        "price": product.price,
        "category_id": product.category_id,
        "unit_id": product.unit_id
    }

@app.get("/products/search")
def search_products(q: str, db: Session = Depends(get_db)):
    products = db.query(Product).filter(
        (Product.name.ilike(f"%{q}%")) | (Product.code.ilike(f"%{q}%"))
    ).all()
    return {"items": products}



# ==================== API ENUMS ====================
@app.get("/enums")
def get_enums(db: Session = Depends(get_db)):
    return db.query(Enum).all()

@app.post("/enums")
def create_enum(
    name: str, 
    code: str, 
    param_id: Optional[int] = None,  # 🔥 THÊM THAM SỐ NÀY
    db: Session = Depends(get_db)
):
    existing = db.query(Enum).filter(Enum.code == code).first()
    if existing:
        raise HTTPException(400, "Enum code already exists")
    
    enum = Enum(name=name, code=code, param_id=param_id)  # 🔥 THÊM param_id
    db.add(enum)
    db.commit()
    db.refresh(enum)
    return enum

@app.put("/enums/{id}")
def update_enum(id: int, name: str, code: str, db: Session = Depends(get_db)):
    enum = db.query(Enum).filter(Enum.id_enum == id).first()
    if not enum:
        raise HTTPException(404, "Enum not found")
    enum.name = name
    enum.code = code
    db.commit()
    return enum

@app.delete("/enums/{id}")
def delete_enum(id: int, db: Session = Depends(get_db)):
    enum = db.query(Enum).filter(Enum.id_enum == id).first()
    if not enum:
        raise HTTPException(404, "Enum not found")
    
    # 🔥 KIỂM TRA: Có category nào đang dùng parameter liên quan đến enum này không?
    # Tìm tất cả parameter có code liên quan
    params_to_check = []
    
    # Tìm theo param_id (nếu có)
    if enum.param_id:
        params_to_check.append(enum.param_id)
    
    # Tìm theo code (COLORS -> COLOR)
    param_code = enum.code
    if param_code.endswith('S'):
        param_code = param_code[:-1]
    param = db.query(Parameter).filter(Parameter.code == param_code).first()
    if param:
        params_to_check.append(param.id_parameter)
    
    # Kiểm tra trong category_parameters
    for p_id in params_to_check:
        category_param = db.query(CategoryParameter).filter(
            CategoryParameter.id_parameter == p_id
        ).first()
        if category_param:
            raise HTTPException(400, f"Нельзя удалить перечисление '{enum.name}', так как оно используется в категориях")
    
    # Xóa enum_items trước
    db.query(EnumItem).filter(EnumItem.id_enum == id).delete()
    
    db.delete(enum)
    db.commit()
    return {"ok": True}

# ==================== API ENUM ITEMS ====================
@app.get("/enums/{id}/items")
def get_enum_items(id: int, db: Session = Depends(get_db)):
    return db.query(EnumItem).filter(EnumItem.id_enum == id).order_by(EnumItem.order_num).all()

@app.post("/enum-items")
def create_enum_item(
    id_enum: int, 
    item_name: str, 
    item_code: str, 
    db: Session = Depends(get_db)
):
    # Tạo enum_item mới
    max_order = db.query(EnumItem).filter(EnumItem.id_enum == id_enum).count()
    item = EnumItem(
        id_enum=id_enum, 
        item_name=item_name, 
        item_code=item_code, 
        order_num=max_order + 1
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    
    # 🔥 TỰ ĐỘNG THÊM VÀO ENUM_VALUES DỰA VÀO PARAM_ID
    enum_obj = db.query(Enum).filter(Enum.id_enum == id_enum).first()
    
    if enum_obj and enum_obj.param_id:
        param = db.query(Parameter).filter(Parameter.id_parameter == enum_obj.param_id).first()
        if param:
            existing = db.query(EnumValue).filter(
                EnumValue.parameter_id == param.id_parameter,
                EnumValue.value_name == item_name
            ).first()
            if not existing:
                enum_value = EnumValue(
                    parameter_id=param.id_parameter,
                    value_name=item_name,
                    value_code=item_code
                )
                db.add(enum_value)
                db.commit()
    
    return item

@app.put("/enum-items/{id}")
def update_enum_item(
    id: int, 
    item_name: str, 
    item_code: str, 
    db: Session = Depends(get_db)
):
    item = db.query(EnumItem).filter(EnumItem.id_item == id).first()
    if not item:
        raise HTTPException(404, "Enum item not found")
    
    old_name = item.item_name
    item.item_name = item_name
    item.item_code = item_code
    db.commit()
    
    # 🔥 CẬP NHẬT ENUM_VALUES 🔥
    enum_obj = db.query(Enum).filter(Enum.id_enum == item.id_enum).first()
    
    ENUM_TO_PARAM = {
        "COLORS": "COLOR",
        "THEMES": "THEME",
        "PACK_MATERIALS": "MATERIAL",
        "COUNTRIES": "COUNTRY"
    }
    
    if enum_obj and enum_obj.code in ENUM_TO_PARAM:
        param_code = ENUM_TO_PARAM[enum_obj.code]
        param = db.query(Parameter).filter(Parameter.code == param_code).first()
        
        if param:
            enum_value = db.query(EnumValue).filter(
                EnumValue.parameter_id == param.id_parameter,
                EnumValue.value_name == old_name
            ).first()
            if enum_value:
                enum_value.value_name = item_name
                enum_value.value_code = item_code
                db.commit()
    
    return item

@app.delete("/enum-items/{id}")
def delete_enum_item(id: int, db: Session = Depends(get_db)):
    item = db.query(EnumItem).filter(EnumItem.id_item == id).first()
    if not item:
        raise HTTPException(404, "Enum item not found")
    
    # 🔥 XÓA TRONG ENUM_VALUES TRƯỚC 🔥
    enum_obj = db.query(Enum).filter(Enum.id_enum == item.id_enum).first()
    
    ENUM_TO_PARAM = {
        "COLORS": "COLOR",
        "THEMES": "THEME",
        "PACK_MATERIALS": "MATERIAL",
        "COUNTRIES": "COUNTRY"
    }
    
    if enum_obj and enum_obj.code in ENUM_TO_PARAM:
        param_code = ENUM_TO_PARAM[enum_obj.code]
        param = db.query(Parameter).filter(Parameter.code == param_code).first()
        
        if param:
            enum_value = db.query(EnumValue).filter(
                EnumValue.parameter_id == param.id_parameter,
                EnumValue.value_name == item.item_name
            ).first()
            if enum_value:
                db.delete(enum_value)
    
    db.delete(item)
    db.commit()
    return {"ok": True}

@app.delete("/enum-values/{id}")
def delete_enum_value(id: int, db: Session = Depends(get_db)):
    """Delete enum value of parameter (enum_values table)"""
    enum_value = db.query(EnumValue).filter(EnumValue.id_enum_value == id).first()
    if not enum_value:
        raise HTTPException(404, "Enum value not found")
    db.delete(enum_value)
    db.commit()
    return {"ok": True}

@app.get("/parameters-for-enum")
def get_parameters_for_enum(db: Session = Depends(get_db)):
    """Lấy danh sách parameters có kiểu enum (để chọn khi tạo enum)"""
    params = db.query(Parameter).filter(Parameter.id_param_type == 3).all()
    return [{"id": p.id_parameter, "name": p.name, "code": p.code} for p in params]

@app.post("/enum-values")
def create_enum_value(
    parameter_id: int,
    value_name: str,
    value_code: str,
    db: Session = Depends(get_db)
):
    """Create a new enum value for parameter"""

    parameter = db.query(Parameter).filter(Parameter.id_parameter == parameter_id).first()
    if not parameter:
        raise HTTPException(404, "Parameter not found")
    

    enum_value = EnumValue(
        parameter_id=parameter_id,
        value_name=value_name,
        value_code=value_code
    )
    db.add(enum_value)
    db.commit()
    db.refresh(enum_value)
    return enum_value

@app.put("/enum-items/{id}/up")
def move_enum_item_up(id: int, db: Session = Depends(get_db)):
    item = db.query(EnumItem).filter(EnumItem.id_item == id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    prev = db.query(EnumItem).filter(
        EnumItem.id_enum == item.id_enum,
        EnumItem.order_num < item.order_num
    ).order_by(EnumItem.order_num.desc()).first()
    if prev:
        prev.order_num, item.order_num = item.order_num, prev.order_num
        db.commit()
    return {"ok": True}

@app.put("/enum-items/{id}/down")
def move_enum_item_down(id: int, db: Session = Depends(get_db)):
    item = db.query(EnumItem).filter(EnumItem.id_item == id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    nxt = db.query(EnumItem).filter(
        EnumItem.id_enum == item.id_enum,
        EnumItem.order_num > item.order_num
    ).order_by(EnumItem.order_num.asc()).first()
    if nxt:
        nxt.order_num, item.order_num = item.order_num, nxt.order_num
        db.commit()
    return {"ok": True}

# ==================== API PARAMETERS ====================
@app.get("/parameters")
def get_parameters(db: Session = Depends(get_db)):
    return db.query(Parameter).all()

@app.post("/parameters")
def create_parameter(
    name: str,
    short_name: str,
    code: str,
    id_param_type: int,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    base_unit_id: Optional[int] = None,  # 🔥 THÊM DÒNG NÀY
    db: Session = Depends(get_db)
):
    param_type = db.query(ParamType).filter(ParamType.id_param_type == id_param_type).first()
    if not param_type:
        raise HTTPException(400, "Invalid param_type id")
    
    existing = db.query(Parameter).filter(Parameter.code == code).first()
    if existing:
        raise HTTPException(400, "Parameter code already exists")
    
    param = Parameter(
        name=name,
        short_name=short_name,
        code=code,
        id_param_type=id_param_type,
        min_value=min_value,
        max_value=max_value,
        base_unit_id=base_unit_id  # 🔥 THÊM DÒNG NÀY
    )
    db.add(param)
    db.commit()
    db.refresh(param)
    return param

@app.put("/parameters/{id_parameter}")
def update_parameter(
    id_parameter: int,
    name: str,
    short_name: str,
    code: str,
    id_param_type: int,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    base_unit_id: Optional[int] = None,  # 🔥 THÊM DÒNG NÀY
    db: Session = Depends(get_db)
):
    param = db.query(Parameter).filter(Parameter.id_parameter == id_parameter).first()
    if not param:
        raise HTTPException(404, "Parameter not found")
    
    existing = db.query(Parameter).filter(Parameter.code == code, Parameter.id_parameter != id_parameter).first()
    if existing:
        raise HTTPException(400, "Parameter code already exists")
    
    param.name = name
    param.short_name = short_name
    param.code = code
    param.id_param_type = id_param_type
    param.min_value = min_value
    param.max_value = max_value
    param.base_unit_id = base_unit_id  # 🔥 THÊM DÒNG NÀY
    
    db.commit()
    db.refresh(param)
    return param

@app.get("/parameters/{id}/enum-values")
def get_parameter_enum_values(id: int, db: Session = Depends(get_db)):
    param = db.query(Parameter).filter(Parameter.id_parameter == id).first()
    if not param:
        raise HTTPException(404, "Parameter not found")
    

    param_type = db.query(ParamType).filter(ParamType.id_param_type == param.id_param_type).first()
    if not param_type or param_type.sys_code != 'enum':
        raise HTTPException(400, "Parameter is not enum type")
    
    return db.query(EnumValue).filter(EnumValue.parameter_id == id).all()

# ==================== API PRODUCT PARAMETER VALUES ====================
@app.get("/products/{id}/parameters")
def get_product_parameter_values(id: int, db: Session = Depends(get_db)):
    values = db.query(ProductParameterValue).filter(ProductParameterValue.id_product == id).all()
    result = []
    for v in values:
        param = db.query(Parameter).filter(Parameter.id_parameter == v.id_parameter).first()
        if not param:
            continue
        

        param_type = db.query(ParamType).filter(ParamType.id_param_type == param.id_param_type).first()
        

        value_display = None
        if param_type and param_type.sys_code == 'string':
            value_display = v.value_string
        elif param_type and param_type.sys_code == 'integer':
            value_display = v.value_integer
        elif param_type and param_type.sys_code == 'enum':
            enum_val = db.query(EnumValue).filter(EnumValue.id_enum_value == v.value_enum).first()
            value_display = enum_val.value_name if enum_val else None
        
        result.append({
            "id_parameter": param.id_parameter,
            "name": param.name,
            "code": param.code,
            "param_type_code": param_type.sys_code if param_type else None,
            "param_type_name": param_type.name if param_type else None,
            "value": value_display
        })
    return result

@app.put("/products/{id}/parameters/{pid}")
def update_product_parameter_value(
    id: int, pid: int,
    value_string: Optional[str] = None,
    value_integer: Optional[int] = None,
    value_enum: Optional[int] = None,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id_product == id).first()
    if not product:
        raise HTTPException(404, "Product not found")
    
    param = db.query(Parameter).filter(Parameter.id_parameter == pid).first()
    if not param:
        raise HTTPException(404, "Parameter not found")
    

    param_type = db.query(ParamType).filter(ParamType.id_param_type == param.id_param_type).first()
    if not param_type:
        raise HTTPException(400, "Parameter type not found")
    
    pv = db.query(ProductParameterValue).filter(
        ProductParameterValue.id_product == id,
        ProductParameterValue.id_parameter == pid
    ).first()
    if not pv:
        pv = ProductParameterValue(id_product=id, id_parameter=pid)
        db.add(pv)
    

    if param_type.sys_code == 'string':
        pv.value_string = value_string
        pv.value_integer = None
        pv.value_enum = None
    elif param_type.sys_code == 'integer':
        pv.value_integer = value_integer
        pv.value_string = None
        pv.value_enum = None
    elif param_type.sys_code == 'enum':
        if value_enum:
            enum_val = db.query(EnumValue).filter(EnumValue.id_enum_value == value_enum).first()
            if not enum_val:
                raise HTTPException(400, "Enum value not found")
        pv.value_enum = value_enum
        pv.value_string = None
        pv.value_integer = None
    else:
        raise HTTPException(400, f"Unknown parameter type: {param_type.sys_code}")
    
    db.commit()
    return {"ok": True}

# ============ MANAGING CATEGORY CHARACTERISTICS (NEW ADDED) ============

@app.post("/categories/{id_category}/parameters")
def add_parameter_to_category(
    id_category: int,
    id_parameter: int,
    is_mandatory: bool = False,
    db: Session = Depends(get_db)
):
    """Add a parameter to the list."""

    category = db.query(Category).filter(Category.id_category == id_category).first()
    if not category:
        raise HTTPException(404, "Category not found")
    
    parameter = db.query(Parameter).filter(Parameter.id_parameter == id_parameter).first()
    if not parameter:
        raise HTTPException(404, "Parameter not found")
    

    existing = db.query(CategoryParameter).filter(
        CategoryParameter.id_category == id_category,
        CategoryParameter.id_parameter == id_parameter
    ).first()
    if existing:
        raise HTTPException(400, "Parameter already added to this category")
    

    max_order = db.query(CategoryParameter).filter(
        CategoryParameter.id_category == id_category
    ).count()
    
    new_cp = CategoryParameter(
        id_category=id_category,
        id_parameter=id_parameter,
        is_mandatory=is_mandatory,
        display_order=max_order + 1
    )
    db.add(new_cp)
    db.commit()
    db.refresh(new_cp)
    return {"status": "success", "message": "Parameter added to category"}


@app.put("/categories/{id_category}/parameters/{id_parameter}")
def update_category_parameter(
    id_category: int,
    id_parameter: int,
    is_mandatory: bool = False,
    db: Session = Depends(get_db)
):
    """Update the parameter information in the list (e.g., mandatory)."""
    cp = db.query(CategoryParameter).filter(
        CategoryParameter.id_category == id_category,
        CategoryParameter.id_parameter == id_parameter
    ).first()
    if not cp:
        raise HTTPException(404, "Parameter not found in this category")
    
    cp.is_mandatory = is_mandatory
    db.commit()
    return {"status": "success", "message": "Parameter updated"}


@app.delete("/categories/{id_category}/parameters/{id_parameter}")
def remove_parameter_from_category(
    id_category: int,
    id_parameter: int,
    db: Session = Depends(get_db)
):
    """Xóa parameter khỏi danh mục"""
    cp = db.query(CategoryParameter).filter(
        CategoryParameter.id_category == id_category,
        CategoryParameter.id_parameter == id_parameter
    ).first()
    if not cp:
        raise HTTPException(404, "Parameter not found in this category")
    
    # 🔥 THÊM: Xóa tất cả product_parameter_values liên quan đến parameter này TRONG category này
    # Lấy tất cả sản phẩm thuộc category này
    products = db.query(Product).filter(Product.category_id == id_category).all()
    product_ids = [p.id_product for p in products]
    
    if product_ids:
        # Xóa giá trị của parameter này trong các sản phẩm của category
        db.query(ProductParameterValue).filter(
            ProductParameterValue.id_product.in_(product_ids),
            ProductParameterValue.id_parameter == id_parameter
        ).delete()
    
    db.delete(cp)
    db.commit()
    return {"status": "success", "message": "Parameter removed from category"}


@app.put("/categories/{id_category}/parameters/reorder")
def reorder_category_parameters(
    id_category: int,
    ordered_ids: str,
    db: Session = Depends(get_db)
):
    """Rearrange the order of parameters in the category"""
    ids = [int(x) for x in ordered_ids.split(",")]
    for idx, param_id in enumerate(ids):
        cp = db.query(CategoryParameter).filter(
            CategoryParameter.id_category == id_category,
            CategoryParameter.id_parameter == param_id
        ).first()
        if cp:
            cp.display_order = idx + 1
    db.commit()
    return {"status": "success", "message": "Parameters reordered"}

@app.put("/categories/{id_category}/parameters/{id_parameter}/up")
def move_category_parameter_up(
    id_category: int,
    id_parameter: int,
    db: Session = Depends(get_db)
):
    """Move up one level"""

    params = db.query(CategoryParameter).filter(
        CategoryParameter.id_category == id_category
    ).order_by(CategoryParameter.display_order).all()
    

    current_idx = None
    for i, p in enumerate(params):
        if p.id_parameter == id_parameter:
            current_idx = i
            break
    
    if current_idx is None or current_idx == 0:
        raise HTTPException(400, "Parameter already at first position or not found")
    

    prev_param = params[current_idx - 1]
    current_order = params[current_idx].display_order
    prev_order = prev_param.display_order
    
    # Swap display_order
    params[current_idx].display_order = prev_order
    prev_param.display_order = current_order
    
    db.commit()
    return {"status": "success", "message": "Moved up"}


@app.put("/categories/{id_category}/parameters/{id_parameter}/down")
def move_category_parameter_down(
    id_category: int,
    id_parameter: int,
    db: Session = Depends(get_db)
):
    """Movedown one level"""
    params = db.query(CategoryParameter).filter(
        CategoryParameter.id_category == id_category
    ).order_by(CategoryParameter.display_order).all()
    

    current_idx = None
    for i, p in enumerate(params):
        if p.id_parameter == id_parameter:
            current_idx = i
            break
    
    if current_idx is None or current_idx == len(params) - 1:
        raise HTTPException(400, "Parameter already at last position or not found")
    

    next_param = params[current_idx + 1]
    current_order = params[current_idx].display_order
    next_order = next_param.display_order
    
    # Swap display_order
    params[current_idx].display_order = next_order
    next_param.display_order = current_order
    
    db.commit()
    return {"status": "success", "message": "Moved down"}

@app.get("/categories/flat")
def get_categories_flat(db: Session = Depends(get_db)):
    categories = db.query(Category).order_by(Category.id_category).all()
    return [{"id": c.id_category, "name": c.name, "parent_id": c.parent_id} for c in categories]
@app.get("/categories/{id}/details")
def get_category_details(id: int, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id_category == id).first()
    if not category:
        raise HTTPException(404, "Category not found")
    
    return {
        "id": category.id_category,
        "name": category.name,
        "code": category.code,
        "parent_id": category.parent_id,
        "base_unit_id": category.base_unit_id
    }
# ==================== ROOT ====================
@app.get("/")
def root():
    return {"message": "Flower Shop API New v2.0 is running", "db": "flower_shop_new"}

@app.post("/sync-enum-values")
def sync_enum_values(db: Session = Depends(get_db)):
    """Đồng bộ tất cả enum_items vào enum_values (xóa trùng)"""
    
    ENUM_TO_PARAM = {
        "COLORS": "COLOR",
        "THEMES": "THEME",
        "PACK_MATERIALS": "MATERIAL",
        "COUNTRIES": "COUNTRY"
    }
    
    total_added = 0
    
    for enum_code, param_code in ENUM_TO_PARAM.items():
        # Tìm enum
        enum_obj = db.query(Enum).filter(Enum.code == enum_code).first()
        if not enum_obj:
            print(f"❌ Enum not found: {enum_code}")
            continue
        
        # Tìm parameter
        param = db.query(Parameter).filter(Parameter.code == param_code).first()
        if not param:
            print(f"❌ Parameter not found: {param_code}")
            continue
        
        # 🔥 XÓA CŨ CỦA PARAMETER NÀY 🔥
        deleted = db.query(EnumValue).filter(EnumValue.parameter_id == param.id_parameter).delete()
        print(f"🗑️ Deleted {deleted} old values for {param.name}")
        
        db.commit()  # 🔥 THÊM DÒNG NÀY: commit ngay sau khi xóa
        
        # 🔥 THÊM LẠI TỪ ENUM_ITEMS 🔥
        items = db.query(EnumItem).filter(EnumItem.id_enum == enum_obj.id_enum).order_by(EnumItem.order_num).all()
        
        for item in items:
            # Kiểm tra trước khi thêm (tránh trùng)
            existing = db.query(EnumValue).filter(
                EnumValue.parameter_id == param.id_parameter,
                EnumValue.value_name == item.item_name
            ).first()
            
            if not existing:
                enum_value = EnumValue(
                    parameter_id=param.id_parameter,
                    value_name=item.item_name,
                    value_code=item.item_code
                )
                db.add(enum_value)
                total_added += 1
                print(f"✅ Added: {item.item_name} -> {param.name}")
            else:
                print(f"⚠️ Already exists: {item.item_name}")
    
    db.commit()
    return {"message": f"Synced {total_added} enum values successfully"}

# ==================== CHẠY SERVER ====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)