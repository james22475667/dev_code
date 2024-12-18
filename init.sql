-- 創建數據庫（如果尚未存在）
CREATE DATABASE IF NOT EXISTS fastapi_crud;

-- 使用該數據庫
USE fastapi_crud;

-- 創建數據表
CREATE TABLE IF NOT EXISTS items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price FLOAT NOT NULL
);
