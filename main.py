from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# FastAPI 應用
app = FastAPI()

# 數據庫設置
DATABASE_URL = "mysql+pymysql://root:yourpassword@localhost:3306/fastapi_crud"
engine = create_engine(DATABASE_URL)

# # 嘗試創建數據庫
# with engine.connect() as conn:
#     conn.execute("CREATE DATABASE IF NOT EXISTS fastapi_crud")
#     conn.execute("USE fastapi_crud")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 定義數據表模型
class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)
    price = Column(Float, nullable=False)

# 初始化數據庫
Base.metadata.create_all(bind=engine)

# 數據庫會話依賴
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 路由：新增資料
@app.post("/items/")
def create_item(name: str, description: str, price: float, db: Session = Depends(get_db)):
    item = Item(name=name, description=description, price=price)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

# 路由：查詢單筆資料
@app.get("/items/{item_id}")
def read_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

# 路由：更新資料
@app.put("/items/{item_id}")
def update_item(item_id: int, name: str, description: str, price: float, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.name = name
    item.description = description
    item.price = price
    db.commit()
    db.refresh(item)
    return item

# 路由：刪除資料
@app.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"message": "Item deleted"}
